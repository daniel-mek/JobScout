import re
from pathlib import Path
from typing import Protocol

from .config import Settings


class FileStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def safe_key(key: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}\.(pdf|docx)", key):
        raise ValueError("Invalid storage key")
    return key


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    def path(self, key: str) -> Path:
        return self.root / safe_key(key)

    def put(self, key: str, content: bytes) -> None:
        with self.path(key).open("xb") as f:
            f.write(content)
        self.path(key).chmod(0o600)

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, config: Settings):
        import boto3

        self.bucket = config.s3_bucket
        self.client = boto3.client("s3", endpoint_url=config.s3_endpoint_url, region_name=config.s3_region)

    def put(self, key: str, content: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=safe_key(key),
            Body=content,
            ServerSideEncryption="AES256",
            ContentType="application/octet-stream",
        )

    def read(self, key: str) -> bytes:
        return bytes(self.client.get_object(Bucket=self.bucket, Key=safe_key(key))["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=safe_key(key))


def storage_for(config: Settings) -> FileStorage:
    return S3Storage(config) if config.storage_backend == "s3" else LocalStorage(config.storage_path)
