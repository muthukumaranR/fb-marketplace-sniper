from fastapi import APIRouter, HTTPException
from loguru import logger

from backend.models import PriceEstimate
from backend.pricer import get_fair_price

router = APIRouter(tags=["prices"])


@router.get("/prices/{item_name}", response_model=PriceEstimate)
async def get_price(item_name: str, force_refresh: bool = False):
    try:
        return await get_fair_price(item_name, force_refresh=force_refresh)
    except Exception as e:
        logger.error("Price estimation failed for '{}': {}", item_name, e)
        raise HTTPException(
            status_code=503,
            detail=f"Could not estimate price: {e}",
        )
