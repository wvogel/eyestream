"""API integration tests — smoke tests for all endpoints.
Requires a running PostgreSQL with the test database.
Run with: pytest tests/test_api.py -v
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from unittest import mock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client with mocked DB pool."""
    # Mock the pool before importing the app
    mock_pool = mock.MagicMock()
    mock_conn = mock.MagicMock()
    mock_cursor = mock.MagicMock()

    # Default fetchone/fetchall returns
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.execute.return_value = mock_cursor
    mock_conn.execute.return_value = mock_cursor
    mock_conn.__enter__ = mock.MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = mock.MagicMock(return_value=False)
    mock_pool.connection.return_value = mock_conn

    import db
    db.pool = mock_pool

    from main import app
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ------------------------------------------------------------------
# Pages (HTML responses)
# ------------------------------------------------------------------

def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_upload_page(client):
    r = client.get("/upload")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_settings_page(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_stats_page(client):
    r = client.get("/stats")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_activity_page(client):
    r = client.get("/activity")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# ------------------------------------------------------------------
# API Endpoints (JSON responses)
# ------------------------------------------------------------------

def test_search_suggest_empty(client):
    r = client.get("/search/suggest?q=")
    assert r.status_code == 200
    assert r.json()["suggestions"] == []


def test_search_suggest_too_short(client):
    r = client.get("/search/suggest?q=a")
    assert r.status_code == 200
    assert r.json()["suggestions"] == []


def test_search_suggest_valid(client):
    r = client.get("/search/suggest?q=test")
    assert r.status_code == 200
    assert "suggestions" in r.json()


def test_video_progress_not_found(client):
    r = client.get("/video/999999/progress")
    assert r.status_code == 404


def test_referers_endpoint(client):
    r = client.get("/referers")
    assert r.status_code == 200
    data = r.json()
    assert "referers" in data


def test_worker_status(client):
    r = client.get("/worker/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


def test_settings_stats(client):
    r = client.get("/settings/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_videos" in data
    assert "disk" in data
    assert "worker" in data


# ------------------------------------------------------------------
# Mutation Endpoints (require valid data)
# ------------------------------------------------------------------

def test_create_category_empty_name(client):
    r = client.post("/categories", json={"name": ""})
    assert r.status_code == 400


def test_create_category_too_long(client):
    r = client.post("/categories", json={"name": "x" * 200})
    assert r.status_code == 400


def test_rename_title_empty(client):
    r = client.post("/video/1/title", json={"title": ""})
    assert r.status_code == 400


def test_rename_title_too_long(client):
    r = client.post("/video/1/title", json={"title": "x" * 300})
    assert r.status_code == 400


def test_save_note_too_long(client):
    r = client.post("/video/1/note", json={"note": "x" * 3000})
    assert r.status_code == 400


def test_set_poster_missing_seconds(client):
    r = client.post("/video/1/poster", json={})
    assert r.status_code == 400


def test_set_poster_invalid_seconds(client):
    r = client.post("/video/1/poster", json={"seconds": "abc"})
    assert r.status_code == 400


def test_referer_ignore_empty(client):
    r = client.post("/referer-ignore", json={"pattern": ""})
    assert r.status_code == 400


def test_referer_ignore_too_long(client):
    r = client.post("/referer-ignore", json={"pattern": "x" * 300})
    assert r.status_code == 400


def test_update_category_empty(client):
    r = client.post("/video/1/category", json={"category_id": None})
    # Should work (removes category) or return 404 (video not found)
    assert r.status_code in (200, 404)


# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------

def test_large_id_rejected(client):
    r = client.get("/video/99999999999999/progress")
    assert r.status_code == 400


def test_negative_id_path(client):
    r = client.get("/video/-1/progress")
    # FastAPI rejects non-matching path (negative not matching \d+)
    assert r.status_code in (400, 404, 422)


def test_file_proxy_path_traversal(client):
    r = client.get("/video/1/file/../../etc/passwd")
    assert r.status_code in (400, 404)


def test_file_proxy_absolute_path(client):
    r = client.get("/video/1/file//etc/passwd")
    assert r.status_code in (400, 404)


# ------------------------------------------------------------------
# Static files
# ------------------------------------------------------------------

def test_static_css(client):
    r = client.get("/static/base.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]


def test_static_js(client):
    r = client.get("/static/app.js")
    assert r.status_code == 200


def test_static_css(client):
    r = client.get("/static/base.css")
    assert r.status_code == 200


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------

def test_pagination_default(client):
    r = client.get("/")
    assert r.status_code == 200


def test_pagination_per_page(client):
    r = client.get("/?per_page=20")
    assert r.status_code == 200


def test_pagination_all(client):
    r = client.get("/?per_page=0")
    assert r.status_code == 200


def test_pagination_invalid_per_page(client):
    r = client.get("/?per_page=999")
    assert r.status_code == 200  # falls back to default


def test_pagination_with_search(client):
    r = client.get("/?q=test&cat=0")
    assert r.status_code == 200


# ------------------------------------------------------------------
# Monitoring
# ------------------------------------------------------------------

def test_health_detailed(client):
    r = client.get("/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "version" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "upload_dir" in data["checks"]
    assert "hls_dir" in data["checks"]
    assert "worker" in data["checks"]
    assert "disk" in data["checks"]
    assert "videos" in data["checks"]


def test_health_detailed_has_video_counts(client):
    r = client.get("/health/detailed")
    data = r.json()
    videos = data["checks"].get("videos", {})
    # Should have count fields (may be 0 with mock)
    assert isinstance(videos, dict)
