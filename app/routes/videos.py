import os
import re
import shutil
import json
import time
import asyncio
import subprocess
import logging
from datetime import datetime, UTC
from uuid import uuid4
from math import ceil
from urllib.parse import quote_plus

from fastapi import APIRouter, Request, UploadFile, File, Form, Query, Body, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, FileResponse

import db
from helpers import (
    UPLOAD_DIR, HLS_DIR, PAGE_SIZE_DEFAULT, PAGE_SIZE_OPTIONS, MAX_UPLOAD_BYTES,
    PUBLIC_BASE,
    get_email, format_local_dt, format_duration_mmss, parse_streams,
    parse_master_playlist, kill_process_group, format_encoding_duration,
    highlight_query_in_text, validate_upload, copy_with_size_limit,
    log_activity, _resolve_hls_path,
)
from i18n import t

logger = logging.getLogger(__name__)

router = APIRouter()

_poster_cooldown: dict = {}


def _get_templates(request: Request):
    return request.app.state.templates


# ---------------------------------------------------------------------
# Index / list
# ---------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    page: int = Query(1, ge=1),
    q: str = Query(""),
    cat: int = Query(0, alias="cat"),
    per_page: int = Query(10, alias="per_page"),
):
    q = (q or "").strip()[:200]
    cat = cat or 0
    page_size = per_page if per_page in PAGE_SIZE_OPTIONS else PAGE_SIZE_DEFAULT
    show_all = page_size == 0

    with db.pool.connection() as c:
        categories = c.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()

        where_parts = []
        params: list = []

        if q:
            like = f"%{q.replace('%', '\\%').replace('_', '\\_')}%"
            where_parts.append("(orig_name ILIKE %s OR COALESCE(note, '') ILIKE %s OR category_id IN (SELECT id FROM categories WHERE name ILIKE %s))")
            params.extend([like, like, like])

        if cat:
            where_parts.append("category_id = %s")
            params.append(cat)

        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

        total = c.execute(
            f"SELECT COUNT(*) AS total FROM videos{where_sql}",
            params,
        ).fetchone()["total"]

        if show_all:
            pages = 1
            videos = c.execute(
                f"SELECT * FROM videos{where_sql} ORDER BY id DESC",
                params,
            ).fetchall()
        else:
            pages = max(1, ceil(total / page_size))
            offset = (page - 1) * page_size
            videos = c.execute(
                f"SELECT * FROM videos{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            ).fetchall()

    enriched = []
    cat_map = {d["id"]: d["name"] for d in categories}
    for v in videos:
        d = dict(v)
        d["duration_mmss"] = format_duration_mmss(d.get("duration_seconds"))
        d["encoded_local"] = format_local_dt(d.get("encoded_at"))
        d["streams"] = parse_streams(d.get("streams_json"))
        d["renditions"] = parse_master_playlist(d["id"])
        d["encoding_duration"] = format_encoding_duration(
            d.get("started_at"),
            d.get("encoded_at")
        )
        d["orig_name_highlighted"] = highlight_query_in_text(d.get("orig_name"), q)
        d["note_highlighted"] = highlight_query_in_text(d.get("note"), q)
        d["note_has_hit"] = bool(q and q.lower() in (d.get("note") or "").lower())
        d["category_name"] = cat_map.get(d.get("category_id"))
        enriched.append(d)

    templates = _get_templates(request)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "videos": enriched,
            "page": page,
            "pages": pages,
            "q": q,
            "q_url": quote_plus(q) if q else "",
            "cat": cat,
            "per_page": page_size,
            "per_page_options": PAGE_SIZE_OPTIONS,
            "categories": categories,
            "email": get_email(request),
        },
    )


# ---------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------

@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    with db.pool.connection() as c:
        categories = c.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()
    templates = _get_templates(request)
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "email": get_email(request), "categories": categories},
    )


