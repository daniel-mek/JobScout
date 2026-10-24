import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from apps.api.applyos.match_models import JobMatch
from apps.api.tests.conftest import confirm, csrf, signup, upload
from packages.matching.engine import MATCH_WEIGHTS, PRIORITY_WEIGHTS, calculate, extract
from packages.matching.qualifications import certification_fit, education_fit, professional_months


def test_months_merge_overlaps_exclude_projects_and_ambiguous_dates():
    at = datetime(2026, 10, 1, tzinfo=UTC)
    profile = dict(
        experience=[dict(dates="2024-01 to 2025-01"), dict(dates="2024-06 to 2026-01")],
        projects=[dict(dates="2000-01 to 2026-01")],
    )
    assert professional_months(profile, at) == 24
    profile["experience"].append(dict(dates="2025-02 to present", title="Intern"))
    assert professional_months(profile, at) is None
    for dates in ("2020–2026", "2026-14 to present", "2027-01 to 2027-10", "2026-10 to 2025-01"):
        assert professional_months(dict(experience=[dict(dates=dates)]), at) is None


def test_degree_subject_and_certifications_need_confirmed_evidence():
    requirement = [
        dict(kind="education", obligation="required", evidence="Bachelor degree in computer science required")
    ]
    assert education_fit(requirement, dict(education=[dict(degree="Bachelor of Computer Science")]))[0] == 100
    assert education_fit(requirement, dict(education=[dict(degree="Bachelor of History")]))[0] == 0
    requirement[0]["evidence"] += " or equivalent experience"
    assert education_fit(requirement, {})[0] == 50
    certificates = [dict(kind="certification", obligation="required", evidence="CCNA certification required")]
    assert certification_fit(certificates, {}) == (0, ["CCNA"])
    assert certification_fit(certificates, dict(certifications=[dict(name="CCNA")])) == (100, [])


def test_sections_and_negations_remain_conservative():
    extracted = extract(
        dict(
            description="Requirements\nPython\nMinimum 3 years experience\nPreferred qualifications\nAWS\n5 years experience\nResponsibilities\nJava"
        )
    )
    assert extracted["experience_min"] == 3
    assert next(s for s in extracted["skills"] if s["name"] == "python")["obligation"] == "required"
    assert next(s for s in extracted["skills"] if s["name"] == "aws")["obligation"] == "preferred"
    assert extract(dict(description="Five years experience not required"))["experience_min"] is None
    assert extract(dict(description="Up to 5 years experience required"))["experience_min"] == 0
    assert (
        calculate(dict(description="No security clearance required"), {}, {}, dict(allow_clearance=False))[
            "eligibility"
        ]
        != "INELIGIBLE"
    )


@pytest.mark.parametrize(
    "data,hard,expected",
    [
        (dict(country="USA", description="Python required"), dict(countries=["US"]), "ELIGIBLE"),
        (dict(description="Must be authorized to work"), dict(authorized_to_work=False), "INELIGIBLE"),
        (dict(description="US citizens only required"), dict(authorized_to_work=True), "UNKNOWN"),
        (dict(description="Must relocate to New York"), dict(allow_relocation=False), "INELIGIBLE"),
        (dict(description="Relocation assistance offered"), dict(allow_relocation=False), "UNKNOWN"),
        (dict(description="Python required"), dict(needs_sponsorship=True), "UNKNOWN"),
    ],
)
def test_geographic_authorization_and_relocation(data, hard, expected):
    assert calculate(data, {}, {}, hard)["eligibility"] == expected


def test_salary_period_currency_and_preference_are_not_hard_filters():
    data = dict(salary_min=60000, salary_max=70000, salary_period="1 YEAR", currency="USD")
    preferences = dict(minimum_salary=80000, currency="USD")
    result = calculate(data, {}, preferences, {})
    assert result["priority_components"]["salary"] == 0
    assert result["eligibility"] != "INELIGIBLE"
    for period, currency in (("hour", "USD"), ("1 YEAR", "CAD"), (None, "USD")):
        assert (
            calculate({**data, "salary_period": period, "currency": currency}, {}, preferences, {})[
                "priority_components"
            ]["salary"]
            == 50
        )


def ready_job(client):
    signup(client)
    assert confirm(client, upload(client).json()).status_code == 200
    return client.post(
        "/jobs/manual",
        headers=csrf(client),
        json=dict(
            title="Junior Python Engineer",
            company="Example",
            application_url="https://example.com/task",
            description="Python required. Minimum 2 years experience required.",
        ),
    ).json()["id"]


