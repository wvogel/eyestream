import shutil
import subprocess
import time
import logging

from fastapi import APIRouter, Request, Body, Query, HTTPException
from fastapi.responses import HTMLResponse

import db
from helpers import (
    UPLOAD_DIR, HLS_DIR,
    get_email, _get_worker_health, _count_orphaned_uploads,
)
from i18n import t
from routes.misc import _referer_cache

logger = logging.getLogger(__name__)

router = APIRouter()

_disk_cache = {"data": None, "ts": 0}


def _get_disk_usage():
    now = time.time()
    if _disk_cache["data"] is not None and now - _disk_cache["ts"] < 600:
        return _disk_cache["data"]

    try:
        du = shutil.disk_usage("/data")
        partition_total = du.total
        partition_used = du.used
        partition_free = du.free
    except Exception:
        partition_total = partition_used = partition_free = 0

    uploads_bytes = 0
    hls_bytes = 0
    try:
        result = subprocess.run(["du", "-sb", UPLOAD_DIR], capture_output=True, timeout=30)
        if result.returncode == 0:
            uploads_bytes = int(result.stdout.split()[0])
    except Exception:
        pass
    try:
        result = subprocess.run(["du", "-sb", HLS_DIR], capture_output=True, timeout=30)
        if result.returncode == 0:
            hls_bytes = int(result.stdout.split()[0])
    except Exception:
        pass

    data = {
        "uploads_bytes": uploads_bytes,
        "hls_bytes": hls_bytes,
        "partition_total": partition_total,
        "partition_used": partition_used,
        "partition_free": partition_free,
    }
    _disk_cache["data"] = data
    _disk_cache["ts"] = now
    return data


def _get_templates(request: Request):
    return request.app.state.templates


# ---------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    with db.pool.connection() as c:
        categories = c.execute(
            """
            SELECT d.id, d.name, d.created_at,
                   COUNT(v.id) AS video_count
            FROM categories d
            LEFT JOIN videos v ON v.category_id = d.id
            GROUP BY d.id
            ORDER BY d.name
            """
        ).fetchall()
        referer_ignores = c.execute(
            "SELECT id, pattern FROM referer_ignore ORDER BY pattern"
        ).fetchall()
    templates = _get_templates(request)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "email": get_email(request),
            "categories": categories,
            "referer_ignores": referer_ignores,
        },
    )


@router.get("/worker/status")
def worker_status():
    return _get_worker_health()


@router.get("/settings/stats")
def settings_stats():
    with db.pool.connection() as c:
        row = c.execute(
            """
            SELECT
                COUNT(*) AS total_videos,
                COUNT(*) FILTER (WHERE status = 'ready') AS ready_count,
                COUNT(*) FILTER (WHERE status = 'encoding') AS encoding_count,
                COUNT(*) FILTER (WHERE status = 'queued') AS queued_count,
                COUNT(*) FILTER (WHERE status IN ('failed', 'cancelled')) AS other_count,
                COALESCE(SUM(duration_seconds), 0) AS total_duration,
                COALESCE(AVG(
                    EXTRACT(EPOCH FROM (encoded_at - started_at)) / NULLIF(duration_seconds, 0)
                ) FILTER (WHERE encoded_at IS NOT NULL AND started_at IS NOT NULL AND duration_seconds > 0), 0
                ) AS avg_encoding_factor
            FROM videos
            """
        ).fetchone()

        by_cat = c.execute(
            """
            SELECT
                COALESCE(d.name, '—') AS name,
                d.id AS cat_id,
                COUNT(v.id) AS count,
                COALESCE(SUM(v.duration_seconds), 0) AS duration_seconds
            FROM videos v
            LEFT JOIN categories d ON d.id = v.category_id
            GROUP BY d.id, d.name
            ORDER BY count DESC
            """
        ).fetchall()

    # Disk usage (cached 10 min)
    disk = _get_disk_usage()

    return {
        "total_videos": row["total_videos"],
        "ready_count": row["ready_count"],
        "encoding_count": row["encoding_count"],
        "queued_count": row["queued_count"],
        "other_count": row["other_count"],
        "total_duration": row["total_duration"],
        "avg_encoding_factor": round(float(row["avg_encoding_factor"] or 0), 2),
        "by_category": [dict(d) for d in by_cat],
        "disk": {
            "uploads_bytes": disk["uploads_bytes"],
            "hls_bytes": disk["hls_bytes"],
            "partition_total": disk["partition_total"],
            "partition_used": disk["partition_used"],
            "partition_free": disk["partition_free"],
        },
        "worker": _get_worker_health(),
        "orphaned": _count_orphaned_uploads(),
    }


# ---------------------------------------------------------------------
# Categories CRUD
# ---------------------------------------------------------------------

@router.post("/categories")
def create_category(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("validation.name_required"))
    if len(name) > 100:
        raise HTTPException(status_code=400, detail=t("validation.name_too_long"))

    with db.pool.connection() as c:
        existing = c.execute(
            "SELECT id FROM categories WHERE name=%s", (name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=t("validation.category_exists"))
        row = c.execute(
            "INSERT INTO categories (name) VALUES (%s) RETURNING id, name",
            (name,),
        ).fetchone()

    return {"ok": True, "category": dict(row)}


@router.post("/categories/{cat_id}/rename")
def rename_category(cat_id: int, payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("validation.name_required"))
    if len(name) > 100:
        raise HTTPException(status_code=400, detail=t("validation.name_too_long"))

    with db.pool.connection() as c:
        existing = c.execute(
            "SELECT id FROM categories WHERE name=%s AND id != %s", (name, cat_id)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=t("validation.name_exists"))
        c.execute("UPDATE categories SET name=%s WHERE id=%s", (name, cat_id))

    return {"ok": True}


@router.post("/categories/{cat_id}/delete")
def delete_category(cat_id: int):
    with db.pool.connection() as c:
        c.execute("UPDATE videos SET category_id=NULL WHERE category_id=%s", (cat_id,))
        c.execute("DELETE FROM categories WHERE id=%s", (cat_id,))
    return {"ok": True}


# ---------------------------------------------------------------------
# Referer ignore CRUD
# ---------------------------------------------------------------------

@router.post("/referer-ignore")
def add_referer_ignore(payload: dict = Body(...)):
    pattern = str(payload.get("pattern", "")).strip().lower()
    if not pattern:
        raise HTTPException(status_code=400, detail=t("validation.pattern_required"))
    if len(pattern) > 200:
        raise HTTPException(status_code=400, detail=t("validation.pattern_too_long"))
    with db.pool.connection() as c:
        existing = c.execute(
            "SELECT id FROM referer_ignore WHERE pattern=%s", (pattern,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=t("validation.pattern_exists"))
        row = c.execute(
            "INSERT INTO referer_ignore (pattern) VALUES (%s) RETURNING id, pattern",
            (pattern,),
        ).fetchone()
    _referer_cache["data"] = None  # invalidate cache
    return {"ok": True, "item": dict(row)}


@router.post("/referer-ignore/{rid}/delete")
def delete_referer_ignore(rid: int):
    with db.pool.connection() as c:
        c.execute("DELETE FROM referer_ignore WHERE id=%s", (rid,))
    _referer_cache["data"] = None  # invalidate cache
    return {"ok": True}
