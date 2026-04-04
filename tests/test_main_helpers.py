"""Unit tests for app/main.py helper functions (no DB required)."""
import sys
import os

# Allow importing main.py without the app starting up
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from datetime import datetime, timezone, UTC
from zoneinfo import ZoneInfo

# Patch pool so importing main doesn't require psycopg_pool to be wired up
import unittest.mock as mock
import main as m


# ------------------------------------------------------------------
# format_duration_mmss
# ------------------------------------------------------------------

def test_format_duration_mmss_zero():
    assert m.format_duration_mmss(0) is None


def test_format_duration_mmss_none():
    assert m.format_duration_mmss(None) is None


def test_format_duration_mmss_under_minute():
    assert m.format_duration_mmss(45) == "00:45"


def test_format_duration_mmss_exact_minute():
    assert m.format_duration_mmss(60) == "01:00"


def test_format_duration_mmss_over_hour():
    assert m.format_duration_mmss(3661) == "61:01"


def test_format_duration_mmss_rounds():
    assert m.format_duration_mmss(90.7) == "01:31"


# ------------------------------------------------------------------
# format_local_dt
# ------------------------------------------------------------------

def test_format_local_dt_none():
    assert m.format_local_dt(None) is None


def test_format_local_dt_empty_string():
    assert m.format_local_dt("") is None


def test_format_local_dt_iso_string():
    result = m.format_local_dt("2024-06-15T10:00:00")
    assert result is not None
    assert "2024" in result


def test_format_local_dt_datetime_object():
    dt = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
    result = m.format_local_dt(dt)
    assert result is not None
    assert "15.06.2024" in result


# ------------------------------------------------------------------
# parse_streams
# ------------------------------------------------------------------

def test_parse_streams_none():
    assert m.parse_streams(None) == []


def test_parse_streams_empty():
    assert m.parse_streams("") == []


def test_parse_streams_valid():
    data = [{"codec_type": "video"}, {"codec_type": "audio"}]
    import json
    result = m.parse_streams(json.dumps(data))
    assert len(result) == 2
    assert result[0]["codec_type"] == "video"


def test_parse_streams_invalid_json():
    result = m.parse_streams("not-json{{{")
    assert result == []


# ------------------------------------------------------------------
# highlight_query_in_text
# ------------------------------------------------------------------

def test_highlight_empty_query():
    result = m.highlight_query_in_text("Hello World", "")
    assert result == "Hello World"
    assert "<mark" not in result


def test_highlight_no_match():
    result = m.highlight_query_in_text("Hello World", "xyz")
    assert "<mark" not in result
    assert "Hello World" in result


def test_highlight_match():
    result = m.highlight_query_in_text("Hello World", "World")
    assert '<mark class="title-hit">World</mark>' in result


def test_highlight_case_insensitive():
    result = m.highlight_query_in_text("Hello World", "world")
    assert "<mark" in result


def test_highlight_escapes_html():
    result = m.highlight_query_in_text("<script>alert(1)</script>", "")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_highlight_escapes_match_content():
    result = m.highlight_query_in_text("Hello <b>World</b>", "World")
    assert "&lt;b&gt;" not in result or "World" in result
    assert "<script" not in result


def test_highlight_multiple_matches():
    result = m.highlight_query_in_text("foo foo foo", "foo")
    assert result.count("<mark") == 3


# ------------------------------------------------------------------
# format_encoding_duration
# ------------------------------------------------------------------

def test_format_encoding_duration_none():
    assert m.format_encoding_duration(None, None) is None


def test_format_encoding_duration_iso_strings():
    result = m.format_encoding_duration("2024-01-01T10:00:00", "2024-01-01T10:05:30")
    assert result == "05:30"


def test_format_encoding_duration_datetime_objects():
    from datetime import datetime, UTC
    start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    end = datetime(2024, 1, 1, 10, 2, 15, tzinfo=UTC)
    result = m.format_encoding_duration(start, end)
    assert result == "02:15"


def test_format_encoding_duration_over_hour():
    result = m.format_encoding_duration("2024-01-01T10:00:00", "2024-01-01T11:30:00")
    assert result == "90:00"


# ------------------------------------------------------------------
# validate_upload
# ------------------------------------------------------------------

def test_validate_upload_valid_mp4():
    f = mock.Mock()
    f.filename = "video.mp4"
    f.content_type = "video/mp4"
    m.validate_upload(f)  # should not raise


def test_validate_upload_invalid_extension():
    from fastapi import HTTPException
    f = mock.Mock()
    f.filename = "document.pdf"
    f.content_type = "application/pdf"
    with pytest.raises(HTTPException) as exc_info:
        m.validate_upload(f)
    assert exc_info.value.status_code == 400


def test_validate_upload_invalid_content_type():
    from fastapi import HTTPException
    f = mock.Mock()
    f.filename = "video.mp4"
    f.content_type = "text/html"
    with pytest.raises(HTTPException) as exc_info:
        m.validate_upload(f)
    assert exc_info.value.status_code == 400


def test_validate_upload_octet_stream_allowed():
    f = mock.Mock()
    f.filename = "video.mkv"
    f.content_type = "application/octet-stream"
    m.validate_upload(f)  # should not raise


# ------------------------------------------------------------------
# copy_with_size_limit
# ------------------------------------------------------------------

def test_copy_with_size_limit_ok(tmp_path):
    import io
    data = b"x" * 100
    src = io.BytesIO(data)
    dst = str(tmp_path / "out.bin")
    size = m.copy_with_size_limit(src, dst, max_bytes=1000)
    assert size == 100
    assert os.path.exists(dst)


def test_copy_with_size_limit_exceeded(tmp_path):
    from fastapi import HTTPException
    import io
    data = b"x" * 200
    src = io.BytesIO(data)
    dst = str(tmp_path / "out.bin")
    with pytest.raises(HTTPException) as exc_info:
        m.copy_with_size_limit(src, dst, max_bytes=100)
    assert exc_info.value.status_code == 413
    assert not os.path.exists(dst)