@router.post("/upload")
def upload(
    request: Request,
    f: UploadFile = File(...),
    note: str = Form(""),
    category_id: int = Form(...),
):
    email = get_email(request)
    now = datetime.now(UTC)
    note = str(note or "").strip()

    if len(note) > 2000:
        raise HTTPException(status_code=400, detail=t("validation.note_too_long"))

    validate_upload(f)

    with db.pool.connection() as c:
        cat_row = c.execute(
            "SELECT id FROM categories WHERE id=%s", (category_id,)
        ).fetchone()
        if not cat_row:
            raise HTTPException(status_code=400, detail=t("validation.invalid_category"))

    safe_filename = re.sub(r'[^\w.\-]', '_', f.filename or "video")[:100]
    stored_name = f"{now:%Y%m%d%H%M%S}_{uuid4().hex}_{safe_filename}"
    target = os.path.join(UPLOAD_DIR, stored_name)

    size = copy_with_size_limit(f.file, target, MAX_UPLOAD_BYTES)
    logger.info("Upload: %s (%d bytes) by %s", f.filename, size, email)

    with db.pool.connection() as c:
        c.execute(
            """
            INSERT INTO videos
            (orig_name, stored_name, uploaded_at, owner_email,
             status, progress, queued_at, note, category_id)
            VALUES (%s, %s, %s, %s, 'queued', 0, %s, %s, %s)
            """,
            (os.path.splitext(f.filename or "")[0] or f.filename, stored_name, now, email, now, note, category_id),
        )

    title = os.path.splitext(f.filename or "")[0] or f.filename
    log_activity(email, "upload", title)
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------------
# Video actions
# ---------------------------------------------------------------------

@router.post("/cancel/{vid}")
def cancel(vid: int):
    with db.pool.connection() as c:
        row = c.execute("SELECT status FROM videos WHERE id=%s", (vid,)).fetchone()
        if not row:
            return {"ok": False}

        if row["status"] == "queued":
            c.execute(
                """
                UPDATE videos
                SET status='cancelled',
                    cancel_requested=0,
                    eta_seconds=NULL
                WHERE id=%s
                """,
                (vid,),
            )
        elif row["status"] == "encoding":
            c.execute("UPDATE videos SET cancel_requested=1 WHERE id=%s", (vid,))

    return {"ok": True}


