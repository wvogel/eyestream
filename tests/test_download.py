"""Tests for the video download feature (original + per-quality MP4)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import subprocess

import pytest

import helpers


# ------------------------------------------------------------------
# Test fixtures: generate a tiny real HLS rendition with ffmpeg
# ------------------------------------------------------------------

def _make_hls_rendition(dir_path: str, quality: str = "720p", duration: int = 1):
    """Create a minimal valid fMP4 HLS rendition (<quality>.m3u8 + segments)."""
    os.makedirs(dir_path, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=15",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2",
            "-hls_time", "1", "-hls_playlist_type", "vod", "-hls_segment_type", "fmp4",
            "-hls_fmp4_init_filename", f"init_{quality}.mp4",
            "-hls_flags", "independent_segments", "-hls_list_size", "0",
            "-hls_segment_filename", os.path.join(dir_path, f"{quality}_%05d.m4s"),
            os.path.join(dir_path, f"{quality}.m3u8"),
        ],
        capture_output=True, check=True, timeout=60,
    )
    with open(os.path.join(dir_path, "master.m3u8"), "w", encoding="utf-8") as f:
        f.write(
            "#EXTM3U\n#EXT-X-VERSION:7\n"
            '#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=320x240,'
            'CODECS="avc1.42c015,mp4a.40.2"\n'
            f"{quality}.m3u8\n"
        )


def _ffprobe_streams(path: str) -> set:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, timeout=30,
    )
    return set(out.stdout.split())


# ------------------------------------------------------------------
# build_download_filename
# ------------------------------------------------------------------

def test_build_download_filename_appends_extension():
    assert helpers.build_download_filename("My Video", ".mp4") == "My Video.mp4"


def test_build_download_filename_keeps_unicode_and_spaces():
    assert helpers.build_download_filename("Grüße 2024", ".mp4") == "Grüße 2024.mp4"


def test_build_download_filename_strips_path_separators():
    assert helpers.build_download_filename("a/b\\c", ".mp4") == "a_b_c.mp4"


def test_build_download_filename_strips_control_chars():
    assert helpers.build_download_filename("line1\nline2", ".mp4") == "line1_line2.mp4"


def test_build_download_filename_empty_falls_back():
    assert helpers.build_download_filename("", ".mp4") == "video.mp4"


def test_build_download_filename_whitespace_only_falls_back():
    assert helpers.build_download_filename("   ", ".mp4") == "video.mp4"


def test_build_download_filename_none_falls_back():
    assert helpers.build_download_filename(None, ".mkv") == "video.mkv"


# ------------------------------------------------------------------
# remux_rendition_to_mp4
# ------------------------------------------------------------------

def test_remux_produces_playable_mp4(tmp_path):
    hls_dir = str(tmp_path / "hls")
    _make_hls_rendition(hls_dir, "720p")
    out = str(tmp_path / "out.mp4")

    helpers.remux_rendition_to_mp4(os.path.join(hls_dir, "720p.m3u8"), out)

    assert os.path.isfile(out)
    assert os.path.getsize(out) > 0
    # Losslessly remuxed: both the video and audio stream survive
    assert _ffprobe_streams(out) == {"video", "audio"}


def test_remux_output_is_faststart(tmp_path):
    hls_dir = str(tmp_path / "hls")
    _make_hls_rendition(hls_dir, "720p")
    out = str(tmp_path / "out.mp4")

    helpers.remux_rendition_to_mp4(os.path.join(hls_dir, "720p.m3u8"), out)

    # faststart moves the moov atom ahead of the mdat payload, so the player
    # has the index before the media finishes downloading.
    data = open(out, "rb").read()
    assert b"moov" in data and b"mdat" in data
    assert data.index(b"moov") < data.index(b"mdat")


def test_remux_missing_input_raises(tmp_path):
    out = str(tmp_path / "out.mp4")
    with pytest.raises(RuntimeError):
        helpers.remux_rendition_to_mp4(str(tmp_path / "nope.m3u8"), out)


# ------------------------------------------------------------------
# Download routes (integration against the real test DB + disk)
# ------------------------------------------------------------------

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _insert_video(orig_name, stored_name, status="ready"):
    import db
    with db.pool.connection() as c:
        row = c.execute(
            "INSERT INTO videos (orig_name, stored_name, status, progress) "
            "VALUES (%s, %s, %s, 100) RETURNING id",
            (orig_name, stored_name, status),
        ).fetchone()
    return row["id"]


def _delete_video(vid):
    import db
    with db.pool.connection() as c:
        c.execute("DELETE FROM videos WHERE id=%s", (vid,))


@pytest.fixture
def original_video(client):
    """A video whose original upload file exists on disk."""
    stored = "testclip_orig.mp4"
    path = os.path.join(helpers.UPLOAD_DIR, stored)
    with open(path, "wb") as f:
        f.write(b"ORIGINAL-BYTES-1234567890")
    vid = _insert_video("Mein Clip", stored, status="ready")
    yield {"id": vid, "stored": stored, "path": path, "bytes": b"ORIGINAL-BYTES-1234567890"}
    _delete_video(vid)
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def ready_video(client):
    """A ready video with a real HLS 720p rendition on disk."""
    vid = _insert_video("Mein Clip", "testclip_hls.mp4", status="ready")
    hls_dir = os.path.join(helpers.HLS_DIR, str(vid))
    _make_hls_rendition(hls_dir, "720p")
    yield {"id": vid, "hls_dir": hls_dir}
    _delete_video(vid)
    import shutil
    shutil.rmtree(hls_dir, ignore_errors=True)


# ---- original ----

def test_download_original_video_not_found(client):
    r = client.get("/video/999999/download/original")
    assert r.status_code == 404


def test_download_original_file_missing(client):
    vid = _insert_video("Ghost", "does_not_exist_on_disk.mp4", status="ready")
    try:
        r = client.get(f"/video/{vid}/download/original")
        assert r.status_code == 404
    finally:
        _delete_video(vid)


def test_download_original_returns_file_as_attachment(client, original_video):
    from urllib.parse import unquote
    r = client.get(f"/video/{original_video['id']}/download/original")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "attachment" in cd.lower()
    # filename derived from the title plus the original extension
    # (Starlette RFC 5987-encodes the space in the title)
    assert "Mein Clip.mp4" in unquote(cd)
    assert r.content == original_video["bytes"]


# ---- per quality ----

def test_download_quality_video_not_found(client):
    r = client.get("/video/999999/download/720p")
    assert r.status_code == 404


def test_download_quality_unknown_rendition(client, ready_video):
    # 480p was never produced for this video
    r = client.get(f"/video/{ready_video['id']}/download/480p")
    assert r.status_code == 404


def test_download_quality_returns_playable_mp4(client, ready_video, tmp_path):
    from urllib.parse import unquote
    r = client.get(f"/video/{ready_video['id']}/download/720p")
    assert r.status_code == 200
    assert "video/mp4" in r.headers["content-type"]
    cd = r.headers["content-disposition"]
    assert "attachment" in cd.lower()
    assert "Mein Clip_720p.mp4" in unquote(cd)

    out = str(tmp_path / "dl.mp4")
    with open(out, "wb") as f:
        f.write(r.content)
    assert _ffprobe_streams(out) == {"video", "audio"}


def test_download_quality_path_traversal(client, ready_video):
    r = client.get(f"/video/{ready_video['id']}/download/..%2f..%2fmaster")
    assert r.status_code in (400, 404)


def test_index_card_shows_download_links(client, ready_video):
    r = client.get("/?per_page=100")
    assert r.status_code == 200
    html = r.text
    vid = ready_video["id"]
    assert f"/video/{vid}/download/original" in html
    assert f"/video/{vid}/download/720p" in html


def test_download_quality_cleans_up_temp_file(client, ready_video):
    import glob
    import tempfile
    vid = ready_video["id"]
    pattern = os.path.join(tempfile.gettempdir(), f"dl_{vid}_720p_*.mp4")
    r = client.get(f"/video/{vid}/download/720p")
    assert r.status_code == 200
    # the remuxed temp file is removed after the response is sent
    assert glob.glob(pattern) == []
