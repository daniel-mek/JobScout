from fastapi.testclient import TestClient

from apps.api.tests.conftest import csrf, signup
from apps.api.tests.test_phase4 import job


def test_setup_counts_catalog_and_scoped_sources(client, application):
    signup(client)
    assert client.get("/discovery-status").json() == dict(jobs=0, connected_sources=0, ready_sources=0)
    job(client)
    client.post(
        "/sources", json=dict(provider="lever", board="example", company="Example"), headers=csrf(client)
    )
    assert client.get("/discovery-status").json() == dict(jobs=1, connected_sources=1, ready_sources=0)
    with TestClient(application, headers={"origin": "http://localhost:3000"}) as other:
        assert other.get("/discovery-status").status_code == 401
        signup(other, "other@example.com")
        assert other.get("/discovery-status").json() == dict(jobs=0, connected_sources=0, ready_sources=0)
