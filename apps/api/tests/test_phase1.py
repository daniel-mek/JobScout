import io
import time
import zipfile

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from apps.api.applyos.config import Settings
from apps.api.applyos.models import AuthAttempt, Session, User
from apps.api.applyos.parsing import DeterministicResumeParser
from apps.api.applyos.schemas import ProfileData
from apps.api.applyos.security import digest
from apps.api.applyos.storage import LocalStorage, S3Storage
from apps.api.tests.conftest import confirm, csrf, docx_bytes, signup, upload


def test_authentication_sessions_and_logout(client, application):
    password = "a safe test passphrase 42"
    assert client.get("/auth/me").status_code == 401
    signup(client)
    cookie = client.cookies.get("applyos_session")
    assert client.get("/auth/me").json()["email"] == "person@example.com"
    with application.state.sessions() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert password not in user.password_hash
        assert db.get(Session, digest(cookie)).token_hash != cookie
    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers=csrf(client)).status_code == 200
    assert client.get("/auth/me").status_code == 401
    client.cookies.set("applyos_session", cookie, domain="testserver.local", path="/")
    assert client.get("/auth/me").status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "person@example.com", "password": "incorrect-password"}
        ).status_code
        == 401
    )
    assert (
        client.post("/auth/login", json={"email": "PERSON@example.com", "password": password}).status_code
        == 200
    )
    assert client.cookies.get("applyos_session") != cookie


def test_origin_validation_and_no_password_echo(client):
    for origin in ("http://evil.example", "null", ""):
        result = client.post(
            "/auth/signup", json={"email": "x@example.com", "password": "short"}, headers={"origin": origin}
        )
        assert result.status_code == 403
    response = client.post("/auth/signup", json={"email": "not-an-email", "password": "do-not-echo-me"})
    assert response.status_code == 422
    assert "do-not-echo-me" not in response.text


def test_cookie_flags_and_expiration(client, application):
    result = client.post(
        "/auth/signup", json={"email": "test@example.com", "password": "a safe test passphrase 42"}
    )
    cookies = result.headers.get_list("set-cookie")
    assert any("HttpOnly" in c and "SameSite=lax" in c for c in cookies)
    with application.state.sessions() as db:
        session = db.get(Session, digest(client.cookies.get("applyos_session")))
        session.expires_at = int(time.time()) - 1
        db.commit()
    assert client.get("/auth/me").status_code == 401


def test_production_fails_closed():
    with pytest.raises(ValidationError):
        Settings(environment="production")
    with pytest.raises(ValidationError):
        Settings(storage_backend="s3")


def test_login_throttle_persists_across_clients(client, application):
    for _ in range(10):
        assert (
            client.post(
                "/auth/login", json={"email": "unknown@example.com", "password": "incorrect-password"}
            ).status_code
            == 401
        )
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        assert (
            other.post(
                "/auth/login", json={"email": "unknown@example.com", "password": "incorrect-password"}
            ).status_code
            == 429
        )
    with application.state.sessions() as db:
        assert db.scalar(select(AuthAttempt)) is not None


