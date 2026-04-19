# Delivery ETA — How It Works

> **`GET /api/delivery/eta`** and **`GET /api/delivery/check`**

---

## Overview

The delivery ETA feature shows customers how long an order will take to arrive,
based on the distance between the store (Mathura, UP) and the customer's
location. **No external delivery-partner API key is required.**

---

## End-to-End Flow

```
Browser (React)                     Backend (FastAPI)              OpenStreetMap
──────────────────────────────────────────────────────────────────────────────
1. Page loads
   │
   ├─ [if no PIN prop]
   │    navigator.geolocation
   │    .getCurrentPosition()
   │         │
   │         │  coords.latitude
   │         │  coords.longitude
   │         ▼
   │   deliveryAPI.etaByCoords(lat, lng)
   │         │
   │         │  GET /api/delivery/eta?lat=28.61&lng=77.20
   │         ▼
   │                              delivery_router.py
   │                              estimate_by_coordinates(lat, lng)
   │                                       │
   │                                       │  GET /reverse?lat=..&lon=..
   │                                       ├──────────────────────────────▶ Nominatim
   │                                       │                                (free OSM API)
   │                                       │◀─────────────────────────────
   │                                       │  { city, state, postcode }
   │                                       │
   │                                       │  Haversine distance
   │                                       │  (store ↔ customer)
   │                                       │
   │                                       │  Map distance → ETA band
   │                                       │  ≤500 km  → 2–3 days
   │                                       │  ≤1200 km → 3–5 days
   │                                       │  >1200 km → 5–7 days
   │                                       │
   │         { city, state, distance_km,   │
   │           min_days, max_days,         │
   │           estimated_delivery_date,    │
   │           message, cod_available }    │
   │◀──────────────────────────────────────┘
   │
   └─ Render result card in DeliveryEstimateWidget

   ── OR ──

   ├─ [if PIN prop / user types PIN]
   │   deliveryAPI.etaByPin("110001")
   │         │
   │         │  GET /api/delivery/check?pin=110001
   │         ▼
   │                              delivery_router.py
   │                              estimate_by_pin("110001")
   │                                       │
   │                                       │  GET /search?postalcode=110001
   │                                       ├──────────────────────────────▶ Nominatim
   │                                       │◀─────────────────────────────
   │                                       │  { lat, lng, address }
   │                                       │
   │                                       └─ estimate_by_coordinates(lat, lng)
   │                                            (same path as GPS flow above)
   │◀──────────────────────────────────────────────────────────────────────
   └─ Render result card
```

---

## Step 1 — Frontend gets the coordinates

**File:** `frontend/src/components/DeliveryEstimateWidget.jsx`

On mount the widget calls `handleDetectLocation()` automatically:

```js
// runs once on mount if no PIN is pre-supplied
useEffect(() => {
  if (!pinProp) handleDetectLocation()
}, [])
```

Inside `handleDetectLocation`:

```js
navigator.geolocation.getCurrentPosition(
  async ({ coords }) => {
    // coords.latitude  — e.g. 28.6139
    // coords.longitude — e.g. 77.2090
    const { data } = await deliveryAPI.etaByCoords(
      coords.latitude,
      coords.longitude
    )
    setResult(data)
  },
  (err) => { /* show friendly error, fall back to PIN input */ },
  { timeout: 10_000, maximumAge: 60_000 }
)
```

The browser asks the user for location permission once. If denied, an error
message is shown and the manual PIN input is offered instead.

---

## Step 2 — Frontend calls the API

**File:** `frontend/src/utils/api.js`

```js
export const deliveryAPI = {
  // GPS path
  etaByCoords: (lat, lng) =>
    api.get('/delivery/eta', { params: { lat, lng } }),

  // PIN path
  etaByPin: (pin) =>
    api.get('/delivery/check', { params: { pin } }),
}
```

Both are public endpoints — **no JWT token needed**.

---

## Step 3 — Backend receives the request

**File:** `backend/routes/delivery_router.py`

### GPS endpoint

