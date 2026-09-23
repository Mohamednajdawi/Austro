"""Dependency/API smoke tests, not security-control acceptance evidence."""

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.main import create_app


def test_health_is_explicitly_scaffold_only():
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "synthetic-demo"}


def test_readiness_does_not_claim_a_working_agent_or_production():
    with TestClient(create_app()) as client:
        response = client.get("/readiness")
    assert response.status_code == 503
    assert response.json() == {
        "implementation_can_start": True,
        "agent_workflow_ready": False,
        "synthetic_workflow_ready": True,
        "production_ready": False,
        "stage": "read-and-draft",
    }


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/api/execute"])
def test_unimplemented_or_external_asset_interfaces_are_not_exposed(path):
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/health", "/readiness"])
def test_metadata_does_not_accept_writes(path):
    with TestClient(create_app()) as client:
        assert client.post(path, json={"approved": True}).status_code == 405
