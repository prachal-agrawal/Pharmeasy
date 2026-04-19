"""Delivery ETA routes.

Public endpoints (no authentication required) for estimating delivery time
based on the customer's GPS coordinates or PIN code.

Routes:
    GET /api/delivery/eta?lat=<float>&lng=<float>  — estimate by GPS coords
    GET /api/delivery/check?pin=<6-digit>           — estimate by PIN code
"""

import logging
import re
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from delhivery_service import estimate_by_coordinates, estimate_by_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/delivery", tags=["Delivery"])

_PIN_RE = re.compile(r"^\d{6}$")


@router.get("/eta")
async def delivery_eta_by_coords(
    lat: float = Query(..., description="Customer latitude",  ge=-90,  le=90),
    lng: float = Query(..., description="Customer longitude", ge=-180, le=180),
) -> dict:
    """Estimate delivery ETA for a customer at the given GPS coordinates.

    No authentication required.  Reverse-geocodes the coordinates using the
    free OpenStreetMap Nominatim API and returns an estimated delivery window
    based on straight-line distance from the warehouse.

    Args:
        lat: Customer's latitude (WGS-84 decimal degrees).
        lng: Customer's longitude (WGS-84 decimal degrees).

    Returns:
        A dict containing::

            {
              "city": "New Delhi",
              "state": "Delhi",
              "pincode": "110001",
              "distance_km": 182.3,
              "min_days": 1,
              "max_days": 1,
              "label": "Next-day delivery",
              "estimated_delivery_date": "17 Apr 2026",
              "message": "Next-day delivery to New Delhi, Delhi 🚚 — arrives by 17 Apr",
              "cod_available": true
            }

    Example::

        GET /api/delivery/eta?lat=28.6139&lng=77.2090
    """
    logger.info("Delivery ETA request for coords lat=%.4f lng=%.4f", lat, lng)
    estimate = await estimate_by_coordinates(lat, lng)
    return asdict(estimate)


@router.get("/check")
async def delivery_eta_by_pin(
    pin: str = Query(..., description="6-digit Indian PIN code", min_length=6, max_length=6),
) -> dict:
    """Estimate delivery ETA for a 6-digit Indian PIN code.

    No authentication required.  Forward-geocodes the PIN code using
    OpenStreetMap Nominatim and returns an estimated delivery window.

    Args:
        pin: 6-digit Indian PIN code.

    Returns:
        Same shape as ``/eta`` endpoint.

    Raises:
        HTTPException 422: If the PIN code is not exactly 6 digits.

    Example::

        GET /api/delivery/check?pin=110001
    """
    if not _PIN_RE.match(pin):
        raise HTTPException(status_code=422, detail="PIN code must be exactly 6 digits.")

    logger.info("Delivery ETA request for pin=%s", pin)
    estimate = await estimate_by_pin(pin)
    return asdict(estimate)