@router.post("/reencode/{vid}")
def reencode(request: Request, vid: int):
    now = datetime.now(UTC)

    with db.pool.connection() as c:
        row = c.execute("SELECT orig_name, status FROM videos WHERE id=%s", (vid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=t("validation.video_not_found"))
        if row["status"] in ("queued", "encoding"):
            return {"ok": True, "already": True}
        c.execute(
            """
            UPDATE videos
            SET status='queued',
                progress=0,
                error=NULL,
                cancel_requested=0,
                started_at=NULL,
                ffmpeg_pid=NULL,
                eta_seconds=NULL,
                queued_at=%s
            WHERE id=%s
            """,
            (now, vid),
        )

    log_activity(get_email(request), "reencode", (row or {}).get("orig_name") or f"Video #{vid}")

    return {"ok": True}


@router.post("/delete/{vid}")
def delete(request: Request, vid: int):
    with db.pool.connection() as c:
        row = c.execute(
            "SELECT stored_name, orig_name, ffmpeg_pid, status FROM videos WHERE id=%s FOR UPDATE",
            (vid,),
        ).fetchone()

        if not row:
            return {"ok": False}

        if row["status"] == "encoding" and row["ffmpeg_pid"]:
            kill_process_group(int(row["ffmpeg_pid"]))

        c.execute("DELETE FROM videos WHERE id=%s", (vid,))

    up = os.path.join(UPLOAD_DIR, row["stored_name"])
    hls = os.path.join(HLS_DIR, str(vid))
    disabled_hls = os.path.join(HLS_DIR, f".disabled_{vid}")

    try:
        if os.path.exists(up):
            os.remove(up)
        if os.path.exists(hls):
            shutil.rmtree(hls)
        if os.path.exists(disabled_hls):
            shutil.rmtree(disabled_hls)
    except OSError as exc:
        logger.warning("File cleanup for video %d: %s", vid, exc)

    log_activity(get_email(request), "delete", row.get("orig_name") or f"Video #{vid}")
    logger.info("Deleted video id=%d (%s)", vid, row["stored_name"])
    return {"ok": True}


@router.post("/video/{vid}/title")
def rename_title(request: Request, vid: int, payload: dict = Body(...)):
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail=t("validation.title_required"))
    if len(title) > 255:
        raise HTTPException(status_code=400, detail=t("validation.title_too_long"))

    with db.pool.connection() as c:
        row = c.execute("SELECT orig_name FROM videos WHERE id=%s", (vid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=t("validation.video_not_found"))
        old_title = row["orig_name"]
        c.execute("UPDATE videos SET orig_name=%s WHERE id=%s", (title, vid))

    log_activity(get_email(request), "rename", title, f"vorher: {old_title}")
    return {"ok": True, "title": title}


@router.post("/video/{vid}/note")
def save_note(request: Request, vid: int, payload: dict = Body(...)):
    note = str(payload.get("note", "")).strip()
    if len(note) > 2000:
        raise HTTPException(status_code=400, detail=t("validation.note_too_long"))

    with db.pool.connection() as c:
        row = c.execute("SELECT orig_name FROM videos WHERE id=%s", (vid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=t("validation.video_not_found"))
        c.execute("UPDATE videos SET note=%s WHERE id=%s", (note, vid))

    log_activity(get_email(request), "note", row.get("orig_name") or f"Video #{vid}")
    return {"ok": True, "note": note}


@router.get("/video/{vid}/progress")
def video_progress(vid: int):
    with db.pool.connection() as c:
        v = c.execute(
            "SELECT status, progress, eta_seconds, poster_url, playlist_url, cpu_percent FROM videos WHERE id=%s",
            (vid,),
        ).fetchone()

    if not v:
        return JSONResponse({"status": "missing"}, status_code=404)

    return {
        "status": v["status"],
        "progress": v["progress"],
        "eta_seconds": v["eta_seconds"],
        "poster_url": v["poster_url"],
        "playlist_url": v["playlist_url"],
        "cpu_percent": v["cpu_percent"],
    }


@router.get("/events/{vid}")
async def video_events(vid: int):
    MAX_SSE_DURATION = 30 * 60  # 30 minutes max

    async def event_stream():
        start = time.time()
        while time.time() - start < MAX_SSE_DURATION:
            with db.pool.connection() as c:
                v = c.execute(
                    "SELECT status, progress, eta_seconds, poster_url, playlist_url, cpu_percent FROM videos WHERE id=%s",
                    (vid,),
                ).fetchone()

            if not v:
                yield f"data: {json.dumps({'status': 'missing'})}\n\n"
                break

            data = {
                "status": v["status"],
                "progress": v["progress"],
                "eta_seconds": v["eta_seconds"],
                "poster_url": v["poster_url"],
                "playlist_url": v["playlist_url"],
                "cpu_percent": v["cpu_percent"],
            }
            yield f"data: {json.dumps(data)}\n\n"

            if v["status"] not in ("queued", "encoding"):
                break

            await asyncio.sleep(3)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@router.post("/video/{vid}/poster")
def set_poster(request: Request, vid: int, payload: dict = Body(...)):
    seconds = payload.get("seconds")
    if seconds is None or not isinstance(seconds, (int, float)):
        raise HTTPException(status_code=400, detail=t("validation.timestamp_required"))
    seconds = max(0, float(seconds))

    now = time.time()
    if vid in _poster_cooldown and now - _poster_cooldown[vid] < 5:
        raise HTTPException(status_code=429, detail=t("validation.rate_limited"))
    _poster_cooldown[vid] = now

    with db.pool.connection() as c:
        row = c.execute(
            "SELECT stored_name, poster_url, orig_name FROM videos WHERE id=%s",
            (vid,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=t("validation.video_not_found"))

    src = os.path.join(UPLOAD_DIR, row["stored_name"])
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=t("validation.source_not_found"))

    # Find the correct HLS directory (active or disabled)
    hls_dir = os.path.join(HLS_DIR, str(vid))
    disabled_dir = os.path.join(HLS_DIR, f".disabled_{vid}")
    target_dir = hls_dir if os.path.isdir(hls_dir) else disabled_dir
    poster_path = os.path.join(target_dir, "poster.jpg")
    os.makedirs(target_dir, exist_ok=True)

    ts = f"{int(seconds // 3600):02d}:{int(seconds % 3600 // 60):02d}:{seconds % 60:06.3f}"

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", ts,
            "-i", src,
            "-vframes", "1",
            "-update", "1",
            "-vf", "scale=1280:-2",
            poster_path,
        ],
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        logger.error("ffmpeg poster extract failed: %s", result.stderr.decode(errors="replace"))
        raise HTTPException(status_code=500, detail=t("validation.poster_failed"))

    # Cache-Buster an die URL haengen
    base_url = (row["poster_url"] or "").split("?")[0]
    if not base_url:
        base_url = f"{PUBLIC_BASE}/{vid}/poster.jpg"
    new_url = f"{base_url}?t={int(time.time())}"

    with db.pool.connection() as c:
        c.execute("UPDATE videos SET poster_url=%s WHERE id=%s", (new_url, vid))

    log_activity(get_email(request), "poster", row.get("orig_name") or f"Video #{vid}", f"bei {seconds:.1f}s")
    return {"ok": True, "poster_url": new_url}


@router.post("/video/{vid}/toggle-disabled")
def toggle_disabled(request: Request, vid: int):
    with db.pool.connection() as c:
        row = c.execute(
            "SELECT disabled, orig_name FROM videos WHERE id=%s FOR UPDATE", (vid,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=t("validation.video_not_found"))

        new_state = 0 if row["disabled"] else 1
        c.execute("UPDATE videos SET disabled=%s WHERE id=%s", (new_state, vid))

    hls_dir = os.path.join(HLS_DIR, str(vid))
    disabled_dir = os.path.join(HLS_DIR, f".disabled_{vid}")

    if new_state == 1:
        if os.path.exists(hls_dir) and not os.path.exists(disabled_dir):
            os.rename(hls_dir, disabled_dir)
    else:
        if os.path.exists(disabled_dir):
            if os.path.exists(hls_dir):
                shutil.rmtree(hls_dir)
            os.rename(disabled_dir, hls_dir)

    log_activity(get_email(request), "disable" if new_state else "enable", row.get("orig_name") or f"Video #{vid}")
    return {"ok": True, "disabled": new_state}


@router.get("/video/{vid}/file/{filename:path}")
def serve_video_file(vid: int, filename: str):
    """Serve HLS files through the app (works for disabled videos too)."""
    # Only allow safe filenames
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400)
    path = _resolve_hls_path(vid, filename)
    if not path:
        raise HTTPException(status_code=404)

    return FileResponse(path)


@router.post("/video/{vid}/category")
def update_video_category(request: Request, vid: int, payload: dict = Body(...)):
    category_id = payload.get("category_id")
    if category_id is not None:
        category_id = int(category_id)

    with db.pool.connection() as c:
        row = c.execute("SELECT orig_name FROM videos WHERE id=%s", (vid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=t("validation.video_not_found"))

        if category_id:
            cat_row = c.execute(
                "SELECT id, name FROM categories WHERE id=%s", (category_id,)
            ).fetchone()
            if not cat_row:
                raise HTTPException(status_code=400, detail=t("validation.invalid_category"))
            c.execute(
                "UPDATE videos SET category_id=%s WHERE id=%s",
                (category_id, vid),
            )
            log_activity(get_email(request), "cat", row.get("orig_name") or f"Video #{vid}", cat_row["name"])
            return {"ok": True, "category_id": category_id, "category_name": cat_row["name"]}
        else:
            c.execute(
                "UPDATE videos SET category_id=NULL WHERE id=%s", (vid,)
            )
            log_activity(get_email(request), "cat", row.get("orig_name") or f"Video #{vid}", t("video.no_category"))
            return {"ok": True, "category_id": None, "category_name": None}
