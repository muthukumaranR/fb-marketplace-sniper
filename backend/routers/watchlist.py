from fastapi import APIRouter, HTTPException
from loguru import logger

from backend import db
from backend.config import settings
from backend.models import WatchItem, WatchItemCreate

router = APIRouter(tags=["watchlist"])


@router.post("/watchlist", response_model=WatchItem)
async def add_watch_item(item: WatchItemCreate):
    location = item.location or settings.default_location
    radius = item.radius or settings.default_radius
    row = await db.add_watch_item(item.name, item.max_price, location, radius)
    logger.info("Watch item added: {}", item.name)
    return row


@router.get("/watchlist", response_model=list[WatchItem])
async def list_watch_items():
    return await db.get_watch_items()


@router.delete("/watchlist/{item_id}")
async def remove_watch_item(item_id: int):
    deleted = await db.delete_watch_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watch item not found")
    return {"deleted": True}
