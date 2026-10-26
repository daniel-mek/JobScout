import csv
import io
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from apps.api.applyos.application_models import Application, ApplicationSnapshot
from apps.api.applyos.jobs_models import JobPosting, SourcePolicy
from apps.api.applyos.jobs_service import sanitize_policy_history
from apps.api.applyos.match_models import JobMatch
from apps.api.tests.conftest import confirm, csrf, signup, upload
from apps.api.tests.test_phase4 import job, ready


def prepare(client, key=None, status="PREPARING"):
    response = client.post(
        "/applications", json=dict(job_id=key or job(client), status=status), headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    return response.json()


def move(client, row, status, **extra):
    return client.post(
        f"/applications/{row['id']}/status",
        json=dict(expected_revision=row["revision"], status=status, **extra),
        headers=csrf(client),
    )


def applied(client, row):
    resume = client.get("/resumes").json()[0]["id"]
    response = move(
        client, row, "APPLIED", resume_version_id=resume, confirm_applied=True, note="Submitted manually"
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_application_preparation_submission_history_and_duplicate_prevention(client):
    ready(client)
    row = prepare(client)
    assert row["status"] == "PREPARING" and row["snapshots"][0]["data"]["description"] == "Python required."
    assert prepare(client, row["job_id"])["id"] == row["id"]
    assert client.get("/applications").json()["total"] == 1
    assert move(client, row, "INTERVIEW").status_code == 422
    assert move(client, row, "APPLIED").status_code == 422
    assert move(client, row, "APPLIED", confirm_applied=True).status_code == 422
    row = applied(client, row)
    assert row["applied_at"] and row["resume"]["version"] == 1
    applied_at = row["applied_at"]
    assert len(row["snapshots"]) == 2
    # A repeated click is idempotent, and stale revisions cannot rewrite history.
    assert move(client, row, "APPLIED").json()["revision"] == row["revision"]
    assert move(client, {**row, "revision": 1}, "INTERVIEW").status_code == 409
    for status in (
        "ONLINE_ASSESSMENT",
        "RECRUITER_SCREEN",
        "INTERVIEW",
        "FINAL_INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
        "PREPARING",
        "APPLIED",
    ):
        row = move(client, row, status).json()
        assert row["status"] == status and row["applied_at"] == applied_at
    history = row["history"]
    assert history[0]["previous_status"] is None
    assert history[1]["previous_status"] == "PREPARING" and history[1]["note"] == "Submitted manually"
    assert all(h["source"] == "USER" and h["created_at"] for h in history)
    assert len(row["snapshots"]) == 2
    assert client.get("/applications?status=APPLIED&company=Example&role=Python").json()["total"] == 1
    assert client.get("/applications?company=%25").json()["total"] == 0
    assert client.get("/applications?limit=1000").status_code == 422


def test_saved_to_preparing_and_distinct_immutable_applied_snapshot(client, application):
    ready(client)
    row = prepare(client, status="SAVED")
    row = move(client, row, "PREPARING").json()
    assert {s["stage"] for s in row["snapshots"]} == {"SAVED", "PREPARING"}
    # Same canonical posting changes after preparation, then disappears after applying.
    client.post(
        "/jobs/manual",
        json=dict(
            title="Changed Role",
            company="Example",
            application_url="https://example.com/one",
            description="Changed description",
        ),
        headers=csrf(client),
    )
    row = applied(client, row)
    snapshots = {s["stage"]: s for s in row["snapshots"]}
    assert snapshots["PREPARING"]["data"]["description"] == "Python required."
    assert snapshots["APPLIED"]["data"]["description"] == "Changed description"
    assert snapshots["APPLIED"]["job_revision"] == 2
    with application.state.sessions() as db:
        posting = db.get(JobPosting, row["job_id"])
        posting.active = False
        posting.data = {**posting.data, "description": "Gone"}
        db.commit()
    assert client.get(f"/applications/{row['id']}").json()["snapshots"] == row["snapshots"]


def test_source_storage_rules_redact_application_snapshots_and_match(client, application):
    ready(client)
    key = job(client)
    assert client.post(f"/jobs/{key}/match", headers=csrf(client)).status_code == 200
    row = prepare(client, key)
    assert row["match"] is not None
    original = row["match"]
    with application.state.sessions() as db:
        match = db.query(JobMatch).one()
        match.result = {**match.result, "resume_match": 1}
        db.commit()
    assert client.get(f"/applications/{row['id']}").json()["match"] == original
    with application.state.sessions() as db:
        policy = db.get(SourcePolicy, "manual")
        policy.description_storage = "prohibited"
        # Reads already fail closed before the explicit operator purge.
        db.commit()
    restricted = client.get(f"/applications/{row['id']}").json()
    assert restricted["match"] is None and restricted["snapshots"][0]["restriction"]
    assert not restricted["snapshots"][0]["data"]["description"]
    with application.state.sessions() as db:
        policy = db.get(SourcePolicy, "manual")
        sanitize_policy_history(db, policy)
        db.commit()
        snapshot = db.query(ApplicationSnapshot).one()
        assert snapshot.match is None and not snapshot.data["description"]
    second = prepare(client, job(client, "two"))
    assert second["snapshots"][0]["restriction"]
    assert not second["snapshots"][0]["data"]["description"]


def test_application_notes_events_actions_and_follow_up(client, application):
    ready(client)
    row = applied(client, prepare(client))
    path = f"/applications/{row['id']}"
    row = client.put(
        path + "/action",
        json=dict(
            expected_revision=row["revision"],
            next_action="Review qualifications",
            next_action_date="2026-11-01",
            follow_up_days=7,
        ),
        headers=csrf(client),
    ).json()
    assert row["due_date"] == "2026-11-01"
    assert (
        client.post(
            path + "/events", json=dict(kind="ASSESSMENT", text="Online test"), headers=csrf(client)
        ).status_code
        == 422
    )
    for body in (
        dict(kind="NOTE", text="Spoke with team"),
        dict(kind="ASSESSMENT", text="Online test", due_date="2026-10-30"),
    ):
        response = client.post(path + "/events", json=body, headers=csrf(client))
        assert response.status_code == 201, response.text
        row = response.json()
    assert len(row["events"]) == 2 and row["due_date"] == "2026-10-30"
    event = row["events"][1]
    row = client.patch(path + f"/events/{event['id']}", headers=csrf(client)).json()
    assert row["due_date"] == "2026-11-01"
    row = client.patch(path + f"/events/{event['id']}?completed=false", headers=csrf(client)).json()
    assert row["due_date"] == "2026-10-30"
    with application.state.sessions() as db:
        stored = db.get(Application, row["id"])
        stored.updated_at = (datetime.now().astimezone() - timedelta(days=8)).isoformat()
        db.commit()
    assert client.get(path).json()["follow_up_suggestion"] == "Consider following up"
    # Recording activity resets deterministic follow-up; there is no outbound send.
    client.post(path + "/events", json=dict(kind="NOTE", text="Followed up myself"), headers=csrf(client))
    assert client.get(path).json()["follow_up_suggestion"] is None
    assert (
        client.put(
            path + "/action", json=dict(expected_revision=1, next_action="stale"), headers=csrf(client)
        ).status_code
        == 409
    )


def test_application_owner_csrf_resume_event_and_export_isolation(client, application):
    ready(client)
    row = prepare(client)
    path = f"/applications/{row['id']}"
    client.post(path + "/events", json=dict(kind="NOTE", text="Private"), headers=csrf(client))
    event = client.get(path).json()["events"][0]["id"]
    assert (
        client.post(path + "/status", json=dict(expected_revision=2, status="WITHDRAWN")).status_code == 403
    )
    assert client.post("/applications", json=dict(job_id=row["job_id"])).status_code == 403
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert confirm(other, upload(other).json()).status_code == 200
        assert other.get("/applications").json()["total"] == 0
        assert "Python Engineer" not in other.get("/applications/export.csv").text
        assert other.get(path).status_code == 404
        assert (
            other.post("/applications", json=dict(job_id=row["job_id"]), headers=csrf(other)).status_code
            == 404
        )
        assert (
            other.post(
                path + "/status", json=dict(expected_revision=2, status="WITHDRAWN"), headers=csrf(other)
            ).status_code
            == 404
        )
        assert (
            other.put(
                path + "/action", json=dict(expected_revision=2, next_action="hijack"), headers=csrf(other)
            ).status_code
            == 404
        )
        assert (
            other.post(
                path + "/events", json=dict(kind="NOTE", text="hijack"), headers=csrf(other)
            ).status_code
            == 404
        )
        assert other.patch(path + f"/events/{event}", headers=csrf(other)).status_code == 404
        alien_resume = other.get("/resumes").json()[0]["id"]
        current = client.get(path).json()
        assert (
            move(client, current, "APPLIED", confirm_applied=True, resume_version_id=alien_resume).status_code
            == 422
        )
        other_row = prepare(other)
        assert (
            other.patch(f"/applications/{other_row['id']}/events/{event}", headers=csrf(other)).status_code
            == 404
        )


def test_application_export_escapes_formulas_and_contains_no_identifiers(client):
    ready(client)
    posting = client.post(
        "/jobs/manual",
        json=dict(title="=HYPERLINK(bad)", company="Example", application_url="https://example.com/csv"),
        headers=csrf(client),
    )
    assert posting.status_code == 201
    row = prepare(client, posting.json()["id"])
    result = client.get("/applications/export.csv")
    assert result.status_code == 200 and "attachment" in result.headers["content-disposition"]
    records = list(csv.DictReader(io.StringIO(result.text)))
    assert records[0]["title"] == "'=HYPERLINK(bad)"
    assert row["id"] not in result.text and row["job_id"] not in result.text
    assert "application_url" in records[0]
    assert records[0]["source_attribution"] and records[0]["source_urls"]
