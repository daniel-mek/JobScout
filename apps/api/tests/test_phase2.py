import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.applyos.jobs_models import (
    JobPosting,
    JobPostingVersion,
    JobSourceRecord,
    SourceHealth,
    SourcePolicy,
)
from apps.api.applyos.jobs_service import sanitize_policy_history
from apps.api.tests.conftest import csrf, signup
from packages.job_sources import adapters, safe_http
from packages.job_sources.adapters import Posting, convert, detect, fetch
from packages.job_sources.safe_http import PinnedHTTPS, SafeHTTP, SourceError, public_url, resolve_public


def posting(**changes):
    return Posting(
        **(
            {
                "external_id": "101",
                "title": "Junior Software Engineer",
                "company": "Example",
                "location": "New York",
                "description": "Build software and maintain Python services. " * 10,
                "application_url": "https://jobs.example.com/101",
                "posted_at": "2026-10-20T00:00:00Z",
            }
            | changes
        )
    )


def add_source(client, provider="greenhouse", board="example"):
    response = client.post(
        "/sources", json={"provider": provider, "board": board, "company": "Example"}, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def approve(application, provider="greenhouse", storage="allowed"):
    with application.state.sessions() as db:
        policy = db.get(SourcePolicy, provider)
        policy.approved_boards = ["example"]
        policy.status, policy.enabled, policy.description_storage, policy.next_run_at = (
            "APPROVED",
            True,
            storage,
            0,
        )
        for health in db.scalars(select(SourceHealth)):
            health.next_run_at = 0
        db.commit()


def run(client, *ids):
    response = client.post("/search-runs", json={"source_ids": list(ids)}, headers=csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_manual_import_persistence_versions_and_owner_isolation(client, application):
    signup(client)
    body = posting().model_dump()
    response = client.post("/jobs/manual", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["provenance"][0]["provider"] == "manual"
    assert job["data"]["experience_min"] is None
    assert len(job["versions"]) == 1
    body["posted_at"] = "2026-10-21T00:00:00Z"
    assert client.post("/jobs/manual", json=body, headers=csrf(client)).json()["revision"] == 1
    body["description"] = "Changed requirements"
    assert client.post("/jobs/manual", json=body, headers=csrf(client)).json()["revision"] == 2
    assert len(client.get("/jobs").json()) == 1
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert other.get("/jobs").json() == []
        assert other.get("/jobs/" + job["id"]).status_code == 404
        assert other.post("/jobs/manual", json=body, headers=csrf(other)).json()["id"] != job["id"]


def test_policy_gate_credentials_health_and_no_browser_approval(client, application, monkeypatch):
    signup(client)
    source = add_source(client)
    call = Mock(side_effect=AssertionError("Network must not run"))
    monkeypatch.setattr(adapters, "fetch", call)
    assert run(client, source)["results"][0]["code"] == "source_not_approved"
    assert not call.called
    registry = client.get("/source-registry").json()
    assert next(x for x in registry if x["id"] == "remotive")["status"] == "DISABLED"
    assert client.patch(
        "/source-registry/greenhouse", json={"status": "APPROVED"}, headers=csrf(client)
    ).status_code in (404, 405)
    for key in ("USAJOBS_API_KEY", "USAJOBS_EMAIL", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
        monkeypatch.delenv(key, raising=False)
    for provider in ("usajobs", "adzuna"):
        optional = add_source(client, provider)
        assert run(client, optional)["results"][0]["state"] == "configuration_required"
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert other.patch(f"/sources/{source}?enabled=false", headers=csrf(other)).status_code == 404
        assert (
            other.post("/search-runs", json={"source_ids": [source]}, headers=csrf(other)).status_code == 404
        )
    assert client.post("/search-runs", json={"source_ids": [source]}).status_code == 403


def test_ingestion_dedup_versions_archive_and_reappearance(client, application, monkeypatch):
    signup(client)
    source = add_source(client)
    approve(application)
    response = Mock(return_value=([posting()], True, 0))
    monkeypatch.setattr(adapters, "fetch", response)
    assert run(client, source)["state"] == "complete"
    key = client.get("/jobs").json()[0]["id"]
    approve(application)
    response.return_value = ([posting(posted_at="2026-10-21T00:00:00Z")], True, 0)
    run(client, source)
    assert client.get("/jobs/" + key).json()["revision"] == 1
    approve(application)
    response.return_value = ([posting(description="A meaningful change")], True, 0)
    run(client, source)
    assert client.get("/jobs/" + key).json()["revision"] == 2
    approve(application)
    response.return_value = ([], False, 0)
    assert run(client, source)["results"][0]["code"] == "partial_feed"
    assert client.get("/jobs/" + key).json()["active"]
    approve(application)
    response.return_value = ([], True, 0)
    run(client, source)
    archived = client.get("/jobs/" + key).json()
    assert not archived["active"] and archived["revision"] == 3
    approve(application)
    response.return_value = ([posting(description="A meaningful change")], True, 0)
    run(client, source)
    restored = client.get("/jobs/" + key).json()
    assert restored["active"] and restored["revision"] == 4
    assert len(restored["provenance"]) == 1
    assert len(client.get("/search-runs").json()) == 6


def test_source_failure_isolated_and_retry_backoff_persisted(client, application, monkeypatch):
    signup(client)
    bad, good = add_source(client), add_source(client, "lever")
    approve(application)
    approve(application, "lever")

    def provider(name, *args, **kwargs):
        if name == "greenhouse":
            raise SourceError("rate_limited", 600)
        return [posting()], True, 0

    monkeypatch.setattr(adapters, "fetch", provider)
    result = run(client, bad, good)
    assert [x["code"] for x in result["results"]] == ["rate_limited", "complete"]
    health = client.get("/sources").json()
    assert all(x["health"]["next_run_at"] > 0 for x in health if x["id"] == bad)
    assert run(client, bad)["results"][0]["code"] == "cooldown"
    assert len(client.get("/jobs").json()) == 1


def test_restricted_content_never_stored_and_tightening_purges_history(client, application, monkeypatch):
    signup(client)
    source = add_source(client)
    approve(application, storage="unknown")
    monkeypatch.setattr(adapters, "fetch", lambda *a, **k: ([posting()], True, 0))
    run(client, source)
    key = client.get("/jobs").json()[0]["id"]
    detail = client.get("/jobs/" + key).json()
    assert detail["data"]["description"] is None
    approve(application)
    run(client, source)
    assert client.get("/jobs/" + key).json()["data"]["description"]
    with application.state.sessions() as db:
        policy = db.get(SourcePolicy, "greenhouse")
        policy.description_storage = "prohibited"
        sanitize_policy_history(db, policy)
        db.commit()
        for model, field in (
            (JobPosting, "data"),
            (JobPostingVersion, "data"),
            (JobSourceRecord, "normalized_data"),
        ):
            for row in db.scalars(select(model)):
                assert getattr(row, field)["description"] is None
    assert all(v["data"]["description"] is None for v in client.get("/jobs/" + key).json()["versions"])


def test_titles_alone_never_merge_and_multi_source_provenance_survives(client, application, monkeypatch):
    signup(client)
    first, second = add_source(client), add_source(client, "lever")
    approve(application)
    approve(application, "lever")
    monkeypatch.setattr(adapters, "fetch", lambda provider, *a, **k: ([posting()], True, 0))
    run(client, first, second)
    jobs = client.get("/jobs").json()
    assert len(jobs) == 1
    assert len(client.get("/jobs/" + jobs[0]["id"]).json()["provenance"]) == 2
    approve(application)
    monkeypatch.setattr(
        adapters,
        "fetch",
        lambda *a, **k: (
            [
                posting(
                    external_id="102",
                    application_url="https://jobs.example.com/102",
                    description="Different team",
                )
            ],
            True,
            0,
        ),
    )
    run(client, first)
    assert len(client.get("/jobs").json()) == 2
    assert client.get("/jobs/" + jobs[0]["id"]).json()["active"]  # Lever still lists it.


def test_saved_searches_titles_and_run_ownership(client, application):
    signup(client)
    source = add_source(client)
    saved = client.post(
        "/saved-searches", json={"name": "My employer", "source_ids": [source]}, headers=csrf(client)
    ).json()
    assert client.post(f"/saved-searches/{saved['id']}/run", headers=csrf(client)).status_code == 201
    assert client.get("/saved-searches").json()[0]["name"] == "My employer"
    assert (
        client.post("/search-titles", json={"title": "Software Engineer I"}, headers=csrf(client)).status_code
        == 201
    )
    assert len(client.get("/search-titles").json()) == 1
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        for path in ("/search-titles", "/saved-searches", "/search-runs", "/sources"):
            assert other.get(path).json() == []
        assert other.post(f"/saved-searches/{saved['id']}/run", headers=csrf(other)).status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/x",
        "http://127.0.0.1",
        "http://169.254.169.254/latest",
        "http://10.2.3.4",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "file:///etc/passwd",
        "https://user:pass@example.com",
        "https://jobs.example.com:444/x",
        "http://metadata.google.internal",
        "https://example.com\\@127.0.0.1",
        "https://2130706433",
        "https://127.1",
        "https://example.com\n/x",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(SourceError):
        public_url(url)


def test_ssrf_dns_mixed_answers_and_pinned_tls(monkeypatch):
    monkeypatch.setattr(
        safe_http.socket,
        "getaddrinfo",
        lambda *a, **k: [
            (None, None, None, None, ("93.184.216.34", 443)),
            (None, None, None, None, ("10.0.0.1", 443)),
        ],
    )
    with pytest.raises(SourceError, match="unsafe_destination"):
        resolve_public("api.lever.co")
    socket = Mock()
    connect = Mock(return_value=socket)
    monkeypatch.setattr(safe_http.socket, "create_connection", connect)
    tls = Mock()
    monkeypatch.setattr(safe_http.ssl, "create_default_context", lambda: tls)
    connection = PinnedHTTPS("api.lever.co", "93.184.216.34", 3)
    connection.connect()
    assert connect.call_args.args[0] == ("93.184.216.34", 443)
    tls.wrap_socket.assert_called_once_with(socket, server_hostname="api.lever.co")


def test_redirect_validation_size_limits_and_rate_retry(monkeypatch):
    monkeypatch.setattr(safe_http, "resolve_public", lambda host: ["93.184.216.34"])
    connection = Mock()
    monkeypatch.setattr(safe_http, "PinnedHTTPS", lambda *a: connection)
    response = Mock(status=302)
    response.getheader.side_effect = lambda name, default="": (
        "https://127.0.0.1/secret" if name == "Location" else default
    )
    connection.getresponse.return_value = response
    with pytest.raises(SourceError, match="unsafe_redirect"):
        SafeHTTP({"api.lever.co"}).get("https://api.lever.co/v0/postings/example")
    response.status = 429
    response.getheader.side_effect = lambda name, default="": "600" if name == "Retry-After" else default
    with pytest.raises(SourceError, match="rate_limited") as error:
        SafeHTTP({"api.lever.co"}).get("https://api.lever.co/v0/postings/example")
    assert error.value.retry_after == 600
    response.status = 200
    response.getheader.side_effect = lambda *a: "application/json"
    response.read.return_value = b"x" * 65536
    with pytest.raises(SourceError, match="response_too_large"):
        SafeHTTP({"api.lever.co"}).get("https://api.lever.co/v0/postings/example")


def test_supported_url_detection_and_manual_fallback_never_fetch(client, monkeypatch):
    signup(client)
    monkeypatch.setattr(adapters, "fetch", Mock(side_effect=AssertionError("no fetch")))
    assert detect("https://jobs.lever.co/example/101")["board"] == "example"
    assert detect("https://jobs.eu.lever.co/example/101")["board"] == "eu:example"
    assert detect("https://jobs.lever.co.evil.example/example")["supported"] is False
    assert detect("https://company.myworkdayjobs.com/jobs")["provider"] == "workday"
    result = client.post(
        "/jobs/import-url", json={"url": "https://careers.example.com/101"}, headers=csrf(client)
    )
    assert result.json()["status"] == "manual_required"
    assert (
        client.post("/jobs/import-url", json={"url": "http://127.0.0.1"}, headers=csrf(client)).status_code
        == 422
    )


def test_ats_normalizers_public_only_and_missing_values():
    greenhouse = convert(
        "greenhouse",
        {
            "id": 1,
            "title": "Engineer",
            "absolute_url": "https://jobs.example.com/1",
            "updated_at": "2026-10-20",
            "content": "<p>Build Python</p><script>bad()</script>",
        },
        "Example",
    )
    assert greenhouse.posted_at is None and greenhouse.arrangement is None
    assert greenhouse.description == "Build Python"
    lever = convert(
        "lever",
        {
            "id": "x",
            "text": "Engineer",
            "categories": {"commitment": "Full-time"},
            "createdAt": 1792454400000,
            "applyUrl": "https://jobs.lever.co/example/x/apply",
            "salaryRange": {"min": 60000, "max": 80000, "currency": "USD", "interval": "per-year"},
        },
        "Example",
    )
    assert lever.salary_min == 60000 and lever.posted_at is not None
    http = Mock()
    http.get.return_value = {
        "jobs": [
            {"title": "Hidden", "isListed": False},
            {"title": "Intern", "isListed": True, "id": "i", "jobUrl": "https://jobs.ashbyhq.com/example/i"},
            {
                "title": "Engineer",
                "isListed": True,
                "id": "e",
                "jobUrl": "https://jobs.ashbyhq.com/example/e",
            },
        ]
    }
    rows, complete, _ = fetch("ashby", "example", "Example", {}, {}, http)
    assert len(rows) == 1 and complete and rows[0].external_id == "e"


def test_smartrecruiters_public_details_and_resume_cursor():
    http = Mock()
    http.get.side_effect = [
        {"totalFound": 8, "content": [{"id": "1", "name": "Engineer"}]},
        {
            "id": "1",
            "name": "Engineer",
            "applyUrl": "https://jobs.smartrecruiters.com/example/1?oga=true",
            "jobAd": {"sections": {"jobDescription": {"text": "<p>Build systems</p>"}}},
        },
    ]
    rows, complete, cursor = fetch("smartrecruiters", "example", "Example", {}, {}, http)
    assert not complete and cursor == 1
    assert rows[0].description == "Build systems"
    assert "api.smartrecruiters.com" not in rows[0].application_url
    assert all("Authorization" not in str(call) for call in http.get.call_args_list)


def test_lever_pagination_and_optional_normalizers():
    http = Mock()
    item = {"id": "x", "text": "Engineer", "hostedUrl": "https://jobs.lever.co/example/x"}
    http.get.side_effect = [[{**item, "id": str(i)} for i in range(100)], []]
    rows, complete, _ = fetch("lever", "example", "Example", {}, {}, http)
    assert len(rows) == 100 and complete
    assert "skip=100" in http.get.call_args.args[0]
    usa = convert(
        "usajobs",
        {
            "PositionID": "12",
            "PositionTitle": "IT Specialist",
            "OrganizationName": "Agency",
            "PositionURI": "https://www.usajobs.gov/job/12",
            "QualificationSummary": "US citizenship required",
        },
        "",
    )
    assert usa.work_authorization is None  # Phase 3 extracts requirements; never guess.
    adzuna = convert(
        "adzuna",
        {
            "id": 1,
            "title": "Engineer",
            "company": {"display_name": "Example"},
            "redirect_url": "https://www.adzuna.com/land/1",
            "salary_is_predicted": 1,
            "salary_min": 12345,
        },
        "",
    )
    assert adzuna.salary_min is None
    assert json.loads(adzuna.model_dump_json())["country"] is None


def test_completed_pagination_cycle_archives_only_missing_jobs(client, application, monkeypatch):
    signup(client)
    source = add_source(client, "smartrecruiters")
    approve(application, "smartrecruiters")
    batch = Mock(
        return_value=(
            [
                posting(),
                posting(
                    external_id="gone",
                    application_url="https://jobs.example.com/gone",
                    description="Different role",
                ),
            ],
            True,
            0,
        )
    )
    monkeypatch.setattr(adapters, "fetch", batch)
    run(client, source)
    old = client.get("/jobs").json()
    approve(application, "smartrecruiters")
    batch.return_value = ([posting()], False, 5)
    run(client, source)
    assert all(j["active"] for j in client.get("/jobs").json())
    approve(application, "smartrecruiters")
    batch.return_value = (
        [
            posting(
                external_id="new", application_url="https://jobs.example.com/new", description="Other role"
            )
        ],
        True,
        0,
    )
    run(client, source)
    assert batch.call_args.kwargs["cursor"] == 5
    original = next(j for j in old if j["application_url"].endswith("/101"))
    gone = next(j for j in old if j["application_url"].endswith("/gone"))
    assert client.get("/jobs/" + original["id"]).json()["active"]
    assert not client.get("/jobs/" + gone["id"]).json()["active"]


def test_approval_scope_and_manual_unsafe_url_validation(client, application, monkeypatch):
    signup(client)
    source = add_source(client, board="unreviewed")
    approve(application)
    call = Mock(side_effect=AssertionError("Unreviewed board cannot run"))
    monkeypatch.setattr(adapters, "fetch", call)
    assert run(client, source)["results"][0]["code"] == "board_not_approved"
    assert not call.called
    body = posting().model_dump() | {"application_url": "http://127.0.0.1/private"}
    assert client.post("/jobs/manual", json=body, headers=csrf(client)).status_code == 422


def test_offline_postgresql_migration_and_catalog_snapshot(monkeypatch):
    import io

    from alembic import command
    from alembic.config import Config

    from apps.api.applyos.config import settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://offline:offline@localhost/offline")
    settings.cache_clear()
    output = io.StringIO()
    config = Config("apps/api/alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE job_source_records" in sql
    assert "INSERT INTO source_policies" in sql and "NEEDS_REVIEW" in sql
    assert "98c00bbaf877" in sql
    settings.cache_clear()
