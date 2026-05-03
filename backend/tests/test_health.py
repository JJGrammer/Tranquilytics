from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok() -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_root_is_not_404_in_dev() -> None:
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "Tranquilytics API"
    assert body["docs"] == "/docs"

