"""Bounded HTTPS transport with DNS validation and pinned connections.

The socket connects to the checked numeric address; TLS still validates the
original hostname. Redirects must stay on the adapter's explicit host allowlist.
"""

import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


class SourceError(Exception):
    def __init__(self, code: str, retry_after: int = 0):
        self.code, self.retry_after = code, min(3600, max(0, retry_after))
        super().__init__(code)


def public_url(value: str) -> str:
    """Validate stored links without requesting them. Fetches also validate DNS."""
    try:
        if len(value) > 2000 or any(ord(c) < 33 or ord(c) == 127 for c in value):
            raise ValueError
        url = urlsplit(value)
        host = (url.hostname or "").lower().rstrip(".")
        if (
            url.scheme not in ("http", "https")
            or url.username is not None
            or url.password is not None
            or url.port not in (None, 80 if url.scheme == "http" else 443)
            or not host
            or "\\" in value
            or "%" in host
            or "." not in host
            or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
            or host in ("metadata.google.internal", "metadata.google", "instance-data.ec2.internal")
        ):
            raise ValueError
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError
        except ValueError as error:
            # Distinguish an invalid numeric address from a normal DNS name.
            if host.replace(".", "").isdigit() or ":" in host:
                raise ValueError from error
        query = [
            (k, v)
            for k, v in parse_qsl(url.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in ("source", "gh_src", "lever-source")
        ]
        return urlunsplit((url.scheme.lower(), host, url.path or "/", urlencode(query), ""))
    except (ValueError, UnicodeError):
        raise SourceError("unsafe_url") from None


def resolve_public(host: str) -> list[str]:
    try:
        addresses = list(
            dict.fromkeys(str(x[4][0]) for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        )
        if not addresses or any(not ipaddress.ip_address(x).is_global for x in addresses):
            raise SourceError("unsafe_destination")
        return addresses
    except (OSError, ValueError):
        raise SourceError("dns_unavailable") from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        self.tls_context = ssl.create_default_context()
        super().__init__(host, timeout=timeout, context=self.tls_context)
        self.address = address

    def connect(self):
        # Never pass the hostname to create_connection (DNS rebinding).
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class SafeHTTP:
    def __init__(self, hosts: set[str], interval: float = 1, budget: float = 45):
        self.hosts = hosts
        self.interval = max(1, min(interval, 10))
        self.deadline = time.monotonic() + budget
        self.last_request = 0.0
        self.requests = 0

    def get(self, value: str, headers: dict | None = None):
        for attempt in range(2):
            try:
                return self._get(value, headers or {})
            except SourceError as error:
                if error.code not in ("rate_limited", "provider_unavailable") or attempt:
                    raise
                delay = max(1, error.retry_after)
                if delay > 3 or time.monotonic() + delay + 1 >= self.deadline:
                    raise
                time.sleep(delay)
        raise SourceError("provider_unavailable")

    def _get(self, value: str, headers: dict):
        for _ in range(4):
            url = urlsplit(public_url(value))
            if url.scheme != "https" or url.hostname not in self.hosts:
                raise SourceError("unapproved_host")
            remaining = self.deadline - time.monotonic()
            delay = max(0, self.last_request + self.interval - time.monotonic())
            if remaining <= delay + 1 or self.requests >= 12:
                raise SourceError("request_budget_exhausted")
            if delay:
                time.sleep(delay)
            addresses = resolve_public(url.hostname)
            connection = PinnedHTTPS(url.hostname, addresses[0], min(8, remaining - delay))
            self.requests += 1
            self.last_request = time.monotonic()
            try:
                connection.request(
                    "GET",
                    urlunsplit(("", "", url.path, url.query, "")),
                    headers={"Accept": "application/json", "User-Agent": "ApplyOS/2", **headers},
                )
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    # No cross-host redirects: credentials never leave their endpoint.
                    target = urljoin(value, response.getheader("Location", ""))
                    if urlsplit(target).hostname != url.hostname:
                        raise SourceError("unsafe_redirect")
                    value = target
                    continue
                if response.status == 429:
                    retry = response.getheader("Retry-After", "60")
                    raise SourceError("rate_limited", int(retry) if retry.isdigit() else 60)
                if response.status >= 500:
                    raise SourceError("provider_unavailable")
                if response.status != 200:
                    raise SourceError("provider_rejected_request")
                if "json" not in response.getheader("Content-Type", "").lower():
                    raise SourceError("invalid_response")
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= self.deadline:
                        raise SourceError("request_budget_exhausted")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 4 * 1024 * 1024:
                        raise SourceError("response_too_large")
                    chunks.append(chunk)
                return json.loads(b"".join(chunks))
            except (OSError, http.client.HTTPException, json.JSONDecodeError, UnicodeError):
                raise SourceError("provider_unavailable") from None
            finally:
                connection.close()
        raise SourceError("too_many_redirects")
