"""Tests for content-hashed static asset cache-busting."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import helpers


def test_asset_version_is_short_hex_for_real_file():
    ver = helpers.asset_version("base.css")
    assert isinstance(ver, str)
    assert 6 <= len(ver) <= 16
    int(ver, 16)  # hex


def test_asset_version_stable_for_same_file():
    assert helpers.asset_version("base.css") == helpers.asset_version("base.css")


def test_asset_version_changes_with_content(tmp_path, monkeypatch):
    monkeypatch.setattr(helpers, "STATIC_DIR", str(tmp_path))
    helpers._asset_version_cache.clear()
    f = tmp_path / "x.css"

    f.write_text("a { color: red; }")
    os.utime(f, (1000, 1000))
    v1 = helpers.asset_version("x.css")

    f.write_text("a { color: blue; }")
    os.utime(f, (2000, 2000))
    v2 = helpers.asset_version("x.css")

    assert v1 != v2


def test_asset_version_missing_file_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(helpers, "STATIC_DIR", str(tmp_path))
    helpers._asset_version_cache.clear()
    # must not raise, returns some fallback token
    assert helpers.asset_version("nope.css")


def test_static_url_embeds_version():
    url = helpers.static_url("components.css")
    assert url == f"/static/components.css?v={helpers.asset_version('components.css')}"


# ------------------------------------------------------------------
# Rendered pages carry the content hash, not the release version
# ------------------------------------------------------------------

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_page_links_assets_with_content_hash(client):
    html = client.get("/").text
    assert f"/static/components.css?v={helpers.asset_version('components.css')}" in html
    assert f"/static/base.css?v={helpers.asset_version('base.css')}" in html
    # the brittle release-version querystring is gone
    assert "components.css?v=Version" not in html