def test_onboarding_persists_full_journey(client, application):
    signup(client)
    assert client.get("/onboarding").json()["next_step"] == "upload"
    assert client.post("/onboarding/complete", headers=csrf(client)).status_code == 409
    assert client.get("/dashboard").status_code == 409
    version = upload(client)
    assert version.status_code == 201, version.text
    version = version.json()
    assert {s["name"] for s in version["draft"]["skills"]} >= {"Python", "PostgreSQL", "Linux"}
    assert client.get("/profile").json()["profile"] is None
    assert client.get("/onboarding").json()["next_step"] == "review"
    reviewed = confirm(client, version)
    assert reviewed.status_code == 200, reviewed.text
    assert client.get("/onboarding").json()["next_step"] == "paths"
    roles = client.get("/role-families").json()
    assert len(roles) == 11
    assert (
        client.put("/career-preferences", json={"role_ids": ["invented"]}, headers=csrf(client)).status_code
        == 422
    )
    assert (
        client.put(
            "/career-preferences",
            json={"role_ids": ["software-engineering", "it-systems"]},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.get("/onboarding").json()["next_step"] == "preferences"
    assert (
        client.put(
            "/preferences",
            json={"locations": ["Jersey City"], "arrangements": ["REMOTE"], "minimum_salary": 60000},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.get("/onboarding").json()["next_step"] == "requirements"
    assert (
        client.put(
            "/requirements",
            json={"allow_contract": False, "countries": ["US"], "needs_sponsorship": None},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.post("/onboarding/complete", headers=csrf(client)).status_code == 200
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as refreshed:
        refreshed.cookies.update(client.cookies)
        state = refreshed.get("/onboarding").json()
        assert state["complete"] is True
        assert state["requirements"]["needs_sponsorship"] is None
        assert refreshed.get("/dashboard").status_code == 200
    assert len(client.get("/profile/history").json()) == 1


def test_owner_isolation_for_reads_writes_and_downloads(client, application):
    signup(client, "alice@example.com")
    alice = upload(client).json()
    assert confirm(client, alice).status_code == 200
    alice_id = alice["resume"]["id"]
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as bob:
        signup(bob, "bob@example.com")
        assert bob.get(f"/resumes/{alice_id}").status_code == 404
        assert bob.get(f"/resumes/{alice_id}/download").status_code == 404
        assert bob.get("/resumes").json() == []
        assert bob.get("/profile").json()["profile"] is None
        assert bob.get("/profile/history").json() == []
        assert confirm(bob, alice).status_code == 404
        assert (
            bob.put("/preferences", json={"locations": ["Elsewhere"]}, headers=csrf(bob)).status_code == 200
        )
    assert client.get("/onboarding").json()["preferences"] is None
    assert client.get("/profile").json()["profile"]["name"] == "Taylor Example"


def test_resume_reupload_preserves_confirmed_profile_and_history(client):
    signup(client)
    original_content = docx_bytes()
    v1 = upload(client, original_content).json()
    assert confirm(client, v1).status_code == 200
    original = client.get("/profile").json()
    v2 = upload(client, docx_bytes("Changed Name\nSkills\nJavaScript")).json()
    assert v2["resume"]["version"] == 2
    assert client.get("/profile").json() == original
    assert client.get("/onboarding").json()["next_step"] == "review"
    assert confirm(client, v1, 1).status_code == 409
    assert confirm(client, v2, 0).status_code == 409
    assert confirm(client, v2, 1).status_code == 200
    assert (
        client.get(f"/resumes/{v1['resume']['id']}").json()["confirmed_profile"]["name"] == "Taylor Example"
    )
    assert len(client.get("/profile/history").json()) == 2
    assert client.get(f"/resumes/{v1['resume']['id']}/download").content == original_content


@pytest.mark.parametrize(
    "filename,mime,content,status",
    [
        ("resume.txt", "text/plain", b"not a document", 415),
        ("resume.pdf", "application/pdf", b"not a PDF", 422),
        ("resume.docx", "application/pdf", b"no", 415),
        (
            "resume.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"not a zip",
            422,
        ),
        ("resume.pdf", "application/pdf", b"a" * (5 * 1024 * 1024 + 1), 413),
    ],
)
def test_upload_validation(client, filename, mime, content, status):
    signup(client)
    assert upload(client, content, filename, mime).status_code == status
    assert client.get("/resumes").json() == []


def test_docx_external_relationship_rejected(client):
    signup(client)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx_bytes())) as original, zipfile.ZipFile(out, "w") as modified:
        for name in original.namelist():
            if name != "word/_rels/document.xml.rels":
                modified.writestr(name, original.read(name))
        modified.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships><Relationship TargetMode="External" Target="http://169.254.169.254/"/></Relationships>',
        )
    assert upload(client, out.getvalue()).status_code == 422


def test_parser_never_fills_unsupported_claims_and_validates_output():
    parsed = DeterministicResumeParser().parse(
        "Taylor Example\nSkills\nPython and Postgres\nProjects\nWrote a Python script."
    )
    assert parsed.location == "" and parsed.graduation_date == ""
    assert parsed.experience == []
    assert {s.name for s in parsed.skills} == {"Python", "PostgreSQL"}
    assert all(s.evidence for s in parsed.skills)
    assert any(s.evidence_ref == "project:0" for s in parsed.skills if s.name == "Python")
    with pytest.raises(ValidationError):
        ProfileData.model_validate({"skills": [{"name": "Python", "evidence_ref": "experience:5"}]})
    with pytest.raises(ValidationError):
        ProfileData.model_validate({"unapproved_field": True})


def test_profile_malformed_output_and_confirmation_required(client):
    signup(client)
    version = upload(client).json()
    request = {
        "expected_revision": 0,
        "resume_version_id": version["resume"]["id"],
        "profile": version["draft"],
        "confirmed": False,
    }
    assert client.put("/profile", json=request, headers=csrf(client)).status_code == 422
    request["confirmed"] = True
    request["profile"]["skills"].append({"name": "Fake", "evidence_ref": "project:900"})
    assert client.put("/profile", json=request, headers=csrf(client)).status_code == 422
    assert client.get("/profile").json()["revision"] == 0


def test_preferences_constraints_and_nulls(client):
    signup(client)
    assert client.put("/requirements", json={"countries": ["USA"]}, headers=csrf(client)).status_code == 422
    assert (
        client.put("/requirements", json={"max_requested_experience": -1}, headers=csrf(client)).status_code
        == 422
    )
    assert client.put("/requirements", json={}, headers=csrf(client)).status_code == 200
    assert all(
        x is None for k, x in client.get("/onboarding").json()["requirements"].items() if k != "countries"
    )
    assert client.put("/preferences", json={"minimum_salary": -2}, headers=csrf(client)).status_code == 422


def test_storage_rejects_path_traversal_and_is_private(tmp_path):
    storage = LocalStorage(tmp_path / "files")
    with pytest.raises(ValueError):
        storage.read("../../secret.pdf")
    key = "a" * 32 + ".pdf"
    storage.put(key, b"private")
    assert storage.read(key) == b"private"
    assert storage.path(key).stat().st_mode & 0o777 == 0o600
    storage.delete(key)
    assert not storage.path(key).exists()


def test_migrations_round_trip(application):
    cfg = Config("apps/api/alembic.ini")
    command.check(cfg)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with application.state.sessions() as db:
        from apps.api.applyos.models import RoleFamily

        assert len(list(db.scalars(select(RoleFamily)))) == 11


def test_pdf_upload_success_and_text_review(client):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 12 Tf 20 700 Td (Taylor Example) Tj 0 -20 Td (Skills) Tj 0 -20 Td (Python, Linux) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    out = io.BytesIO()
    writer.write(out)
    signup(client)
    result = upload(client, out.getvalue(), "resume.pdf", "application/pdf")
    assert result.status_code == 201, result.text
    assert "Python" in result.json()["extracted_text"]


def test_extraction_timeout_and_parser_failure_leave_no_version(client, application, monkeypatch):
    import subprocess

    signup(client)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("extract", 12)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", timeout)
        assert upload(client).status_code == 422
    assert client.get("/resumes").json() == []
    from fastapi import HTTPException

    from apps.api.applyos.models import User
    from apps.api.applyos.services import ResumeService

    class InvalidParser:
        name = "invalid"

        def parse(self, text):
            return ProfileData.model_construct(skills=[{"name": 123, "invented": True}])

    with application.state.sessions() as db:
        owner = db.scalar(select(User)).id
        with pytest.raises(HTTPException) as error:
            ResumeService(
                db, owner, application.state.config, application.state.storage, parser=InvalidParser()
            ).upload(
                "test.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                docx_bytes(),
            )
        assert error.value.status_code == 422
    assert client.get("/resumes").json() == []


def test_s3_storage_uses_private_encrypted_objects(monkeypatch):
    calls = []

    class Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(b"resume")}

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *a, **k: Client())
    store = S3Storage(Settings(storage_backend="s3", s3_bucket="private-test"))
    key = "b" * 32 + ".pdf"
    store.put(key, b"resume")
    assert store.read(key) == b"resume"
    store.delete(key)
    assert calls[0][1]["ServerSideEncryption"] == "AES256"
    assert "ACL" not in calls[0][1]
