import httpx
from fastapi.testclient import TestClient

from operation import OperationClient
from operation.app import app

client = TestClient(app)


def test_numeric_op():
    response = client.post("/v1/operation/numeric_op", json={"a": 2, "b": 3})
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_numeric_op_floats_and_negatives():
    response = client.post("/v1/operation/numeric_op", json={"a": -1.5, "b": 4.25})
    assert response.json() == {"result": 2.75}


def test_numeric_op_missing_input_returns_422():
    response = client.post("/v1/operation/numeric_op", json={"a": 2})
    assert response.status_code == 422


def test_numeric_op_non_numeric_input_returns_422():
    response = client.post("/v1/operation/numeric_op", json={"a": "x", "b": 3})
    assert response.status_code == 422


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_client_numeric_op():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/operation/numeric_op"
        return httpx.Response(200, json={"result": 5.0})

    with OperationClient("http://operation", transport=httpx.MockTransport(handler)) as op:
        assert op.numeric_op(2, 3).result == 5.0
