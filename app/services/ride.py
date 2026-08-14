from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.driver import APPROVAL_APPROVED, DRIVER_STATUS_DRIVING, DriverProfile
from app.models.history import HISTORY_COMPLETED, RideHistory
from app.models.ride import (
    RIDE_STATUS_ARRIVING,
    RIDE_STATUS_CANCELLED,
    RIDE_STATUS_COMPLETED,
    RIDE_STATUS_DRIVER_FOUND,
    RIDE_STATUS_IN_PROGRESS,
    RIDE_STATUS_SEARCHING,
    ChatMessage,
    Ride,
    RideLocationUpdate,
    RideShareToken,
)
from app.models.user import USER_ROLE_DRIVER, User
from app.models.transaction import WalletTransaction
from app.models.wallet import Wallet
from app.schemas.ride import CreateRideRequest
from app.services.driver import DriverService
from app.services.pricing import PricingService, haversine_km
from app.services.settings import SettingsService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)

SHARE_TOKEN_TTL_HOURS = 24


class RideService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Booking ────────────────────────────────────────────────────────────────

    async def create(self, user: User, data: CreateRideRequest) -> Ride:
        settings_row = await SettingsService(self._db).get()
        pricing = await PricingService().estimate(
            data.pickup.lat,
            data.pickup.lng,
            data.destination.lat,
            data.destination.lng,
            data.ride_class_id,
            settings_row,
        )
        fare = pricing["fare"]

        # Points redeemed: 1 pt = 100 FCFA, débité du wallet à la création
        wallet = await WalletService(self._db).get_or_create(user.id)
        points_redeemed = 0
        if data.points_redeemed > 0:
            points_redeemed = min(data.points_redeemed, wallet.points)
            discount_fcfa = points_redeemed * 100
            fare = max(0, fare - discount_fcfa)
            wallet.points -= points_redeemed

        # Wallet paiement : vérifier le solde et débiter immédiatement
        wallet_paid = False
        if data.payment_method == "wallet":
            if wallet.balance < fare:
                raise BadRequestException(
                    f"Solde insuffisant : {wallet.balance} FCFA (course : {fare} FCFA). "
                    "Rechargez votre portefeuille ou payez autrement."
                )
            wallet.balance -= fare
            wallet_paid = True

        commission_rate = settings_row.commission_rate
        platform_commission = int(round(fare * commission_rate / 100))
        driver_net = fare - platform_commission

        ride = Ride(
            passenger_id=user.id,
            passenger_name=user.name,
            passenger_phone=user.phone,
            pickup=data.pickup.model_dump(),
            destination=data.destination.model_dump(),
            ride_class_id=data.ride_class_id,
            fare=fare,
            base_fare=pricing["base_fare"],
            distance_km=pricing["distance_km"],
            surge_multiplier=pricing["surge_multiplier"],
            tip_amount=data.tip_amount,
            points_redeemed=points_redeemed,
            payment_method=data.payment_method,
            status=RIDE_STATUS_SEARCHING,
            commission_rate=commission_rate,
            platform_commission=platform_commission,
            driver_net_earnings=driver_net,
        )
        self._db.add(ride)
        await self._db.flush()

        if wallet_paid:
            self._db.add(
                WalletTransaction(
                    wallet_id=wallet.id,
                    user_id=user.id,
                    type="ride_payment",
                    amount=-fare,
                    carrier="wallet",
                    status="success",
                    ride_id=ride.id,
                )
            )

        await self._db.commit()
        await self._db.refresh(ride)
        return ride

    # ── Dispatch ───────────────────────────────────────────────────────────────

    async def dispatch(self, ride: Ride) -> DriverProfile | None:
        """Tente d'assigner un chauffeur proche (mode recherche simple)."""
        driver = await DriverService(self._db).find_nearby_driver(
            ride.pickup.get("lat", 0), ride.pickup.get("lng", 0), ride.ride_class_id
        )
        if driver is not None:
            ride.driver_id = driver.user_id
            ride.status = RIDE_STATUS_DRIVER_FOUND
            driver.status = "heading_to_pickup"
            await self._db.commit()
        return driver

    async def accept(self, ride_id: str, driver: User) -> Ride:
        ride = await self._get_ride(ride_id)
        if driver.role != USER_ROLE_DRIVER:
            raise ForbiddenException("Seul un chauffeur peut accepter une course")

        profile = await DriverService(self._db).get_by_user_id(driver.id)
        if profile.approval_status != APPROVAL_APPROVED:
            raise ForbiddenException("Profil chauffeur non approuvé")

        if ride.status == RIDE_STATUS_SEARCHING:
            ride.driver_id = driver.id
            ride.status = RIDE_STATUS_DRIVER_FOUND
            profile.status = DRIVER_STATUS_DRIVING
        elif ride.status == RIDE_STATUS_DRIVER_FOUND and ride.driver_id == driver.id:
            # Déjà assigné à ce chauffeur (dispatch automatique) — simple confirmation.
            pass
        else:
            raise BadRequestException("Cette course n'est plus disponible")

        await self._db.commit()
        await self._db.refresh(ride)
        return ride

    async def update_status(self, ride_id: str, user: User, status: str) -> Ride:
        ride = await self._get_ride(ride_id)
        is_participant = ride.passenger_id == user.id or ride.driver_id == user.id
        if not is_participant:
            raise ForbiddenException("Cette course ne vous est pas assignée")

        allowed = {
            RIDE_STATUS_ARRIVING,
            RIDE_STATUS_IN_PROGRESS,
            RIDE_STATUS_COMPLETED,
            RIDE_STATUS_CANCELLED,
        }
        if status not in allowed:
            raise BadRequestException(f"Transition invalide : {status}")

        ride.status = status

        if status == RIDE_STATUS_COMPLETED:
            await self._complete(ride)

        if status in (RIDE_STATUS_COMPLETED, RIDE_STATUS_CANCELLED):
            if ride.driver_id:
                profile = await DriverService(self._db).get_by_user_id(ride.driver_id)
                if profile:
                    profile.status = "idle"

        await self._db.commit()
        await self._db.refresh(ride)
        return ride

    async def _complete(self, ride: Ride) -> None:
        """À la fin de course : points, historique, commission, payout."""
        from app.models.transaction import TX_COMMISSION_DEBIT, TX_RIDE_PAYOUT

        wallet = await WalletService(self._db).get_or_create(ride.passenger_id)
        points_earned = 1 if ride.payment_method == "wallet" else 0
        wallet.points += points_earned
        ride.points_earned = points_earned

        # Payout chauffeur (fare brute) + commission plateforme.
        # Le chauffeur est d'abord crédité du montant plein de la course, puis
        # débité de la commission : net perçu = fare - platform_commission
        # (== ride.driver_net_earnings). Ne PAS créditer directement
        # driver_net_earnings puis débiter la commission par-dessus : cela
        # soustrairait la commission deux fois.
        if ride.driver_id:
            await WalletService(self._db).credit(
                ride.driver_id,
                ride.fare,
                TX_RIDE_PAYOUT,
                ride_id=ride.id,
            )
            # Commission (compte plateforme = super admin non requis pour phase 1)
            await WalletService(self._db).debit(
                ride.driver_id,
                ride.platform_commission,
                TX_COMMISSION_DEBIT,
                ride_id=ride.id,
            )

        # Historique passager
        driver_name = None
        if ride.driver_id:
            driver_user = await self._db.get(User, ride.driver_id)
            driver_name = driver_user.name if driver_user else None
        self._db.add(
            RideHistory(
                user_id=ride.passenger_id,
                ride_id=ride.id,
                pickup_name=ride.pickup.get("name", ""),
                dest_name=ride.destination.get("name", ""),
                pickup_lat=ride.pickup.get("lat"),
                pickup_lng=ride.pickup.get("lng"),
                dest_lat=ride.destination.get("lat"),
                dest_lng=ride.destination.get("lng"),
                fare=ride.fare,
                tip_amount=ride.tip_amount,
                payment_method=ride.payment_method,
                status=HISTORY_COMPLETED,
                vehicle_class=ride.ride_class_id,
                driver_name=driver_name,
                points_earned=points_earned,
                points_redeemed=ride.points_redeemed,
            )
        )

    async def cancel(self, ride_id: str, user: User, reason: str | None = None) -> Ride:
        ride = await self._get_ride(ride_id)
        is_participant = ride.passenger_id == user.id or ride.driver_id == user.id
        if not is_participant:
            raise ForbiddenException("Non autorisé")

        if ride.status in (RIDE_STATUS_COMPLETED, RIDE_STATUS_CANCELLED):
            raise BadRequestException("Course déjà terminée")

        # Remboursement wallet si déjà débité et non démarrée
        if (
            ride.payment_method == "wallet"
            and ride.status in (RIDE_STATUS_SEARCHING, RIDE_STATUS_DRIVER_FOUND)
            and ride.fare > 0
        ):
            await WalletService(self._db).credit(
                ride.passenger_id,
                ride.fare,
                "ride_payment_refund",
                carrier="wallet",
                ride_id=ride.id,
            )

        ride.status = RIDE_STATUS_CANCELLED
        ride.cancel_reason = reason
        ride.cancelled_by = "driver" if user.id == ride.driver_id else "passenger"

        if ride.driver_id:
            profile = await DriverService(self._db).get_by_user_id(ride.driver_id)
            profile.status = "idle"

        # Historique passager (cancelled)
        self._db.add(
            RideHistory(
                user_id=ride.passenger_id,
                ride_id=ride.id,
                pickup_name=ride.pickup.get("name", ""),
                dest_name=ride.destination.get("name", ""),
                fare=ride.fare,
                payment_method=ride.payment_method,
                status="cancelled",
                vehicle_class=ride.ride_class_id,
                points_earned=0,
                points_redeemed=ride.points_redeemed,
            )
        )

        await self._db.commit()
        await self._db.refresh(ride)
        return ride

    async def rate(self, ride_id: str, user: User, rating: int, praise: str | None) -> Ride:
        ride = await self._get_ride(ride_id)
        if ride.passenger_id != user.id:
            raise ForbiddenException("Seul le passager peut noter")
        if ride.status != RIDE_STATUS_COMPLETED:
            raise BadRequestException("Course non terminée")

        ride.passenger_rating = rating
        ride.passenger_praise = praise

        if ride.driver_id:
            profile = await DriverService(self._db).get_by_user_id(ride.driver_id)
            profile.rating = ((profile.rating * 0.9) + rating) if profile.rating else rating

        await self._db.commit()
        await self._db.refresh(ride)
        return ride

    # ── Live location / chat / share ──────────────────────────────────────────

    async def push_location(self, ride_id: str, driver: User, lat: float, lng: float) -> None:
        ride = await self._get_ride(ride_id)
        if ride.driver_id != driver.id:
            raise ForbiddenException("Non autorisé")
        self._db.add(
            RideLocationUpdate(ride_id=ride.id, lat=lat, lng=lng)
        )
        await self._db.commit()

    async def send_chat(self, ride_id: str, user: User, text: str) -> ChatMessage:
        ride = await self._get_ride(ride_id)
        is_participant = ride.passenger_id == user.id or ride.driver_id == user.id
        if not is_participant:
            raise ForbiddenException("Non autorisé")
        role = "passenger" if ride.passenger_id == user.id else "driver"
        message = ChatMessage(
            ride_id=ride.id, sender_id=user.id, sender_role=role, text=text
        )
        self._db.add(message)
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def chat_history(self, ride_id: str, user: User) -> list[ChatMessage]:
        ride = await self._get_ride(ride_id)
        is_participant = ride.passenger_id == user.id or ride.driver_id == user.id
        if not is_participant:
            raise ForbiddenException("Non autorisé")
        result = await self._db.execute(
            select(ChatMessage)
            .where(ChatMessage.ride_id == ride_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())

    async def create_share_token(self, ride_id: str, user: User) -> RideShareToken:
        ride = await self._get_ride(ride_id)
        if ride.passenger_id != user.id:
            raise ForbiddenException("Seul le passager peut partager sa course")
        token = secrets.token_urlsafe(32)
        share = RideShareToken(
            ride_id=ride.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SHARE_TOKEN_TTL_HOURS),
        )
        self._db.add(share)
        await self._db.commit()
        await self._db.refresh(share)
        return share

    async def get_share_status(self, token: str) -> dict:
        result = await self._db.execute(
            select(RideShareToken).where(RideShareToken.token == token)
        )
        share = result.scalar_one_or_none()
        if share is None:
            raise NotFoundException("Lien de partage invalide")

        if share.expires_at:
            expires = share.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                raise NotFoundException("Lien de partage expiré")

        ride = await self._get_ride(share.ride_id)
        driver_profile = None
        driver_name = None
        if ride.driver_id:
            driver_user = await self._db.get(User, ride.driver_id)
            if driver_user:
                driver_name = driver_user.name
            driver_profile = await self._get_driver_profile_if_any(ride.driver_id)

        latest_location = None
        result = await self._db.execute(
            select(RideLocationUpdate)
            .where(RideLocationUpdate.ride_id == ride.id)
            .order_by(RideLocationUpdate.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest:
            latest_location = {"lat": latest.lat, "lng": latest.lng}

        return {
            "token": token,
            "lat": latest_location["lat"] if latest_location else None,
            "lng": latest_location["lng"] if latest_location else None,
            "status": ride.status,
            "passenger_name": ride.passenger_name,
            "driver_name": driver_name,
            "vehicle_plate": driver_profile.vehicle_plate if driver_profile else None,
            "vehicle_type": driver_profile.vehicle_type if driver_profile else None,
            "vehicle_color": driver_profile.vehicle_color if driver_profile else None,
            "driver_rating": driver_profile.rating if driver_profile else None,
        }

    async def _get_driver_profile_if_any(self, driver_user_id: str) -> DriverProfile | None:
        try:
            return await DriverService(self._db).get_by_user_id(driver_user_id)
        except NotFoundException:
            return None

    # ── Read helpers ───────────────────────────────────────────────────────────

    async def get(self, ride_id: str, user: User) -> Ride:
        ride = await self._get_ride(ride_id)
        is_participant = ride.passenger_id == user.id or ride.driver_id == user.id
        if not is_participant:
            raise ForbiddenException("Non autorisé")
        return ride

    async def list_for_user(self, user: User, *, limit: int = 20, offset: int = 0) -> list[Ride]:
        stmt = (
            select(Ride)
            .where((Ride.passenger_id == user.id) | (Ride.driver_id == user.id))
            .order_by(Ride.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def history_for_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[RideHistory]:
        stmt = (
            select(RideHistory)
            .where(RideHistory.user_id == user_id)
            .order_by(RideHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _get_ride(self, ride_id: str) -> Ride:
        ride = await self._db.get(Ride, ride_id)
        if ride is None:
            raise NotFoundException("Course introuvable")
        return ride
