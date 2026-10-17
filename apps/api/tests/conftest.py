import io
import os

import pytest
from alembic import command
from alembic.config import Config
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.applyos.config import Settings, settings
from apps.api.applyos.main import create_app
from apps.api.applyos.models import Base


@pytest.fixture
def application(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    if "postgresql" in url and not url.endswith("/applyos_test"):
        raise RuntimeError("PostgreSQL tests require a dedicated applyos_test database")
    monkeypatch.setenv("DATABASE_URL", url)
    settings.cache_clear()
    config = Settings(database_url=url, storage_path=tmp_path / "files", environment="test")
    app = create_app(config)
    if "postgresql" in url:
        Base.metadata.drop_all(app.state.engine)
        with app.state.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    command.upgrade(Config("apps/api/alembic.ini"), "head")
    yield app
    app.state.engine.dispose()
    settings.cache_clear()


@pytest.fixture
def client(application):
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as client:
        yield client


def signup(client, email="person@example.com"):
    response = client.post("/auth/signup", json={"email": email, "password": "a safe test passphrase 42"})
    assert response.status_code == 201, response.text
    return response.json()


def csrf(client):
    return {"x-csrf-token": client.cookies.get("applyos_csrf")}


def docx_bytes(
    text="Taylor Example\nEducation\nExample University\nSkills\nPython, PostgreSQL, Linux\nProjects\nBuilt a Python service with PostgreSQL.",
):
    out = io.BytesIO()
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    document.save(out)
    return out.getvalue()


def upload(
    client,
    content=None,
    filename="resume.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
):
    return client.post(
        "/resumes", files={"file": (filename, content or docx_bytes(), mime)}, headers=csrf(client)
    )


def confirm(client, version, revision=0):
    return client.put(
        "/profile",
        json={
            "expected_revision": revision,
            "resume_version_id": version["resume"]["id"],
            "profile": version["draft"],
            "confirmed": True,
        },
        headers=csrf(client),
    )
