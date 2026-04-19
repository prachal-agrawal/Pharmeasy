"""Location-based delivery ETA service.

Estimates delivery time based on straight-line distance between the
store/warehouse and the customer's location.  No external delivery-partner
API key is required — geocoding uses the free OpenStreetMap Nominatim API.

Flow:
    1. Receive destination as either (lat, lng) or a 6-digit PIN code.
    2. If PIN code is supplied, resolve it to (lat, lng) via Nominatim.
    3. Calculate Haversine distance from the warehouse coordinates.
    4. Map distance to a delivery window (same-day / 1 day / 2-3 days / 4-5 days).

Typical usage::

    est = await estimate_by_coordinates(28.6139, 77.2090)   # New Delhi
    print(est.message)  # "Delivery to New Delhi, DL in 1–2 days 🚚"

    est = await estimate_by_pin("110001")
    print(est.estimated_delivery_date)  # "20 Apr 2026"
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH  = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "MathuraPharmeasy/2.0 (pharmacy delivery ETA)"}

# Distance → (min_days, max_days, label)
_ETA_BANDS: list[tuple[float, int, int, str]] = [
    (500,  2, 3, "2–3 day delivery"),          # ≤ 500 km
    (1200, 3, 5, "3–5 day delivery"),          # 501–1200 km
    (float("inf"), 5, 7, "5–7 day delivery"),  # > 1200 km
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two lat/lon points.

    Args:
        lat1: Latitude of point 1 (degrees).
        lon1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lon2: Longitude of point 2 (degrees).

    Returns:
        Distance in kilometres (float).
    """
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi        = math.radians(lat2 - lat1)
    dlambda     = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _next_business_day(days: int) -> date:
    """Return the calendar date that is *days* business days from today.

    Args:
        days: Number of business days to advance (weekends skipped).

    Returns:
        A :class:`datetime.date`.
    """
    target = date.today()
    if days == 0:
        return target
    added = 0
    while added < days:
        target += timedelta(days=1)
        if target.weekday() < 5:
            added += 1
    return target


def _eta_from_distance(distance_km: float) -> tuple[int, int, str]:
    """Return (min_days, max_days, label) for a given distance in km.

    Args:
        distance_km: Straight-line distance to destination.

    Returns:
        Tuple of (min_days, max_days, label_string).
    """
    for threshold, mn, mx, label in _ETA_BANDS:
        if distance_km <= threshold:
            return mn, mx, label
    return 5, 7, "5–7 day delivery"


# ── Data class ───────────────────────────────────────────────────────────────

@dataclass
class DeliveryEstimate:
    """Result of a location-based delivery ETA calculation.

    Attributes:
        city: City / locality name resolved from coordinates or PIN.
        state: State name (may be empty if unavailable).
        pincode: PIN code (may be empty if only coordinates were provided).
        distance_km: Approximate straight-line distance from the warehouse.
        min_days: Lower bound of delivery window (calendar / business days).
        max_days: Upper bound of delivery window.
        label: Short window label e.g. "Next-day delivery".
        estimated_delivery_date: Formatted earliest delivery date string.
        message: Full human-readable message for display in the UI.
        cod_available: Always True for domestic India (no restrictions).
    """

    city:                    str
    state:                   str
    pincode:                 str
    distance_km:             float
    min_days:                int
    max_days:                int
    label:                   str
    estimated_delivery_date: str
    message:                 str
    cod_available:           bool = True


# ── Nominatim helpers ─────────────────────────────────────────────────────────

