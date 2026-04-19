import json
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/medicines", tags=["Medicines"])


class FetchOnlineRequest(BaseModel):
    """Request body for the fetch-online endpoint.

    Attributes:
        q: Medicine name to search on 1mg (min 2 chars).
    """

    q: str


def _normalize_medicine_images(row: dict) -> dict:
    """Attach ``image_urls`` list and set ``image_url`` to the primary (first) image.

    Args:
        row: Medicine row that may contain ``image_urls`` (JSON/list) and/or legacy
            ``image_url``.

    Returns:
        Same row mutated for API responses.
    """
    raw = row.get("image_urls")
    urls: list[str] = []
    if raw is not None:
        if isinstance(raw, str):
            try:
                urls = json.loads(raw) if raw.strip() else []
            except (json.JSONDecodeError, TypeError):
                urls = []
        elif isinstance(raw, list):
            urls = [str(u).strip() for u in raw if u]
    legacy = (row.get("image_url") or "").strip() if row.get("image_url") else ""
    if not urls and legacy:
        urls = [legacy]
    row["image_urls"] = urls
    row["image_url"] = urls[0] if urls else None
    return row


def _parse(row: dict) -> dict:
    """Parse JSON string fields in a medicine row into Python lists.

    Args:
        row: Raw medicine row dict from the database.

    Returns:
        dict: Same row with ``side_effects`` and ``safety_points`` as lists,
            and normalized ``image_urls`` / ``image_url``.
    """
    for f in ("side_effects", "safety_points"):
        v = row.get(f)
        row[f] = json.loads(v) if isinstance(v, str) else (v or [])
    return _normalize_medicine_images(row)


@router.get("/categories")
def get_categories():
    """Return all medicine categories ordered by sort_order.

    Returns:
        list[dict]: Category rows.
    """
    with DB() as db:
        return db.fetchall("SELECT * FROM categories ORDER BY sort_order")


@router.get("")
def list_medicines(
    search:   Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort:     Optional[str] = Query("name"),
):
    """List active medicines with optional filtering and sorting.

    Search strategy (when ``search`` is provided):

    1. Every word in the query must appear in at least one of the four
       searchable fields: ``name``, ``brand``, ``salt_composition``, or
       ``description`` (product information).  This means a query like
       "paracetamol 500" is satisfied by a medicine that contains
       "paracetamol" somewhere and "500" somewhere across those fields.
    2. Results are ranked by **match priority** so that the most specific
       matches surface first:

       * Priority 1 — full query matches ``name``
       * Priority 2 — full query matches ``brand``
       * Priority 3 — full query matches ``salt_composition``
       * Priority 4 — full query matches ``description`` (product info)
       * Priority 5 — words are spread across multiple fields

    3. Within each priority tier the user-chosen ``sort`` order is applied
       as a secondary key.

    Args:
        search: Search string — matched against name, brand, salt_composition,
            and description via LIKE.
        category: Category slug to filter by.
        sort: Sort order — ``"name"`` (default), ``"price_asc"``, or
            ``"price_desc"``.  Applied as a secondary sort after the
            match-priority tier.

    Returns:
        list[dict]: Parsed medicine rows with aggregated pricing and stock.
    """
    _BASE_SQL = """
        SELECT m.*, c.name AS category_name,
               MIN(v.price) AS min_price, MAX(v.price) AS max_price,
               MIN(v.mrp)   AS min_mrp,
               COALESCE(SUM(v.stock), 0) AS total_stock
        FROM medicines m
        JOIN categories c ON m.category_id = c.id
        LEFT JOIN medicine_variants v ON v.medicine_id = m.id
        WHERE m.is_active = 1
    """
    # Secondary sort keys (used after match_priority in the search path and
    # as the sole ORDER BY in the no-search path).
    _SORT_SECONDARY = {
        "price_asc":  "min_price ASC",
        "price_desc": "min_price DESC",
    }
    _default_secondary = "m.name ASC"

    params: list = []

    if not search:
        sql = _BASE_SQL
        if category:
            sql += " AND c.slug=%s"
            params.append(category)
        secondary = _SORT_SECONDARY.get(sort, _default_secondary)
        sql += f" GROUP BY m.id ORDER BY {secondary}"
        with DB() as db:
            return [_parse(dict(r)) for r in db.fetchall(sql, params)]

    # Split query into individual words.  Each word must independently appear
    # in at least one of: name, brand, salt_composition, or description.
    words = [w for w in search.strip().split() if w]
    if not words:
        return []

    cat_clause = ""
    cat_params: list = []
    if category:
        cat_clause = " AND c.slug=%s"
        cat_params = [category]

    # WHERE: every word must match at least one of the four searchable fields.
    word_clauses = " ".join(
        "AND ("
        "LOWER(m.name) LIKE LOWER(%s) OR "
        "LOWER(m.brand) LIKE LOWER(%s) OR "
        "LOWER(COALESCE(m.salt_composition,'')) LIKE LOWER(%s) OR "
        "LOWER(COALESCE(m.description,'')) LIKE LOWER(%s)"
        ")"
        for _ in words
    )
    word_params: list = []
    for w in words:
        like_w = f"%{w}%"
        word_params.extend([like_w, like_w, like_w, like_w])

    # CASE expression: priority is determined by where the *full* search
    # string lands (name → brand → salt_composition → description → mixed).
    full_like = f"%{search.strip()}%"
    priority_case = (
        "CASE "
        "WHEN LOWER(m.name) LIKE LOWER(%s) THEN 1 "
        "WHEN LOWER(m.brand) LIKE LOWER(%s) THEN 2 "
        "WHEN LOWER(COALESCE(m.salt_composition,'')) LIKE LOWER(%s) THEN 3 "
        "WHEN LOWER(COALESCE(m.description,'')) LIKE LOWER(%s) THEN 4 "
        "ELSE 5 "
        "END AS match_priority"
    )
    priority_params = [full_like, full_like, full_like, full_like]

    secondary = _SORT_SECONDARY.get(sort, _default_secondary)

    sql1 = (
        f"SELECT m.*, c.name AS category_name, "
        f"MIN(v.price) AS min_price, MAX(v.price) AS max_price, "
        f"MIN(v.mrp) AS min_mrp, COALESCE(SUM(v.stock), 0) AS total_stock, "
        f"{priority_case} "
        f"FROM medicines m "
        f"JOIN categories c ON m.category_id = c.id "
        f"LEFT JOIN medicine_variants v ON v.medicine_id = m.id "
        f"WHERE m.is_active = 1 "
        f"{word_clauses} "
        f"{cat_clause} "
        f"GROUP BY m.id "
        f"ORDER BY match_priority ASC, {secondary}"
    )

    all_params = priority_params + word_params + cat_params
    with DB() as db:
        rows = db.fetchall(sql1, all_params)

    return [_parse(dict(r)) for r in rows]


