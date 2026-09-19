import pytest
from edge_gateway.order_local_api import attach_order_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient
from restaurant_os.operations import BusinessError


class Service:
    manifest = {
        "organization_id": "org",
        "branch_id": "branch",
        "device_id": "device",
        "bundle_id": "bundle",
        "lease_epoch": 1,
    }
    bundle = {"hash": "hash"}

    def authorize(self, token, now):
        if token != "valid":
            raise BusinessError("offline_order_grant_invalid", "Invalid grant")
        return {"actor_id": "actor", "branch_id": "branch", "capabilities": ["orders.create"]}

    def execute(self, token, command_type, payload, key, **kwargs):
        assert payload == {"lines": [{"product_id": "product", "quantity": 1}]}
        assert command_type == "create"
        return {"id": "order", "_offline": {"status": "PENDING_SYNC"}}


@pytest.fixture
def client():
    app = FastAPI()
    attach_order_routes(app, Service())
    return TestClient(app)


def test_local_order_rejects_cloud_bearer_and_cross_branch(client):
    path = "/api/v1/local/order-api/orders"
    payload = {"branch_id": "branch", "lines": [{"product_id": "product", "quantity": 1}]}
    assert (
        client.post(path, json=payload, headers={"Authorization": "Bearer valid"}).status_code
        == 401
    )
    headers = {"Authorization": "Offline valid", "Idempotency-Key": "command-123456"}
    response = client.post(path, json={**payload, "branch_id": "other"}, headers=headers)
    assert response.status_code == 403
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["_offline"]["status"] == "PENDING_SYNC"


def test_missing_key_and_unknown_operation_are_rejected(client):
    headers = {"Authorization": "Offline valid"}
    assert (
        client.post("/api/v1/local/order-api/orders", json={}, headers=headers).status_code == 422
    )
    assert (
        client.post("/api/v1/local/order-api/cash/shifts", json={}, headers=headers).status_code
        == 404
    )
