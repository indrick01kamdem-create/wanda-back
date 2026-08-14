from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.history import RideHistoryRead
from app.schemas.ride import (
    ChatMessageCreate,
    ChatMessageRead,
    CreateRideRequest,
    RideEstimateRequest,
    RideEstimateResponse,
    RideRatingRequest,
    RideCancelRequest,
    RideRead,
    RideShareResponse,
    RideLocationUpdateRequest,
)
from app.services.pricing import PricingService
from app.services.ride import RideService
from app.services.settings import SettingsService

router = APIRouter(prefix="/rides", tags=["rides"])


@router.post("/estimate", response_model=ApiResponse[RideEstimateResponse])
@handle_exceptions
async def estimate(
    body: RideEstimateRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = await SettingsService(db).get()
    result = await PricingService().estimate(
        body.pickup.lat,
        body.pickup.lng,
        body.destination.lat,
        body.destination.lng,
        body.ride_class_id,
        settings,
    )
    return ApiResponse(data=RideEstimateResponse(**result))


@router.post("", response_model=ApiResponse[RideRead], status_code=201)
@handle_exceptions
async def create_ride(
    body: CreateRideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).create(current_user, body)
    # Tentative de dispatch immédiat
    await RideService(db).dispatch(ride)
    await db.refresh(ride)
    return ApiResponse(message="Course créée", data=RideRead.model_validate(ride))


@router.get("", response_model=ApiResponse[list[RideRead]])
@handle_exceptions
async def list_rides(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rides = await RideService(db).list_for_user(current_user)
    return ApiResponse(data=[RideRead.model_validate(r) for r in rides])


@router.get("/history", response_model=ApiResponse[list[RideHistoryRead]])
@handle_exceptions
async def list_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await RideService(db).history_for_user(current_user.id)
    return ApiResponse(data=[RideHistoryRead.model_validate(h) for h in history])


@router.get("/{ride_id}", response_model=ApiResponse[RideRead])
@handle_exceptions
async def get_ride(
    ride_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).get(ride_id, current_user)
    return ApiResponse(data=RideRead.model_validate(ride))


@router.post("/{ride_id}/accept", response_model=ApiResponse[RideRead])
@handle_exceptions
async def accept_ride(
    ride_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).accept(ride_id, current_user)
    return ApiResponse(message="Course acceptée", data=RideRead.model_validate(ride))


@router.post("/{ride_id}/status", response_model=ApiResponse[RideRead])
@handle_exceptions
async def update_ride_status(
    ride_id: str,
    status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).update_status(ride_id, current_user, status)
    return ApiResponse(data=RideRead.model_validate(ride))


@router.post("/{ride_id}/cancel", response_model=ApiResponse[RideRead])
@handle_exceptions
async def cancel_ride(
    ride_id: str,
    body: RideCancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).cancel(ride_id, current_user, body.reason)
    return ApiResponse(message="Course annulée", data=RideRead.model_validate(ride))


@router.post("/{ride_id}/rate", response_model=ApiResponse[RideRead])
@handle_exceptions
async def rate_ride(
    ride_id: str,
    body: RideRatingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ride = await RideService(db).rate(ride_id, current_user, body.passenger_rating, body.passenger_praise)
    return ApiResponse(message="Merci pour votre évaluation", data=RideRead.model_validate(ride))


@router.post("/{ride_id}/location", response_model=ApiResponse)
@handle_exceptions
async def push_location(
    ride_id: str,
    body: RideLocationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await RideService(db).push_location(ride_id, current_user, body.lat, body.lng)
    return ApiResponse(message="Position envoyée")


@router.post("/{ride_id}/chat", response_model=ApiResponse[ChatMessageRead])
@handle_exceptions
async def send_chat(
    ride_id: str,
    body: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = await RideService(db).send_chat(ride_id, current_user, body.text)
    return ApiResponse(data=ChatMessageRead.model_validate(message))


@router.get("/{ride_id}/chat", response_model=ApiResponse[list[ChatMessageRead]])
@handle_exceptions
async def get_chat(
    ride_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await RideService(db).chat_history(ride_id, current_user)
    return ApiResponse(data=[ChatMessageRead.model_validate(m) for m in messages])


@router.post("/{ride_id}/share", response_model=ApiResponse[RideShareResponse])
@handle_exceptions
async def create_share(
    ride_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    share = await RideService(db).create_share_token(ride_id, current_user)
    return ApiResponse(
        data=RideShareResponse(token=share.token, status="created"),
    )


@router.get("/share/{token}", response_model=ApiResponse[RideShareResponse])
@handle_exceptions
async def get_share(token: str, db: AsyncSession = Depends(get_db)):
    data = await RideService(db).get_share_status(token)
    return ApiResponse(data=RideShareResponse(**data))
