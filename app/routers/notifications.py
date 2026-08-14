from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.settings import NotificationRead
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=ApiResponse[list[NotificationRead]])
@handle_exceptions
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notifications = await NotificationService(db).list_for_user(current_user)
    return ApiResponse(data=[NotificationRead.model_validate(n) for n in notifications])


@router.post("/{notification_id}/read", response_model=ApiResponse[NotificationRead])
@handle_exceptions
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notification = await NotificationService(db).mark_read(notification_id, current_user.id)
    return ApiResponse(data=NotificationRead.model_validate(notification))
