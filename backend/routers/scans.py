from fastapi import APIRouter, HTTPException

from backend import db
from backend.config import settings
from backend.models import ScanResult

router = APIRouter(tags=["scans"])


@router.get("/scans", response_model=list[ScanResult])
async def list_scans(limit: int = 20):
    return await db.get_scans(limit)


@router.get("/scans/{scan_id}", response_model=ScanResult)
async def get_scan(scan_id: int):
    scan = await db.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.post("/scans/trigger", response_model=ScanResult)
async def trigger_scan():
    from backend.tasks import scan_all

    scan = await db.create_scan()
    scan_all.delay(scan["id"])
    return scan


@router.get("/auth/fb-status")
async def fb_status():
    """Check if Facebook session is saved."""
    return {"logged_in": settings.fb_state_resolved.exists()}
