from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend import db
from backend.routers import listings, prices, scans, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("FB Marketplace Sniper API started")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="FB Marketplace Sniper",
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
    }


@app.get("/api/proxy-image")
async def proxy_image(url: str):
    """Proxy external images (FB thumbnails) to bypass referrer/auth restrictions."""
    import httpx
    from fastapi.responses import Response

    if not url:
        return Response(status_code=400)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.facebook.com/",
            })
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        return Response(status_code=502)


# Serve frontend static files in production (Docker)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = _frontend_dist / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")
