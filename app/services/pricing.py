from __future__ import annotations

import logging
from math import asin, cos, pi, sin, sqrt

from app.core.config import settings
from app.models.settings import SystemSettings

logger = logging.getLogger(__name__)

# Fallback pricing (identique à src/data.ts du front Wanda)
DEFAULT_CLASS_RATES: dict[str, dict] = {
    "okada": {"baseFare": 250, "perKm": 80, "label": "Okada"},
    "keke": {"baseFare": 300, "perKm": 100, "label": "Keke"},
    "ecoride": {"baseFare": 1500, "perKm": 250, "label": "EcoRide"},
    "comfort": {"baseFare": 3000, "perKm": 400, "label": "Comfort"},
}

EARTH_RADIUS_KM = 6371.0


def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    p = pi / 180
    dlat = (b_lat - a_lat) * p
    dlng = (b_lng - a_lng) * p
    h = (
        sin(dlat / 2) ** 2
        + cos(a_lat * p) * cos(b_lat * p) * sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


class PricingService:
    """
    Tarification Wanda :
      fare = (baseFare + perKm × distance) × surgeMultiplier
    Le multiplicateur surge vient du SystemSettings (défaut 1.0).
    """

    async def estimate(
        self,
        pickup_lat: float,
        pickup_lng: float,
        dest_lat: float,
        dest_lng: float,
        ride_class_id: str,
        settings_row: SystemSettings | None,
    ) -> dict:
        distance = haversine_km(pickup_lat, pickup_lng, dest_lat, dest_lng)
        rates = dict(DEFAULT_CLASS_RATES)
        if settings_row and settings_row.class_rates:
            rates.update(settings_row.class_rates)

        rate = rates.get(ride_class_id, DEFAULT_CLASS_RATES["ecoride"])
        surge = settings_row.surge_multiplier if settings_row else settings.surge_multiplier
        base_fare = int(rate["baseFare"])
        per_km = int(rate["perKm"])
        fare = int(round((base_fare + per_km * distance) * surge))
        duration_min = int(round(distance / 25 * 60))  # ~25 km/h moyen

        return {
            "ride_class_id": ride_class_id,
            "distance_km": round(distance, 2),
            "base_fare": base_fare,
            "per_km": per_km,
            "fare": fare,
            "surge_multiplier": surge,
            "estimated_duration_min": duration_min,
        }


async def get_pricing_settings(db) -> SystemSettings | None:
    from sqlalchemy import select

    row = (await db.execute(select(SystemSettings).limit(1))).scalar_one_or_none()
    return row
