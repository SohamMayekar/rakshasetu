from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_demo_routes_answer_on_the_local_listener():
    r = client.get("/v1/demo/status", headers={"X-RS-Listener": "local"})
    assert r.status_code == 200
    assert r.json()["listener"] == "local"


def test_demo_routes_refused_on_the_public_listener():
    assert client.get("/v1/demo/status", headers={"X-RS-Listener": "public"}).status_code == 403


def test_demo_routes_refused_without_a_listener_header():
    assert client.get("/v1/demo/status").status_code == 403


def test_demo_routes_refused_through_the_tunnel_even_if_local():
    r = client.get("/v1/demo/status", headers={"X-RS-Listener": "local", "CF-Connecting-IP": "203.0.113.9"})
    assert r.status_code == 403
