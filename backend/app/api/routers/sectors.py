from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.sector import Sector
from app.schemas.sector import SectorOut

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("", response_model=list[SectorOut])
async def list_sectors(db: AsyncSession = Depends(get_db)):
    sectors = (
        await db.execute(select(Sector).where(Sector.is_active.is_(True)).order_by(Sector.name))
    ).scalars().all()
    return [SectorOut.model_validate(s) for s in sectors]
