from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.watchlist_repository import reset_watchlist_repository_singleton


@pytest.fixture
def watchlist_client(tmp_path, monkeypatch):
    db = tmp_path / "wl.db"
    monkeypatch.setenv("TRANQUILYTICS_STATE_DB", str(db))
    reset_watchlist_repository_singleton()
    client = TestClient(create_app())
    yield client
    reset_watchlist_repository_singleton()


def test_watchlist_empty_then_add(watchlist_client: TestClient) -> None:
    r = watchlist_client.get("/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "local"
    assert body["items"] == []

    r2 = watchlist_client.post("/watchlist", json={"symbol": "AAPL"})
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "AAPL"


def test_watchlist_duplicate_409(watchlist_client: TestClient) -> None:
    assert watchlist_client.post("/watchlist", json={"symbol": "MSFT"}).status_code == 200
    r = watchlist_client.post("/watchlist", json={"symbol": "MSFT"})
    assert r.status_code == 409


def test_watchlist_delete(watchlist_client: TestClient) -> None:
    watchlist_client.post("/watchlist", json={"symbol": "NVDA"})
    r = watchlist_client.delete("/watchlist/NVDA")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_watchlist_delete_missing_404(watchlist_client: TestClient) -> None:
    r = watchlist_client.delete("/watchlist/ZZZZ")
    assert r.status_code == 404


def test_watchlist_user_partition_header(watchlist_client: TestClient) -> None:
    h = {"X-User-Id": "alice"}
    watchlist_client.post("/watchlist", json={"symbol": "IBM"}, headers=h)
    assert watchlist_client.get("/watchlist").json()["items"] == []
    body = watchlist_client.get("/watchlist", headers=h).json()
    assert len(body["items"]) == 1
    assert body["items"][0]["symbol"] == "IBM"


def test_watchlist_invalid_symbol(watchlist_client: TestClient) -> None:
    r = watchlist_client.post("/watchlist", json={"symbol": "!!!"})
    assert r.status_code == 400
