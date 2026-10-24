from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.tests.conftest import confirm, csrf, signup, upload
from packages.matching.engine import calculate, extract, weighted


@pytest.mark.parametrize(
    "years,label",
    [(0, "TRUE_ENTRY_LEVEL"), (1, "EARLY_CAREER"), (3, "REASONABLE_REACH"), (4, "MID_LEVEL"), (5, "SENIOR")],
)
def test_description_overrides_junior_title(years, label):
    result = extract(
        dict(
            title="Junior Engineer",
            description=f"Minimum {years}+ years of professional experience required.",
        )
    )
    assert result["early_career"] == label
    assert result["requirements"][0]["evidence"]


def test_required_preferred_aliases_and_unknowns():
    data = dict(
        title="Engineer", description="Python and JS required.\nPostgres preferred.\nAWS is used here."
    )
    rows = extract(data)["skills"]
    assert any(r["name"] == "javascript" and r["obligation"] == "required" for r in rows)
    assert any(r["name"] == "postgresql" and r["obligation"] == "preferred" for r in rows)
    assert any(r["name"] == "aws" and r["obligation"] == "uncertain" for r in rows)
    result = calculate({}, {}, {}, {})
    assert result["eligibility"] == "UNKNOWN"
    assert result["early_career"] == "UNKNOWN"


def test_freshness_cannot_override_hard_failure_and_projects_not_years():
    data = dict(
        title="Entry-level Engineer",
        description="Minimum 5 years experience required.",
        posted_at="2026-10-23T00:00:00Z",
    )
    profile = dict(projects=[dict(description="Ten years Python experience")])
    result = calculate(
        data, profile, {}, dict(max_requested_experience=2), at=datetime(2026, 10, 23, tzinfo=UTC)
    )
    assert result["eligibility"] == "INELIGIBLE"
    assert result["application_priority"] <= 10
    assert result["recommendation"] == "SKIP"
    assert result["components"]["experience"] == 50


def test_evidence_strength_and_missing_preferred_are_distinct():
    data = dict(description="Python required.\nAWS preferred.")
    bare = calculate(data, dict(skills=[dict(name="Python")]), {}, {})
    linked = calculate(
        data,
        dict(
            skills=[dict(name="Python", evidence="Built service", evidence_ref="project:0")],
            projects=[dict(description="Python service")],
        ),
        {},
        {},
    )
    assert linked["resume_match"] > bare["resume_match"]
    assert "preferred" in linked["explanation"]["missing_qualifications"][0]
    assert linked["explanation"]["strong_matches"]


@pytest.mark.parametrize(
    "data,hard",
    [
        (dict(employment_type="CONTRACT"), dict(allow_contract=False)),
        (dict(country="CA"), dict(countries=["US"])),
        (dict(description="Active security clearance required"), dict(allow_clearance=False)),
        (
            dict(description="No sponsorship. Must have work authorization required"),
            dict(needs_sponsorship=True),
        ),
    ],
)
def test_hard_conflicts(data, hard):
    assert calculate(data, {}, {}, hard)["eligibility"] == "INELIGIBLE"


def test_weight_validation():
    assert weighted(dict(a=100, b=0), dict(a=3, b=1)) == 75
    with pytest.raises(ValueError):
        weighted(dict(a=100), dict(a=-1))


def test_match_owner_csrf_versions_and_input_invalidation(client, application):
    signup(client)
    resume = upload(client).json()
    assert confirm(client, resume).status_code == 200
    job = client.post(
        "/jobs/manual",
        headers=csrf(client),
        json=dict(
            title="Junior Python Engineer",
            company="Example",
            application_url="https://example.com/job",
            description="Python required. Minimum 2 years experience required.",
        ),
    ).json()
    url = f"/jobs/{job['id']}/match"
    assert client.post(url).status_code == 403
    first = client.post(url, headers=csrf(client))
    assert first.status_code == 200, first.text
    assert client.post(url, headers=csrf(client)).json()["id"] == first.json()["id"]
    client.post(
        "/jobs/manual",
        headers=csrf(client),
        json=dict(
            title="Junior Python Engineer",
            company="Example",
            application_url="https://example.com/job",
            description="Python required. Minimum 5 years experience required.",
        ),
    )
    second = client.post(url, headers=csrf(client)).json()
    assert second["id"] != first.json()["id"]
    assert second["result"]["early_career"] == "SENIOR"
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        signup(other, "other@example.com")
        assert other.post(url, headers=csrf(other)).status_code == 404
