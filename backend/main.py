from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend import db
from backend.routers import listings, prices, scans, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("MarketSwipe API started")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="MarketSwipe",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(watchlist.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(prices.router, prefix="/api")


# Facebook's image CDNs. Thumbnails are the only thing this proxy exists for,
# so the allowlist is exact-suffix — no user-controlled host reaches httpx.
ALLOWED_IMAGE_HOST_SUFFIXES = (".fbcdn.net", ".facebook.com", ".cdninstagram.com")
MAX_IMAGE_REDIRECTS = 3


def is_allowed_image_url(url: str) -> bool:
    """Allow only https URLs on Facebook's image CDNs."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(
        host == suffix.lstrip(".") or host.endswith(suffix)
        for suffix in ALLOWED_IMAGE_HOST_SUFFIXES
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/setup-status")
async def setup_status():
    """Return setup checklist status for onboarding UI."""
    from backend.config import settings

    watch_items = await db.get_watch_items()
    scans = await db.get_scans(limit=1)
    return {
        "fb_logged_in": settings.fb_state_resolved.exists(),
        "has_watch_items": len(watch_items) > 0,
        "has_scans": len(scans) > 0,
        "has_email": bool(settings.smtp_user and settings.smtp_pass),
        # Exposed so the UI can show a real next-scan countdown instead of
        # assuming the default interval.
        "scan_interval_minutes": settings.scan_interval_minutes,
        # The global notification floor. Per-item thresholds do not exist yet,
        # so the Watchlist slider reflects this rather than faking per-item state.
        "notify_min_relevance": settings.notify_min_relevance,
    }


@app.get("/api/proxy-image")
async def proxy_image(url: str):
    """
    Proxy Facebook thumbnails, which refuse to load cross-origin from the SPA.

    Restricted to Facebook's CDN: this endpoint is unauthenticated, so an
    unconstrained fetcher would let anyone reach cloud metadata, localhost, and
    anything else reachable from the container, and read the response body.
    """
    import httpx
    from fastapi.responses import Response

    if not is_allowed_image_url(url):
        logger.warning("Blocked image proxy request for disallowed URL: {!r}", url[:200])
        return Response(status_code=400)

    try:
        # Redirects are followed manually so each hop is checked against the
        # allowlist — otherwise an allowed host can 302 anywhere it likes.
        async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
            current = url
            for _ in range(MAX_IMAGE_REDIRECTS):
                resp = await client.get(current, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://www.facebook.com/",
                })
                if resp.status_code not in (301, 302, 303, 307, 308):
                    break
                current = str(resp.headers.get("location", ""))
                if not is_allowed_image_url(current):
                    logger.warning("Blocked image proxy redirect to: {!r}", current[:200])
                    return Response(status_code=400)
            else:
                return Response(status_code=502)

            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.warning("Image proxy got non-image content-type: {!r}", content_type[:80])
                return Response(status_code=502)

            return Response(
                content=resp.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        return Response(status_code=502)


# Serve frontend static files in production (Docker)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    _dist_root = _frontend_dist.resolve()

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        index = _dist_root / "index.html"
        # Containment check: an encoded traversal (`..%2f`) survives URL decoding
        # and would otherwise serve any file the process can read.
        try:
            candidate = (_dist_root / path).resolve()
            candidate.relative_to(_dist_root)
        except (ValueError, OSError):
            logger.warning("Blocked path traversal attempt: {!r}", path[:200])
            return FileResponse(index)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
