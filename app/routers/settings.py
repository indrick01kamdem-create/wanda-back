from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import handle_exceptions
from app.schemas.common import ApiResponse
from app.schemas.settings import SystemSettingsRead
from app.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=ApiResponse[SystemSettingsRead])
@handle_exceptions
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    """Réglages publics (tarifs, commission, promos) utilisés par l'app."""
    settings = await SettingsService(db).get()
    return ApiResponse(data=SystemSettingsRead.model_validate(settings))