def test_persisted_weights_revision_validation_and_match_invalidation(client):
    key = ready_job(client)
    first = client.post(f"/jobs/{key}/match", headers=csrf(client)).json()
    weights = {**MATCH_WEIGHTS, "skills": 50, "experience": 5}
    body = dict(expected_revision=0, weights=weights, priority_weights=PRIORITY_WEIGHTS)
    assert client.put("/scoring-policy", json=body).status_code == 403
    assert client.put("/scoring-policy", json=body, headers=csrf(client)).status_code == 200
    assert client.put("/scoring-policy", json=body, headers=csrf(client)).status_code == 409
    assert client.get("/scoring-policy").json()["weights"] == weights
    second = client.post(f"/jobs/{key}/match", headers=csrf(client)).json()
    assert first["id"] != second["id"]
    for invalid in (
        {"skills": 100},
        {**weights, "skills": -1},
        {**weights, "skills": 51},
        {**weights, "skills": True},
    ):
        assert (
            client.put(
                "/scoring-policy",
                json={**body, "expected_revision": 1, "weights": invalid},
                headers=csrf(client),
            ).status_code
            == 422
        )


def test_preferences_and_hard_requirements_invalidate_existing_match(client):
    key = ready_job(client)
    url = f"/jobs/{key}/match"
    original = client.post(url, headers=csrf(client)).json()
    assert (
        client.put(
            "/preferences", headers=csrf(client), json=dict(locations=["New York"], companies=["Example"])
        ).status_code
        == 200
    )
    updated = client.post(url, headers=csrf(client)).json()
    assert updated["id"] != original["id"]
    assert (
        client.put("/requirements", headers=csrf(client), json=dict(max_requested_experience=1)).status_code
        == 200
    )
    constrained = client.post(url, headers=csrf(client)).json()
    assert constrained["id"] != updated["id"] and constrained["result"]["eligibility"] == "INELIGIBLE"
    assert constrained["result"]["application_priority"] <= 10


def test_retention_tightening_purges_derived_match_evidence(client, application):
    from apps.api.applyos.jobs_models import SourcePolicy
    from apps.api.applyos.jobs_service import sanitize_policy_history
    from apps.api.applyos.match_models import JobRequirement, JobSkill

    key = ready_job(client)
    assert client.post(f"/jobs/{key}/match", headers=csrf(client)).status_code == 200
    with application.state.sessions() as db:
        assert db.scalar(select(JobMatch).where(JobMatch.job_id == key))
        policy = db.get(SourcePolicy, "manual")
        policy.description_storage = "prohibited"
        sanitize_policy_history(db, policy)
        db.commit()
        for model in (JobMatch, JobRequirement, JobSkill):
            assert db.scalar(select(model).where(model.job_id == key)) is None


def test_worker_reconciliation_is_bounded_and_idempotent(client, application, monkeypatch):
    from apps.worker import matching

    key = ready_job(client)
    monkeypatch.setenv("DATABASE_URL", application.state.config.database_url)
    from apps.api.applyos.config import settings

    settings.cache_clear()
    rows = matching.match_batch(limit=10000)
    assert len(rows) == 1 and rows[0][0] == key
    publish = Mock()
    monkeypatch.setattr(matching.calculate_job, "apply_async", publish)
    assert matching.reconcile.run() == 1
    assert publish.call_args.kwargs["args"][1] == key
    owner = rows[0][1]
    a = matching.calculate_job.run(owner, key)
    assert matching.calculate_job.run(owner, key) == a
    assert matching.calculate_job.run("different-owner", key) is None
    settings.cache_clear()


@pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated test Redis broker; exercised in CI"
)
def test_real_redis_worker_calculates_persisted_job(client, application, tmp_path):
    from apps.worker import matching

    key = ready_job(client)
    owner = client.get("/auth/me").json()["id"]
    queue = "test-matching-" + uuid.uuid4().hex
    environment = {
        **os.environ,
        "DATABASE_URL": application.state.config.database_url,
        "REDIS_URL": os.environ["TEST_REDIS_URL"],
        "ENVIRONMENT": "test",
    }
    matching.app.conf.broker_url = os.environ["TEST_REDIS_URL"]
    with (tmp_path / "worker.log").open("w") as log:
        worker = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "apps.worker.matching:app",
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--loglevel=WARNING",
                "--queues=" + queue,
                "--without-gossip",
                "--without-mingle",
            ],
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            matching.calculate_job.apply_async(args=[owner, key], queue=queue, expires=45)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with application.state.sessions() as db:
                    row = db.scalar(
                        select(JobMatch).where(JobMatch.owner_id == owner, JobMatch.job_id == key)
                    )
                    if row:
                        assert row.result["early_career"] == "EARLY_CAREER"
                        break
                assert worker.poll() is None, "Worker exited unexpectedly; see private test log"
                time.sleep(0.2)
            else:
                pytest.fail("Worker did not persist the queued match within 30 seconds")
        finally:
            worker.terminate()
            worker.wait(timeout=10)
