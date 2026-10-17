# Security and privacy

## Current assessment

The current Worker uses a shared dashboard password, HMAC-signed expiring cookies with HttpOnly/Secure/SameSite=Lax, and a separate ingestion secret. Rendering escapes text and restricts clickable URLs. These are useful single-user controls, not multi-user authentication or an ownership model.

No account signup, secure password database, per-user authorization, upload pipeline, encrypted OAuth token store, or full privacy-deletion workflow exists. Authentication route code was inspected; this assessment is not a completed penetration test.

Legacy scout/posting.py permits generic HTML retrieval and reverse-engineered employer endpoints. It lacks comprehensive IP/DNS/redirect SSRF controls. Do not expose it as an arbitrary user-facing fetch API. Source policy and SSRF enforcement remain implementation work.

worker/wrangler.toml contains inherited deployment identifiers and an upstream GH_REPO. They are configuration, not credentials, but must be replaced/verified before deployment. A shared KV namespace must never be reused for unrelated users or environments.

## Phase 1 controls

- Use a mature password-hashing implementation with Argon2id; opaque revocable sessions, secure cookies, expiry, logout and rotation. Rate-limit login/recovery and avoid account enumeration.
- Validate CSRF/origin for cookie-authenticated mutations. Configure CORS explicitly; frontend route protection is not authorization.
- Every owner-scoped query/mutation/file download must authorize the current user. Test read, write, delete and identifier guessing using two users.
- PDF/DOCX uploads: bounded size, allowlisted extension/MIME plus detected format, safe randomized storage keys, extraction resource limits, no macros/external relationships, and private authenticated downloads. Treat parser text as untrusted. Never execute embedded content.
- Profile edits, resume versions, onboarding and preference updates must validate structured schemas; parsed claims remain unconfirmed until review.
- Do not log resume contents, passwords, session tokens, provider credentials, OAuth tokens, or generated candidate packets.
- Persist secrets server-side; use placeholder-only examples. Commit no real candidate data or credentials.

## Later-phase controls

URL import requires HTTP/HTTPS allowlisting, no URL credentials, strict ports, DNS resolution rejecting private/reserved/loopback/link-local addresses (IPv4 and IPv6), safe connections to validated destinations, and revalidation of every redirect including DNS rebinding defenses. Block cloud metadata and internal hostnames. Bound redirects, body size and duration. Parsing success is not permission to fetch.

AI outputs require schema validation, prompt-version/source-version metadata, and programmatic evidence checks. Unsupported candidate claims must fail or request confirmation; no fabricated skills, metrics, experience or company facts. No automatic applications or external messages.

OAuth uses supported provider flows, least privilege, state/PKCE where applicable, encrypted tokens, revocation/disconnection, and incremental synchronization. Email-derived status changes default to suggestions. Production secrets and provider tokens must never enter public frontend variables.

Uploads, application snapshots and artifacts must honor source retention policies. Document deletion across database, storage, queues, caches, credentials and backups. Backup expiry and restore behavior must be explicit. Do not claim immediate backup erasure if retention prevents it.

## Release gates

Verify authentication, cross-user isolation, IDOR, CSRF, XSS, safe redirects, SQL parameterization, SSRF, upload abuse, secret redaction and rate limiting with automated coverage. Add dependency auditing and error reporting as tooling appears. Production requires documented incident response, key rotation, migration rollback, backups and a tested restore. No multi-user deployment is certified by this preparation task.

