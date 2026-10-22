from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.api.applyos.config import Settings
from apps.api.applyos.storage import VercelBlobStorage, storage_for


def test_marketplace_url_uses_installed_driver(monkeypatch):
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "jobscout.example.com")
    config = Settings(
        environment="production",
        database_url="postgresql://user:password@example.com/database?sslmode=require",
        cookie_secure=True,
        storage_backend="vercel_blob",
    )
    assert config.database_url.startswith("postgresql+psycopg://")
    assert config.web_origin == "https://jobscout.example.com"
    assert isinstance(storage_for(config), VercelBlobStorage)


def test_explicit_web_origin_wins(monkeypatch):
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "other.example.com")
    assert Settings(web_origin="https://jobs.example.com").web_origin == "https://jobs.example.com"


def test_blob_is_private_immutable_and_rejects_paths():
    key = "a" * 32 + ".pdf"
    storage = VercelBlobStorage()
    with (
        patch("vercel.blob.sync.put_blob") as put,
        patch("vercel.blob.sync.get_blob", return_value=SimpleNamespace(body=b"resume")) as get,
        patch("vercel.blob.sync.delete_blob") as delete,
    ):
        storage.put(key, b"resume")
        put.assert_called_once_with(
            key, b"resume", access="private", add_random_suffix=False, allow_overwrite=False
        )
        assert storage.read(key) == b"resume"
        get.assert_called_once_with(key, access="private")
        storage.delete(key)
        delete.assert_called_once_with(key)
        for bad_key in ("../resume.pdf", "https://example.com/resume.pdf", "/tmp/resume.pdf"):
            with pytest.raises(ValueError):
                storage.put(bad_key, b"resume")
            with pytest.raises(ValueError):
                storage.read(bad_key)
            with pytest.raises(ValueError):
                storage.delete(bad_key)
