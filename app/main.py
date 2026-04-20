import os
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from db import wait_for_db, init_pool, close_pool, ensure_schema
import db
from helpers import (  # noqa: F401 — re-exported for backwards compat (tests)
    UPLOAD_DIR, HLS_DIR, APP_VERSION, MAX_ID,
    BRAND_NAME, PRODUCT_NAME, PUBLIC_BASE, LOGO_URL,
    FOOTER_LINKS, COPYRIGHT_TEXT, EXAMPLE_PAGE_URL,
    format_duration_mmss, format_local_dt, parse_streams,
    highlight_query_in_text, format_encoding_duration,
    validate_upload, copy_with_size_limit,
)
from i18n import (
    t, set_language, get_language, get_translations,
    SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE,
)

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(HLS_DIR, exist_ok=True)

    wait_for_db()
    init_pool()

    with db.pool.connection() as c:
        ensure_schema(c)

    # Cleanup old activity log entries (>90 days)
    with db.pool.connection() as c:
        c.execute("DELETE FROM activity_log WHERE ts < now() - INTERVAL '90 days'")

    logger.info("App started, DB pool ready.")
    yield

    close_pool()
    logger.info("App shut down, DB pool closed.")


# ---------------------------------------------------------------------
# App
# ---------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

def _parse_footer_links(s):
    if not s:
        return []
    links = []
    for part in s.split(","):
        if "|" in part:
            label, url = part.split("|", 1)
            links.append({"label": label.strip(), "url": url.strip()})
    return links

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.globals["app_version"] = APP_VERSION
templates.env.globals["brand_name"] = BRAND_NAME
templates.env.globals["product_name"] = PRODUCT_NAME
templates.env.globals["public_base"] = PUBLIC_BASE
templates.env.globals["logo_url"] = LOGO_URL
templates.env.globals["copyright_text"] = COPYRIGHT_TEXT
templates.env.globals["example_page_url"] = EXAMPLE_PAGE_URL
templates.env.globals["footer_links"] = _parse_footer_links(FOOTER_LINKS)
templates.env.globals["t"] = t
templates.env.globals["get_language"] = get_language
templates.env.globals["get_translations_json"] = lambda: json.dumps(
    get_translations(), ensure_ascii=False
)
templates.env.globals["supported_languages"] = SUPPORTED_LANGUAGES
templates.env.globals["default_language"] = DEFAULT_LANGUAGE
app.state.templates = templates

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ---------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            host = request.headers.get("host")
            # Allow requests with no origin/referer (e.g. server-to-server)
            if origin:
                origin_host = origin.split("://", 1)[-1].split("/")[0]
                if origin_host != host:
                    return StarletteResponse(status_code=403, content="CSRF rejected")
            elif referer:
                referer_host = referer.split("://", 1)[-1].split("/")[0]
                if referer_host != host:
                    return StarletteResponse(status_code=403, content="CSRF rejected")
        return await call_next(request)


class LanguageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lang = request.cookies.get("eyestream-lang", DEFAULT_LANGUAGE)
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        set_language(lang)
        response = await call_next(request)
        return response


class IDValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        for part in request.url.path.split("/"):
            if part.isdigit() and int(part) > MAX_ID:
                return StarletteResponse(status_code=400, content="Invalid ID")
        return await call_next(request)


app.add_middleware(IDValidationMiddleware)
app.add_middleware(LanguageMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------
# Routes (order matters for overlapping patterns)
# ---------------------------------------------------------------------

from routes.misc import router as router_misc
from routes.settings import router as router_settings
from routes.videos import router as router_videos

app.include_router(router_misc)
app.include_router(router_settings)
app.include_router(router_videos)


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "80")))