async def _reverse_geocode(lat: float, lng: float) -> dict:
    """Reverse-geocode lat/lng to address components via Nominatim.

    Args:
        lat: Latitude.
        lng: Longitude.

    Returns:
        Nominatim ``address`` sub-dict (empty dict on failure).
    """
    params = {"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1, "zoom": 14}
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=NOMINATIM_HEADERS) as client:
            resp = await client.get(NOMINATIM_REVERSE, params=params)
            resp.raise_for_status()
            return resp.json().get("address", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nominatim reverse-geocode failed for (%s, %s): %s", lat, lng, exc)
        return {}


async def _geocode_pin(pin: str) -> Optional[tuple[float, float, dict]]:
    """Forward-geocode a 6-digit Indian PIN code to (lat, lng, address) via Nominatim.

    Args:
        pin: 6-digit Indian PIN code string.

    Returns:
        Tuple of (lat, lng, address_dict) or None on failure / no results.
    """
    params = {
        "country":    "India",
        "postalcode": pin,
        "format":     "jsonv2",
        "addressdetails": 1,
        "limit": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=NOMINATIM_HEADERS) as client:
            resp = await client.get(NOMINATIM_SEARCH, params=params)
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return None
            r = results[0]
            return float(r["lat"]), float(r["lon"]), r.get("address", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nominatim geocode failed for pin=%s: %s", pin, exc)
        return None


def _extract_city(addr: dict) -> str:
    """Extract the best available city name from a Nominatim address dict.

    Args:
        addr: Nominatim address component dictionary.

    Returns:
        City/locality string (may be empty).
    """
    return (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("county")
        or addr.get("suburb")
        or ""
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def estimate_by_coordinates(lat: float, lng: float) -> DeliveryEstimate:
    """Estimate delivery ETA for a customer at the given GPS coordinates.

    Reverse-geocodes the coordinates to obtain a human-readable city name,
    then computes distance from the warehouse and maps it to a delivery window.

    Args:
        lat: Customer's latitude.
        lng: Customer's longitude.

    Returns:
        A :class:`DeliveryEstimate` with ETA and location details.

    Example::

        est = await estimate_by_coordinates(28.6139, 77.2090)
        # est.message → "Next-day delivery to New Delhi, Delhi 🚚"
    """
    settings = get_settings()

    addr        = await _reverse_geocode(lat, lng)
    city        = _extract_city(addr)
    state       = addr.get("state", "")
    pincode     = addr.get("postcode", "")

    distance_km = _haversine_km(settings.WAREHOUSE_LAT, settings.WAREHOUSE_LNG, lat, lng)
    min_d, max_d, label = _eta_from_distance(distance_km)
    eta_date    = _next_business_day(min_d)

    location_str = city
    if state and city:
        location_str = f"{city}, {state}"
    elif state:
        location_str = state

    msg = f"Delivery to {location_str} in {min_d}–{max_d} days 🚚 — arrives by {eta_date.strftime('%d %b')}"

    return DeliveryEstimate(
        city=city,
        state=state,
        pincode=pincode,
        distance_km=round(distance_km, 1),
        min_days=min_d,
        max_days=max_d,
        label=label,
        estimated_delivery_date=eta_date.strftime("%d %b %Y"),
        message=msg,
        cod_available=True,
    )


async def estimate_by_pin(pin: str) -> DeliveryEstimate:
    """Estimate delivery ETA for a given 6-digit PIN code.

    Forward-geocodes the PIN via Nominatim, then delegates to
    :func:`estimate_by_coordinates`.  Falls back to a generic 3–5 day
    estimate when geocoding fails.

    Args:
        pin: 6-digit Indian PIN code.

    Returns:
        A :class:`DeliveryEstimate` with ETA and location details.

    Example::

        est = await estimate_by_pin("110001")
        print(est.estimated_delivery_date)  # "20 Apr 2026"
    """
    result = await _geocode_pin(pin)

    if result is None:
        # Couldn't geocode — return safe fallback
        logger.warning("Could not geocode pin=%s, returning default estimate", pin)
        eta = _next_business_day(3)
        return DeliveryEstimate(
            city="",
            state="",
            pincode=pin,
            distance_km=0.0,
            min_days=3,
            max_days=5,
            label="3–5 day delivery",
            estimated_delivery_date=eta.strftime("%d %b %Y"),
            message=f"Delivery in 3–5 days — arrives by {eta.strftime('%d %b')} 🚚",
            cod_available=True,
        )

    dest_lat, dest_lng, addr = result
    est = await estimate_by_coordinates(dest_lat, dest_lng)

    # Override pincode with the queried one (more reliable than reverse-geocoded value)
    est.pincode = pin
    return est
