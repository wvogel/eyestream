import os
import re
import json
import html
import signal
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Request, UploadFile, HTTPException

import db
from i18n import t

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
HLS_DIR = os.getenv("HLS_DIR", "/data/hls")
APP_VERSION = "Version 4.2"
NPM_LOG_DIR = os.getenv("NPM_LOG_DIR", "/data/npm-logs")
NPM_SITE_ID = os.getenv("NPM_SITE_ID", "")

BRAND_NAME = os.getenv("BRAND_NAME", "Eyestream")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Eyestream")
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "https://localhost")
LOGO_URL = os.getenv("LOGO_URL", "")
FOOTER_LINKS = os.getenv("FOOTER_LINKS", "")  # format: "Label1|URL1,Label2|URL2"
COPYRIGHT_TEXT = os.getenv("COPYRIGHT_TEXT", "")
EXAMPLE_PAGE_URL = os.getenv("EXAMPLE_PAGE_URL", "")
REFERER_IGNORE_SEEDS = os.getenv("REFERER_IGNORE_SEEDS", "localhost")
PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_OPTIONS = [10, 20, 50, 100, 0]  # 0 = all
LOCAL_TZ = ZoneInfo("Europe/Berlin")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024 * 1024)))  # 10 GB
ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".mxf", ".m4v", ".ts", ".flv", ".wmv",
}
ALLOWED_CONTENT_TYPES = {
    "video/mp4", "video/quicktime", "video/x-matroska", "video/x-msvideo",
    "video/webm", "video/mxf", "video/x-m4v", "video/mp2t", "video/x-flv",
    "video/x-ms-wmv", "application/octet-stream",
}

MAX_ID = 2147483647


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _check_id(vid: int):
    if vid < 1 or vid > MAX_ID:
        raise HTTPException(status_code=400, detail=t("validation.invalid_id"))


def log_activity(email: str, action: str, target: str, detail: str = ""):
    try:
        with db.pool.connection() as c:
            c.execute(
                "INSERT INTO activity_log (user_email, action, target, detail) VALUES (%s, %s, %s, %s)",
                (email, action, target, detail),
            )
    except Exception as exc:
        logger.warning("Failed to log activity: %s", exc)


def get_email(request: Request) -> str:
    return (
        request.headers.get("X-Auth-Request-Email")
        or request.headers.get("X-Forwarded-Email")
        or request.headers.get("X-Forwarded-User")
        or ""
    )


def format_local_dt(val) -> str | None:
    if not val:
        return None
    if isinstance(val, str):
        dt = datetime.fromisoformat(val).replace(tzinfo=ZoneInfo("UTC"))
    else:
        dt = val
    return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")


def format_duration_mmss(seconds) -> str | None:
    if not seconds:
        return None
    seconds = int(round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_streams(streams_json: str) -> list:
    if not streams_json:
        return []
    try:
        return json.loads(streams_json)
    except Exception as exc:
        logger.warning("Failed to parse streams_json: %s", exc)
        return []


def parse_master_playlist(vid_id: int) -> list:
    path = os.path.join(HLS_DIR, str(vid_id), "master.m3u8")
    if not os.path.exists(path):
        path = os.path.join(HLS_DIR, f".disabled_{vid_id}", "master.m3u8")
    if not os.path.exists(path):
        return []

    renditions = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            attrs = line.split(":", 1)[1]
            data = {}
            for part in attrs.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    data[k] = v.strip('"')

            playlist = lines[i + 1].strip()

            renditions.append({
                "resolution": data.get("RESOLUTION"),
                "bandwidth": data.get("BANDWIDTH"),
                "playlist": playlist,
            })

    return renditions


def kill_process_group(pid: int):
    if not pid:
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError as exc:
        logger.debug("kill_process_group(%d): %s", pid, exc)


def format_encoding_duration(start, end) -> str | None:
    if not start or not end:
        return None

    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        delta = int((end - start).total_seconds())
        m = delta // 60
        s = delta % 60
        return f"{m:02d}:{s:02d}"
    except Exception as exc:
        logger.warning("format_encoding_duration failed: %s", exc)
        return None


def highlight_query_in_text(text: str, query: str) -> str:
    text = text or ""
    query = (query or "").strip()
    if not query:
        return html.escape(text)

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return html.escape(text)

    parts = []
    last = 0
    for match in matches:
        start, end = match.span()
        parts.append(html.escape(text[last:start]))
        parts.append(
            f'<mark class="title-hit">{html.escape(text[start:end])}</mark>'
        )
        last = end

    parts.append(html.escape(text[last:]))
    return "".join(parts)


def validate_upload(f: UploadFile):
    """Raise HTTPException if the upload is not a valid video file."""
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t("validation.unsupported_format", ext=ext),
        )

    content_type = (f.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=t("validation.unsupported_content_type", type=content_type),
        )


def copy_with_size_limit(src, dst_path: str, max_bytes: int) -> int:
    """Stream file to disk, raising HTTP 413 if max_bytes is exceeded."""
    written = 0
    with open(dst_path, "wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                out.close()
                os.remove(dst_path)
                raise HTTPException(
                    status_code=413,
                    detail=t("validation.file_too_large", max=max_bytes // (1024**3)),
                )
            out.write(chunk)
    return written


def _resolve_hls_path(vid: int, filename: str) -> str | None:
    """Find a file in the HLS dir, checking both active and disabled paths."""
    hls_real = os.path.realpath(HLS_DIR)
    for d in [os.path.join(HLS_DIR, str(vid)), os.path.join(HLS_DIR, f".disabled_{vid}")]:
        p = os.path.realpath(os.path.join(d, filename))
        if not p.startswith(hls_real + os.sep):
            continue
        if os.path.isfile(p):
            return p
    return None


def _get_worker_health():
    try:
        with db.pool.connection() as c:
            row = c.execute("SELECT last_seen, status, cpu_percent FROM worker_heartbeat WHERE id=1").fetchone()
        if not row or not row["last_seen"]:
            return {"status": "unknown", "last_seen": None}
        from datetime import UTC
        age = (datetime.now(UTC) - row["last_seen"]).total_seconds()
        return {
            "status": "ok" if age < 30 else "stale",
            "worker_status": row["status"],
            "last_seen_seconds_ago": int(age),
            "cpu_percent": row.get("cpu_percent"),
        }
    except Exception:
        return {"status": "unknown", "last_seen": None}


def _count_orphaned_uploads():
    try:
        with db.pool.connection() as c:
            stored = {r["stored_name"] for r in c.execute("SELECT stored_name FROM videos").fetchall()}
        if not os.path.isdir(UPLOAD_DIR):
            return {"count": 0, "files": []}
        on_disk = set(os.listdir(UPLOAD_DIR))
        orphaned = sorted(on_disk - stored)
        return {"count": len(orphaned), "files": orphaned[:50]}
    except Exception:
        return {"count": 0, "files": []}
