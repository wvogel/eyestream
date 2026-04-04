import os
import re
import time
import subprocess
import logging
from collections import defaultdict
from datetime import datetime, UTC, timedelta
from math import ceil

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

import db
from helpers import (
    NPM_LOG_DIR, NPM_SITE_ID, REFERER_IGNORE_SEEDS,
    get_email, format_local_dt,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_referer_cache: dict = {"data": None, "ts": 0}

REFERER_IGNORE_DOMAINS = set([s.strip() for s in REFERER_IGNORE_SEEDS.split(",") if s.strip()] + ["localhost", "127.0.0.1", "-", ""])


def _get_templates(request: Request):
    return request.app.state.templates


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/detailed")
def health_detailed():
    """Comprehensive health check for monitoring."""
    checks = {}
    overall = "ok"

    # Database
    try:
        with db.pool.connection() as c:
            c.execute("SELECT 1").fetchone()
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error"}
        overall = "degraded"

    # Upload directory
    from helpers import UPLOAD_DIR, HLS_DIR, APP_VERSION
    upload_ok = os.path.isdir(UPLOAD_DIR) and os.access(UPLOAD_DIR, os.W_OK)
    checks["upload_dir"] = {"status": "ok" if upload_ok else "error"}
    if not upload_ok:
        overall = "degraded"

    # HLS directory
    hls_ok = os.path.isdir(HLS_DIR) and os.access(HLS_DIR, os.W_OK)
    checks["hls_dir"] = {"status": "ok" if hls_ok else "error"}
    if not hls_ok:
        overall = "degraded"

    # Worker heartbeat
    try:
        with db.pool.connection() as c:
            row = c.execute("SELECT last_seen, status, cpu_percent FROM worker_heartbeat WHERE id=1").fetchone()
        if row and row["last_seen"]:
            age = (datetime.now(UTC) - row["last_seen"]).total_seconds()
            worker_ok = age < 30
            checks["worker"] = {
                "status": "ok" if worker_ok else "stale",
                "worker_status": row["status"],
                "last_seen_seconds_ago": int(age),
                "cpu_percent": row.get("cpu_percent"),
            }
            if not worker_ok:
                overall = "degraded"
        else:
            checks["worker"] = {"status": "unknown"}
            overall = "degraded"
    except Exception:
        checks["worker"] = {"status": "error"}
        overall = "degraded"

    # ffmpeg availability
    try:
        import subprocess as sp
        result = sp.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        checks["ffmpeg"] = {"status": "ok" if result.returncode == 0 else "error"}
    except Exception:
        checks["ffmpeg"] = {"status": "missing"}
        overall = "degraded"

    # Disk space
    try:
        import shutil
        du = shutil.disk_usage("/data")
        used_pct = du.used / du.total * 100
        checks["disk"] = {
            "status": "ok" if used_pct < 90 else "warning",
            "used_percent": round(used_pct, 1),
            "free_gb": round(du.free / (1024**3), 1),
        }
        if used_pct >= 90:
            overall = "degraded"
    except Exception:
        checks["disk"] = {"status": "unknown"}

    # Video counts
    try:
        with db.pool.connection() as c:
            row = c.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='ready') AS ready,
                       COUNT(*) FILTER (WHERE status='encoding') AS encoding,
                       COUNT(*) FILTER (WHERE status='queued') AS queued,
                       COUNT(*) FILTER (WHERE disabled=1) AS disabled
                FROM videos
            """).fetchone()
        checks["videos"] = dict(row)
    except Exception:
        checks["videos"] = {"status": "error"}

    # NPM logs
    if NPM_SITE_ID:
        checks["npm_logs"] = {"status": "ok" if os.path.isdir(NPM_LOG_DIR) else "missing"}
    else:
        checks["npm_logs"] = {"status": "disabled"}

    return {
        "status": overall,
        "version": APP_VERSION,
        "checks": checks,
    }


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------

@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    templates = _get_templates(request)
    return templates.TemplateResponse(
        "stats.html",
        {"request": request, "email": get_email(request)},
    )


# ---------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------

@router.get("/activity", response_class=HTMLResponse)
def activity_page(request: Request, page: int = Query(1, ge=1)):
    per_page = 50
    offset = (page - 1) * per_page
    with db.pool.connection() as c:
        total = c.execute("SELECT COUNT(*) AS total FROM activity_log").fetchone()["total"]
        pages = max(1, ceil(total / per_page))
        entries = c.execute(
            "SELECT * FROM activity_log ORDER BY ts DESC LIMIT %s OFFSET %s",
            (per_page, offset),
        ).fetchall()

    enriched = []
    for e in entries:
        d = dict(e)
        d["ts_local"] = format_local_dt(d["ts"])
        enriched.append(d)

    templates = _get_templates(request)
    return templates.TemplateResponse(
        "activity.html",
        {
            "request": request,
            "email": get_email(request),
            "entries": enriched,
            "page": page,
            "pages": pages,
        },
    )


# ---------------------------------------------------------------------
# Search suggest
# ---------------------------------------------------------------------

@router.get("/search/suggest")
def search_suggest(q: str = Query("")):
    q = (q or "").strip()[:100]
    if len(q) < 2:
        return {"suggestions": []}

    escaped = q.replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped}%"
    with db.pool.connection() as c:
        videos = c.execute(
            "SELECT id, orig_name FROM videos WHERE orig_name ILIKE %s ORDER BY id DESC LIMIT 5",
            (like,),
        ).fetchall()
        cats = c.execute(
            "SELECT id, name FROM categories WHERE name ILIKE %s ORDER BY name LIMIT 3",
            (like,),
        ).fetchall()

    suggestions = []
    for v in videos:
        suggestions.append({"type": "video", "label": v["orig_name"], "value": v["orig_name"]})
    for d in cats:
        suggestions.append({"type": "bereich", "label": d["name"], "value": str(d["id"])})

    return {"suggestions": suggestions}


# ---------------------------------------------------------------------
# Referers
# ---------------------------------------------------------------------

@router.get("/referers")
def get_referers():
    if not NPM_SITE_ID:
        return {"referers": {}}

    now = time.time()
    if _referer_cache["data"] is not None and now - _referer_cache["ts"] < 600:
        return _referer_cache["data"]

    log_dir = NPM_LOG_DIR
    if not os.path.isdir(log_dir):
        return {"referers": {}}

    log_files = sorted(
        [f for f in os.listdir(log_dir)
         if f.startswith(f"proxy-host-{NPM_SITE_ID}_access.log")],
        reverse=True,
    )

    if not log_files:
        return {"referers": {}}

    # Load ignore patterns from DB
    with db.pool.connection() as c:
        ignore_rows = c.execute("SELECT pattern FROM referer_ignore").fetchall()
    ignore_patterns = [r["pattern"] for r in ignore_rows]

    # Use grep/zgrep for performance on large log files (200MB+)
    REFERER_DAYS = 4

    referer_domains: dict[str, set] = defaultdict(set)
    referer_urls: dict[str, set] = defaultdict(set)
    global_domain_counts: dict[str, int] = defaultdict(int)
    video_views: dict[str, int] = defaultdict(int)
    daily_hits: dict[str, int] = defaultdict(int)
    vid_re = re.compile(r'"/(\d+)/master\.m3u8|"/embed/(\d+)')
    ref_re = re.compile(r'"([^"]*)"$')
    date_re = re.compile(r'\[(\d{2}/\w{3}/\d{4}):')

    cutoff_dt = datetime.now(UTC) - timedelta(days=REFERER_DAYS)
    cutoff_ts = cutoff_dt.timestamp()
    cutoff_date = cutoff_dt.strftime("%Y-%m-%d")
    _month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                  "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}

    # Filter to files newer than cutoff
    recent_files = []
    for fname in log_files:
        fpath = os.path.join(log_dir, fname)
        try:
            if os.path.getmtime(fpath) >= cutoff_ts:
                recent_files.append(fpath)
        except OSError:
            pass

    if not recent_files:
        _referer_cache["data"] = {"referers": {}, "top_domains": []}
        _referer_cache["ts"] = now
        return _referer_cache["data"]

    try:
        cmd = ["zgrep", "-h", "-e", "master.m3u8", "-e", "/embed/"] + recent_files
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        for line in result.stdout.splitlines():
                # Filter by date in log line
                dm = date_re.search(line)
                if dm:
                    try:
                        d, m, y = dm.group(1).split("/")
                        log_date = f"{y}-{_month_map.get(m,'01')}-{d}"
                        if log_date < cutoff_date:
                            continue
                    except (ValueError, KeyError):
                        pass

                vm = vid_re.search(line)
                if not vm:
                    continue
                vid_id = vm.group(1) or vm.group(2)

                # Count views and daily trend
                video_views[vid_id] += 1
                if dm:
                    daily_hits[log_date] += 1

                rm = ref_re.search(line.rstrip())
                if not rm:
                    continue
                ref = rm.group(1)
                if not ref or ref == "-":
                    continue

                try:
                    domain = ref.split("//", 1)[1].split("/")[0].split(":")[0] if "//" in ref else ref
                except (IndexError, ValueError):
                    domain = ref

                if domain not in REFERER_IGNORE_DOMAINS and not any(p in domain for p in ignore_patterns):
                    referer_domains[vid_id].add(domain)
                    global_domain_counts[domain] += 1
                    clean_url = ref.split("?")[0].rstrip("/")
                    if clean_url.startswith("http://"):
                        clean_url = "https://" + clean_url[7:]
                    referer_urls[vid_id].add(clean_url)
    except Exception as exc:
        logger.warning("Error reading NPM logs: %s", exc)

    per_video = {
        vid: {
            "domains": sorted(referer_domains[vid]),
            "urls": sorted(referer_urls[vid]),
        }
        for vid in referer_domains
    }
    top_domains = sorted(global_domain_counts.items(), key=lambda x: -x[1])
    trend = sorted([{"date": d, "hits": h} for d, h in daily_hits.items()], key=lambda x: x["date"])
    response = {
        "referers": per_video,
        "top_domains": [{"domain": d, "hits": h} for d, h in top_domains],
        "views": dict(video_views),
        "trend": trend,
    }
    _referer_cache["data"] = response
    _referer_cache["ts"] = now

    return response