def _fetch_medicine_cards(ids: list[int]) -> list[dict]:
    """Fetch full catalogue cards (with pricing) for a list of medicine IDs.

    Args:
        ids: List of medicine primary keys to fetch.

    Returns:
        List of parsed medicine dicts ordered by ``m.name``.
    """
    if not ids:
        return []
    placeholders = ",".join(["%s"] * len(ids))
    with DB() as db:
        rows = db.fetchall(
            f"""SELECT m.*, c.name AS category_name,
                       MIN(v.price) AS min_price, MIN(v.mrp) AS min_mrp,
                       COALESCE(SUM(v.stock), 0) AS total_stock
                FROM medicines m
                JOIN categories c ON c.id = m.category_id
                LEFT JOIN medicine_variants v ON v.medicine_id = m.id
                WHERE m.id IN ({placeholders})
                GROUP BY m.id
                ORDER BY m.name""",
            ids,
        )
    return [_parse(dict(r)) for r in rows]


@router.post("/fetch-online")
async def fetch_online_medicine(body: FetchOnlineRequest):
    """Search 1mg for a medicine name, insert ALL matching results, and return them.

    Flow:
    1. Validate query (min 2 chars).
    2. Check local DB — if name-matching medicines already exist, return them
       immediately without scraping (idempotent).
    3. Call ``fetch_and_insert_many`` which:
       a. Uses Playwright to load the 1mg search page.
       b. Collects **all** matching product URLs (brand mode) or top-N results
          (generic mode, e.g. "ointment", "cream").
       c. Fetches every detail page concurrently and inserts each medicine.
    4. Return the full catalogue cards for every inserted/found medicine.

    Response shape::

        {
          "source": "local" | "scraped" | "mixed",
          "medicines": [ { ...medicine card... }, ... ],
          "count": <int>
        }

    Args:
        body: JSON body ``{"q": "<search query>"}``

    Raises:
        HTTPException: 400 — query too short.
        HTTPException: 404 — nothing found on 1mg.
        HTTPException: 502 — scraper error.
    """
    q = body.q.strip()
    if len(q) < 2:
        raise HTTPException(400, "Search query must be at least 2 characters")

    print(f"\n{'='*60}")
    print(f"[fetch-online] ▶ query='{q}'")
    print(f"{'='*60}")

    q_norm = q.lower().replace(" ", "")

    # ── 1. Local DB check (name LIKE + Python validation) ───────────────────
    print(f"[fetch-online] Step 1 — checking local DB for '{q}' ...")
    with DB() as db:
        local_rows = db.fetchall(
            """SELECT m.*, c.name AS category_name,
                      MIN(v.price) AS min_price, MIN(v.mrp) AS min_mrp,
                      COALESCE(SUM(v.stock), 0) AS total_stock
               FROM medicines m
               JOIN categories c ON c.id = m.category_id
               LEFT JOIN medicine_variants v ON v.medicine_id = m.id
               WHERE m.is_active = 1
                 AND LOWER(m.name) LIKE LOWER(%s)
               GROUP BY m.id
               ORDER BY m.name""",
            (f"%{q}%",),
        )

    # Python guard: only keep rows whose name genuinely contains the query
    valid_local = [
        r for r in local_rows
        if q_norm in (r.get("name") or "").lower().replace(" ", "")
    ]

    if valid_local:
        names = [r.get("name") for r in valid_local]
        print(f"[fetch-online] ✓ Local DB hit — {len(valid_local)} match(es): {names}")
        logger.info(
            "fetch-online: '%s' → %d local match(es), skipping 1mg", q, len(valid_local)
        )
        return {
            "source": "local",
            "medicines": [_parse(dict(r)) for r in valid_local],
            "count": len(valid_local),
        }

    print(f"[fetch-online] ✗ Not in local DB — proceeding to 1mg scrape ...")

    # ── 2. Scrape from 1mg — returns all matching products ──────────────────
    print(f"[fetch-online] Step 2 — launching scraper for '{q}' ...")
    try:
        from scraper_service import fetch_and_insert_many  # lazy import
        results = await fetch_and_insert_many(q)
    except Exception as exc:
        print(f"[fetch-online] ✗ Scraper error: {exc}")
        logger.error("Scraper error for '%s': %s", q, exc, exc_info=True)
        raise HTTPException(502, f"Scraper error: {exc}")

    if not results:
        print(f"[fetch-online] ✗ 0 results returned from scraper for '{q}'")
        raise HTTPException(404, f"No medicines found for '{q}' on 1mg. Try a more specific name.")

    print(f"[fetch-online] ✓ Scraper returned {len(results)} result(s):")
    for r in results:
        status = "existing" if r.get("already_existed") else "NEW"
        print(f"   [{status}] id={r['id']}  name='{r['name']}'")

    # ── 3. Return full catalogue cards for every inserted / existing medicine ─
    med_ids = [r["id"] for r in results]
    print(f"[fetch-online] Step 3 — fetching catalogue cards for ids={med_ids}")
    medicines = _fetch_medicine_cards(med_ids)

    any_new      = any(not r.get("already_existed") for r in results)
    any_existing = any(r.get("already_existed")     for r in results)
    source = "mixed" if (any_new and any_existing) else ("scraped" if any_new else "local")

    print(f"[fetch-online] ✓ Done — source='{source}'  count={len(medicines)}")
    print(f"{'='*60}\n")

    return {
        "source": source,
        "medicines": medicines,
        "count": len(medicines),
    }


