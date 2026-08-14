from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.driver import (
    DriverEditRequest,
    DriverLocationUpdate,
    DriverProfileRead,
    OnlineDriverRead,
)
from app.services.driver import DriverService

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/online", response_model=ApiResponse[list[OnlineDriverRead]])
@handle_exceptions
async def online_drivers(db: AsyncSession = Depends(get_db)):
    profiles = await DriverService(db).list_online()
    return ApiResponse(
        data=[
            OnlineDriverRead(
                user_id=p.user_id,
                name=p.user.name if p.user else "",
                phone=p.user.phone if p.user else None,
                vehicle_type=p.vehicle_type,
                vehicle_model=p.vehicle_model,
                vehicle_color=p.vehicle_color,
                vehicle_plate=p.vehicle_plate,
                rating=p.rating,
                lat=p.lat,
                lng=p.lng,
            )
            for p in profiles
        ]
    )


@router.get("/me", response_model=ApiResponse[DriverProfileRead])
@handle_exceptions
async def my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await DriverService(db).get_or_create(current_user)
    return ApiResponse(data=DriverProfileRead.model_validate(profile))


@router.patch("/me", response_model=ApiResponse[DriverProfileRead])
@handle_exceptions
async def edit_profile(
    body: DriverEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DriverService(db)
    profile = await service.get_or_create(current_user)
    profile = await service.edit_profile(profile, body)
    return ApiResponse(data=DriverProfileRead.model_validate(profile))


@router.post("/location", response_model=ApiResponse[DriverProfileRead])
@handle_exceptions
async def update_location(
    body: DriverLocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DriverService(db)
    await service.get_or_create(current_user)
    profile = await service.update_location(current_user.id, body)
    return ApiResponse(data=DriverProfileRead.model_validate(profile))
