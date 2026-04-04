"""Unit tests for worker/worker.py helper functions (no DB/ffmpeg required)."""
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))

import worker as w


# ------------------------------------------------------------------
# codecs_for_profile
# ------------------------------------------------------------------

def test_codecs_baseline():
    result = w.codecs_for_profile("baseline")
    assert "avc1.42E01E" in result
    assert "mp4a.40.2" in result


def test_codecs_main():
    result = w.codecs_for_profile("main")
    assert "avc1.4D401F" in result


def test_codecs_high():
    result = w.codecs_for_profile("high")
    assert "avc1.640028" in result


def test_codecs_unknown_falls_back_to_high():
    result = w.codecs_for_profile("unknown")
    assert "avc1.640028" in result


# ------------------------------------------------------------------
# width_from_height
# ------------------------------------------------------------------

def test_width_1080p():
    assert w.width_from_height(1080) == 1920


def test_width_720p():
    assert w.width_from_height(720) == 1280


def test_width_480p():
    assert w.width_from_height(480) == 852


def test_width_360p():
    assert w.width_from_height(360) == 640


def test_width_always_even():
    for h in range(100, 1200, 13):
        width = w.width_from_height(h)
        assert width % 2 == 0, f"width_from_height({h}) = {width} is not even"


# ------------------------------------------------------------------
# count_segments
# ------------------------------------------------------------------

def test_count_segments_empty(tmp_path):
    assert w.count_segments(str(tmp_path)) == 0


def test_count_segments_counts_m4s(tmp_path):
    (tmp_path / "seg_00001.m4s").write_bytes(b"")
    (tmp_path / "seg_00002.m4s").write_bytes(b"")
    (tmp_path / "other.mp4").write_bytes(b"")
    assert w.count_segments(str(tmp_path)) == 2


def test_count_segments_recursive(tmp_path):
    sub = tmp_path / "rendition"
    sub.mkdir()
    (sub / "seg_00001.m4s").write_bytes(b"")
    (tmp_path / "seg_00001.m4s").write_bytes(b"")
    assert w.count_segments(str(tmp_path)) == 2


# ------------------------------------------------------------------
# VideoDeleted / VideoCancelled exceptions
# ------------------------------------------------------------------

def test_video_deleted_is_exception():
    with __import__("pytest").raises(w.VideoDeleted):
        raise w.VideoDeleted()


def test_video_cancelled_is_exception():
    with __import__("pytest").raises(w.VideoCancelled):
        raise w.VideoCancelled()


def test_exceptions_are_distinct():
    assert w.VideoDeleted is not w.VideoCancelled
    assert not issubclass(w.VideoDeleted, w.VideoCancelled)
    assert not issubclass(w.VideoCancelled, w.VideoDeleted)