@router.get("/{med_id}")
def get_medicine(med_id: int):
    """Return full medicine details including variants and generic alternative.

    The response includes a ``generic_alternative`` key that, when present,
    contains the full details of a cheaper generic substitute with the same
    salt composition, including its variants and calculated savings percentage.

    Args:
        med_id: Primary key of the medicine to fetch.

    Returns:
        dict: Full medicine row with ``variants`` list and optional
              ``generic_alternative`` dict.

    Raises:
        HTTPException: 404 if medicine is not found or is inactive.
    """
    with DB() as db:
        med = db.fetchone(
            """SELECT m.*, c.name AS category_name
               FROM medicines m
               JOIN categories c ON c.id = m.category_id
               WHERE m.id = %s AND m.is_active = 1""",
            (med_id,)
        )
        if not med:
            from fastapi import HTTPException
            raise HTTPException(404, "Not found")

        variants = db.fetchall(
            "SELECT * FROM medicine_variants WHERE medicine_id=%s ORDER BY sort_order",
            (med_id,)
        )
        med = _parse(dict(med))
        med["variants"] = [dict(v) for v in variants]

        # Fetch ALL active alternatives, ordered by cheapest selling price first
        alt_mappings = db.fetchall(
            """SELECT ma.id AS mapping_id, ma.alternative_medicine_id,
                      MIN(v.price) AS alt_min_price
               FROM medicine_alternatives ma
               JOIN medicine_variants v ON v.medicine_id = ma.alternative_medicine_id
               WHERE ma.source_medicine_id = %s AND ma.is_active = 1
               GROUP BY ma.id
               ORDER BY alt_min_price ASC""",
            (med_id,),
        )

        source_min = min((float(v["price"]) for v in med["variants"]), default=0)

        alternatives: list[dict] = []
        for mapping in alt_mappings:
            alt_id = mapping["alternative_medicine_id"]
            alt = db.fetchone(
                """SELECT m.*, c.name AS category_name
                   FROM medicines m
                   JOIN categories c ON c.id = m.category_id
                   WHERE m.id = %s AND m.is_active = 1""",
                (alt_id,),
            )
            if not alt:
                continue
            alt_variants = db.fetchall(
                "SELECT * FROM medicine_variants WHERE medicine_id=%s ORDER BY sort_order",
                (alt_id,),
            )
            alt = _parse(dict(alt))
            alt["variants"] = [dict(v) for v in alt_variants]

            alt_min = min((float(v["price"]) for v in alt["variants"]), default=0)
            savings_pct = (
                round((1 - alt_min / source_min) * 100)
                if source_min > 0 and alt_min < source_min
                else 0
            )
            alt["savings_pct"] = savings_pct
            alt["mapping_id"]  = mapping["mapping_id"]
            alternatives.append(alt)

        # generic_alternative = cheapest single one (backward compat)
        med["generic_alternative"]  = alternatives[0] if alternatives else None
        # generic_alternatives = full sorted list used by the new UI
        med["generic_alternatives"] = alternatives

        return med