```
GET /api/delivery/eta?lat=28.6139&lng=77.2090
```

FastAPI validates that `lat` is in `[-90, 90]` and `lng` in `[-180, 180]`,
then calls `estimate_by_coordinates(lat, lng)`.

### PIN endpoint

```
GET /api/delivery/check?pin=110001
```

FastAPI validates the 6-digit regex, then calls `estimate_by_pin(pin)`.

---

## Step 4 — Backend calculates ETA

**File:** `backend/delhivery_service.py`

### GPS path — `estimate_by_coordinates(lat, lng)`

1. **Reverse-geocode** — calls Nominatim to turn `(lat, lng)` into a human
   address (`city`, `state`, `postcode`):

   ```
   GET https://nominatim.openstreetmap.org/reverse
       ?lat=28.6139&lon=77.2090&format=jsonv2&addressdetails=1
   ```

2. **Haversine distance** — straight-line km between the store and customer:

   ```python
   # Store: Mathura, UP → 27.4924° N, 77.6737° E  (set in config.py)
   distance_km = _haversine_km(
       WAREHOUSE_LAT, WAREHOUSE_LNG,   # 27.4924, 77.6737
       customer_lat,  customer_lng
   )
   ```

3. **Map to ETA band:**

   | Distance from store | Delivery window |
   |---------------------|-----------------|
   | ≤ 500 km            | **2–3 days**    |
   | 501 – 1200 km       | **3–5 days**    |
   | > 1200 km           | **5–7 days**    |

4. **Next business day** — skips Saturdays and Sundays when computing the
   earliest arrival date.

### PIN path — `estimate_by_pin(pin)`

1. **Forward-geocode** — calls Nominatim to turn the PIN code into `(lat, lng)`:

   ```
   GET https://nominatim.openstreetmap.org/search
       ?country=India&postalcode=110001&format=jsonv2&limit=1
   ```

2. Delegates to `estimate_by_coordinates(lat, lng)` — same logic as above.

3. If Nominatim returns no results, falls back to a generic 3–5 day estimate.

---

## Step 5 — API response shape

Both endpoints return the same JSON:

```json
{
  "city": "New Delhi",
  "state": "Delhi",
  "pincode": "110001",
  "distance_km": 182.3,
  "min_days": 2,
  "max_days": 3,
  "label": "2–3 day delivery",
  "estimated_delivery_date": "19 Apr 2026",
  "message": "Delivery to New Delhi, Delhi in 2–3 days 🚚 — arrives by 19 Apr",
  "cod_available": true
}
```

---

## Step 6 — Frontend renders the result

Back in `DeliveryEstimateWidget.jsx`, `setResult(data)` triggers a re-render.
The widget shows:

- **Main message** — `result.message`
- **City + state** — `result.city`, `result.state`
- **Distance chip** — `~182.3 km from store`
- **COD badge** — always "Available"
- **Delivery window badge** — `2–3 day delivery · by 19 Apr 2026`

In **compact mode** (used in the checkout Review step), only the one-line
message is shown.

---

## Where the widget is used

| Location | Mode | Trigger |
|---|---|---|
| `Home.jsx` — below hero | Full | Auto-detect on page load |
| `Checkout.jsx` — Address step | Full | Auto-fires when address card is selected (uses saved PIN) |
| `Checkout.jsx` — Review step | Compact | Same saved PIN |

---

## Configuration

`backend/config.py` / `.env`:

```env
# Warehouse / store coordinates (defaults to Mathura, UP)
WAREHOUSE_LAT=27.4924
WAREHOUSE_LNG=77.6737
```

Change these values if the store moves — all ETA calculations update automatically.

---

## External dependencies

| Service | Purpose | Cost | Key needed |
|---|---|---|---|
| [OpenStreetMap Nominatim](https://nominatim.org) | Reverse & forward geocoding | Free | ❌ No |
| Browser Geolocation API | Get user's GPS coordinates | Free | ❌ No |

Nominatim usage is subject to their [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
(max 1 req/sec, must send a descriptive `User-Agent` — already set in the service).
