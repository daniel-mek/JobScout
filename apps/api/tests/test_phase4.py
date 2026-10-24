from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.applyos.discovery import notify
from apps.api.applyos.discovery_models import Notification
from apps.api.applyos.match_models import JobMatch
from apps.api.tests.conftest import confirm, csrf, signup, upload
from packages.matching.engine import VERSION


def job(client, suffix="one", **extra):
    result = client.post(
        "/jobs/manual",
        json=dict(
            title="Python Engineer " + suffix,
            company="Example",
            application_url="https://example.com/" + suffix,
            location="New York",
            country="US",
            arrangement="REMOTE",
            employment_type="Full-time",
            description="Python required.",
            **extra,
        ),
        headers=csrf(client),
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


def ready(client):
    signup(client)
    assert confirm(client, upload(client).json()).status_code == 200


def test_discovery_order_pagination_filters_and_unknown_scores(client, application):
    ready(client)
    first, second = job(client), job(client, "two")
    owner = client.get("/auth/me").json()["id"]
    with application.state.sessions() as db:
        for key, score in ((first, 20), (second, 80)):
            db.add(
                JobMatch(
                    owner_id=owner,
                    job_id=key,
                    input_hash=key,
                    profile_revision=1,
                    job_revision=1,
                    algorithm_version=VERSION,
                    result=dict(
                        application_priority=score,
                        resume_match=score,
                        early_career="EARLY_CAREER",
                        eligibility="UNKNOWN",
                        recommendation="STRONG_APPLY" if score == 80 else "LONG_SHOT",
                    ),
                )
            )
        db.commit()
    result = client.get("/discover?limit=1").json()
    assert result["total"] == 2 and result["items"][0]["id"] == second
    assert client.get("/discover?limit=1&offset=1").json()["items"][0]["id"] == first
    assert client.get("/discover?min_match=70&arrangement=REMOTE").json()["total"] == 1
    assert client.get("/discover?company=Other").json()["total"] == 0
    assert client.get("/discover?title=%25").json()["total"] == 0  # SQL wildcards are literal.
    assert client.get("/discover?min_salary=1").json()["total"] == 0
    assert client.get("/discover?source=manual").json()["total"] == 2
    assert client.get("/discover?limit=1000").status_code == 422


def test_save_notes_deadline_feedback_unsave_preserves_job(client):
    ready(client)
    key = job(client)
    url = f"/jobs/{key}/review"
    assert client.put(url, json=dict(saved=True)).status_code == 403
    row = client.put(
        url,
        json=dict(saved=True, notes="Review original requirements", deadline="2026-11-01"),
        headers=csrf(client),
    ).json()
    assert row["saved"] and row["reviewed"] and row["job_revision"] == 1 and row["saved_at"]
    assert client.get("/discover?saved=true").json()["total"] == 1
    client.put(url, json=dict(feedback="NOT_INTERESTED", reason="TOO_SENIOR"), headers=csrf(client))
    assert client.get("/discover").json()["total"] == 0
    assert client.get("/discover?saved=true").json()["total"] == 1
    client.put(url, json=dict(saved=False, feedback="CLEAR"), headers=csrf(client))
    assert client.get("/discover?saved=true").json()["total"] == 0
    assert client.get("/jobs/" + key).status_code == 200
    assert client.get(url).json()["notes"] == "Review original requirements"
    assert client.put(url, json=dict(deadline="invalid"), headers=csrf(client)).status_code == 422


def test_review_and_notifications_are_owner_scoped(client, application):
    ready(client)
    key = job(client)
    owner = client.get("/auth/me").json()["id"]
    with application.state.sessions() as db:
        notify(db, owner, "one", "NEW_HIGH_MATCH_JOB", key)
        notify(db, owner, "one", "NEW_HIGH_MATCH_JOB", key)
        db.commit()
    items = client.get("/notifications").json()
    assert len(items) == 1
    identifier = items[0]["id"]
    assert client.patch(f"/notifications/{identifier}", headers=csrf(client)).json()["read"]
    assert client.get("/notifications?unread=true").json() == []
    assert client.patch(f"/notifications/{identifier}?read=false", headers=csrf(client)).status_code == 200
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert other.get("/discover").json()["total"] == 0
        assert other.get("/notifications").json() == []
        assert other.get(f"/jobs/{key}/review").status_code == 404
        assert other.put(f"/jobs/{key}/review", json=dict(saved=True), headers=csrf(other)).status_code == 404
        assert other.patch(f"/notifications/{identifier}", headers=csrf(other)).status_code == 404


def test_preferences_suppress_notifications_and_brief_has_no_filler(client, application):
    ready(client)
    assert client.get("/daily-brief").json()["sections"] == dict(
        excellent=[], strong_apply=[], fresh_reach=[], needs_review=[]
    )
    assert client.put("/notification-preferences", json=["UNKNOWN"], headers=csrf(client)).status_code == 422
    assert (
        client.put("/notification-preferences", json=["FRESH_OPPORTUNITY"], headers=csrf(client)).status_code
        == 200
    )
    owner = client.get("/auth/me").json()["id"]
    with application.state.sessions() as db:
        notify(db, owner, "fresh", "FRESH_OPPORTUNITY")
        db.commit()
        assert db.scalar(select(Notification)) is None
    key = job(client)
    assert client.get("/daily-brief").json()["sections"]["needs_review"][0]["id"] == key


def test_saved_search_preserves_validated_filters_and_ownership(client, application):
    ready(client)
    body = dict(
        name="Remote Python",
        filters=dict(title="Python", arrangement="REMOTE", min_match="70", reviewed="false", offset=25),
    )
    result = client.post("/discovery-searches", json=body, headers=csrf(client))
    assert result.status_code == 201, result.text
    saved = result.json()
    assert saved["filters"]["min_match"] == 70 and saved["filters"]["reviewed"] is False
    assert "offset" not in saved["filters"]
    assert len(client.get("/discovery-searches").json()) == 1
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert other.get("/discovery-searches").json() == []
        assert other.delete("/discovery-searches/" + saved["id"], headers=csrf(other)).status_code == 404
    assert client.delete("/discovery-searches/" + saved["id"], headers=csrf(client)).json()["deleted"]
