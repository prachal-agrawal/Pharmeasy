import json, os, shutil, uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse
from typing import List, Optional, Union

from database import DB
from routes.medicines_router import _parse
from auth import require_admin
from config import get_settings
from notifications import notify_order_status_changed

settings = get_settings()
router   = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/stats")
def stats(admin=Depends(require_admin)):
    with DB() as db:
        td   = db.fetchone("SELECT COUNT(*) AS c, COALESCE(SUM(total),0) AS rev FROM orders WHERE DATE(created_at)=CURDATE()")
        pend = db.fetchone("SELECT COUNT(*) AS c FROM orders WHERE status='pending'")
        usr  = db.fetchone("SELECT COUNT(*) AS c FROM users WHERE role='customer'")
        low  = db.fetchone("SELECT COUNT(*) AS c FROM medicine_variants WHERE stock<10")
        return {"todayOrders": td["c"], "todayRevenue": float(td["rev"]),
                "pendingOrders": pend["c"], "totalUsers": usr["c"], "lowStock": low["c"]}

@router.get("/orders")
def all_orders(admin=Depends(require_admin)):
    with DB() as db:
        rows = db.fetchall("""
            SELECT o.*, u.name AS user_name, u.email,
                   COUNT(DISTINCT oi.id) AS item_count,
                   GROUP_CONCAT(DISTINCT op.url ORDER BY op.id SEPARATOR '|||') AS rx_urls
            FROM orders o
            JOIN users u ON u.id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN order_prescriptions op ON op.order_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 500
        """)
        return [dict(r) for r in rows]

@router.put("/orders/{order_id}/status")
def update_status(order_id: int, body: dict, background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    """Update an order's status and notify the customer via email and SMS.

    Args:
        order_id: Order DB primary key.
        body: JSON body with keys ``status`` (required) and optional ``note``.
        background_tasks: FastAPI background task queue for async notifications.
        admin: Injected admin user.

    Returns:
        dict: ``{"ok": True}``

    Raises:
        HTTPException: 400 if the provided status is not in the allowed list.
    """
    valid = ["pending", "confirmed", "dispatched", "shipped", "delivered", "cancelled"]
    s    = body.get("status")
    note = body.get("note", "")
    if s not in valid:
        raise HTTPException(400, "Invalid status")

    with DB() as db:
        db.execute("UPDATE orders SET status=%s WHERE id=%s", (s, order_id))
        db.execute(
            "INSERT INTO order_status_log (order_id,status,note,changed_by) VALUES (%s,%s,%s,%s)",
            (order_id, s, note or None, int(admin["sub"]))
        )
        # Fetch user contact info for notifications
        order_row = db.fetchone(
            """SELECT o.order_number, u.email, u.name, u.phone
               FROM orders o JOIN users u ON u.id = o.user_id
               WHERE o.id = %s""",
            (order_id,)
        )

    if order_row:
        background_tasks.add_task(
            notify_order_status_changed,
            user_email=order_row["email"],
            user_name=order_row["name"],
            user_phone=order_row.get("phone"),
            order_number=order_row["order_number"],
            order_id=order_id,
            new_status=s,
            note=note,
        )

    return {"ok": True}

@router.get("/categories")
def list_cats(admin=Depends(require_admin)):
    with DB() as db:
        return [dict(r) for r in db.fetchall("SELECT * FROM categories ORDER BY sort_order")]

@router.get("/medicines")
def list_meds(admin=Depends(require_admin)):
    with DB() as db:
        rows = db.fetchall("""
            SELECT m.*,c.name AS category_name,
                   COUNT(mv.id) AS variant_count, COALESCE(SUM(mv.stock),0) AS total_stock
            FROM medicines m JOIN categories c ON c.id=m.category_id
            LEFT JOIN medicine_variants mv ON mv.medicine_id=m.id
            GROUP BY m.id ORDER BY m.created_at DESC
        """)
        return [dict(r) for r in rows]

def _save_image(image: UploadFile) -> str:
    """Persist one uploaded image and return a public ``/uploads/...`` path."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(image.filename or "")[1] or ".jpg"
    fname = f"med_{uuid.uuid4().hex[:16]}{ext}"
    dest = os.path.join(settings.UPLOAD_DIR, fname)
    with open(dest, "wb") as f:
        shutil.copyfileobj(image.file, f)
    return f"/uploads/{fname}"


def _normalize_images_field(
    images: Optional[Union[UploadFile, List[UploadFile]]],
) -> list[UploadFile]:
    """Turn the ``images`` form field into a list (used when not using :func:`_images_from_multipart`)."""
    if images is None:
        return []
    if isinstance(images, list):
        return [x for x in images if x and getattr(x, "filename", None)]
    if getattr(images, "filename", None):
        return [images]
    return []


def _images_from_multipart(form) -> tuple[list[UploadFile], Optional[UploadFile]]:
    """Read **all** ``images`` parts and optional legacy ``image`` from a parsed multipart form.

    FastAPI's ``File()`` binding for ``Union[UploadFile, List[UploadFile]]`` often
    delivers only **one** :class:`~starlette.datastructures.UploadFile` when several
    parts share the name ``images``. Using :meth:`starlette.datastructures.FormData.getlist`
    returns every file in order.

    Args:
        form: Result of ``await request.form()``.

    Returns:
        Tuple of (ordered ``images`` uploads with a filename, optional legacy ``image``).
    """
    out: list[UploadFile] = []
    for item in form.getlist("images"):
        if item is not None and getattr(item, "filename", None):
            out.append(item)
    legacy = form.get("image")
    legacy_file: Optional[UploadFile] = None
    if legacy is not None and getattr(legacy, "filename", None):
        legacy_file = legacy  # type: ignore[assignment]
    return out, legacy_file


def _collect_uploads(
    images: Optional[Union[UploadFile, List[UploadFile]]],
    legacy: Optional[UploadFile],
) -> list[UploadFile]:
    """Merge multi-file and legacy single-file upload fields."""
    out: list[UploadFile] = []
    out.extend(_normalize_images_field(images))
    if legacy and legacy.filename:
        out.append(legacy)
    return out


def _collect_uploads_multipart(form) -> list[UploadFile]:
    """Merge ``images`` (all parts) and legacy ``image`` from a parsed form."""
    parts, legacy = _images_from_multipart(form)
    out = list(parts)
    if legacy and legacy.filename:
        out.append(legacy)
    return out


@router.get("/medicines/{med_id}")
def admin_get_medicine(med_id: int, admin=Depends(require_admin)):
    """Return one medicine with variants (including inactive) for admin edit."""
    with DB() as db:
        med = db.fetchone(
            """SELECT m.*, c.name AS category_name
               FROM medicines m JOIN categories c ON c.id=m.category_id
               WHERE m.id=%s""",
            (med_id,),
        )
        if not med:
            raise HTTPException(404, "Medicine not found")
        variants = db.fetchall(
            "SELECT * FROM medicine_variants WHERE medicine_id=%s ORDER BY sort_order",
            (med_id,),
        )
    row = _parse(dict(med))
    row["variants"] = [dict(v) for v in variants]
    return row

@router.post("/medicines")
async def add_medicine(request: Request, admin=Depends(require_admin)):
    """Create a new medicine with optional variants and image(s).

    Multipart fields are read via :meth:`starlette.requests.Request.form` so **every**
    part named ``images`` is collected (FastAPI ``File()`` often only binds one).

    Args:
        request: Raw request (multipart form).
        admin: Injected admin user from JWT.

    Returns:
        dict: {"id": new_medicine_id}
    """
    form = await request.form()
    name = str(form.get("name") or "").strip()
    brand = str(form.get("brand") or "").strip()
    if not name or not brand:
        raise HTTPException(422, "name and brand are required")
    try:
        category_id = int(form.get("category_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "invalid category_id")
    requires_rx = int(form.get("requires_rx") or 0)
    salt_composition = str(form.get("salt_composition") or "")
    manufacturer = str(form.get("manufacturer") or "")
    uses = str(form.get("uses") or "")
    side_effects = str(form.get("side_effects") or "[]")
    safety_points = str(form.get("safety_points") or "[]")
    warning = str(form.get("warning") or "")
    variants = str(form.get("variants") or "[]")

    uploads = _collect_uploads_multipart(form)
    paths = [_save_image(u) for u in uploads]
    image_urls_json = json.dumps(paths) if paths else None
    image_url_first = paths[0] if paths else None

    # Duplicate check — case-insensitive name match
    with DB() as db:
        dup = db.fetchone(
            "SELECT id, name FROM medicines WHERE LOWER(name) = LOWER(%s)",
            (name,),
        )
        if dup:
            raise HTTPException(
                409,
                f"A medicine named '{dup['name']}' already exists "
                f"(ID: {dup['id']}). Edit it instead of creating a duplicate.",
            )

    with DB() as db:
        mid = db.insert(
            """INSERT INTO medicines
               (name,brand,salt_composition,manufacturer,category_id,uses,
                side_effects,safety_points,warning,requires_rx,image_url,image_urls)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (name, brand, salt_composition or None, manufacturer or None,
             category_id, uses, side_effects, safety_points, warning,
             requires_rx, image_url_first, image_urls_json)
        )
        for i, v in enumerate(json.loads(variants)):
            price   = float(v["price"])
            # If MRP not supplied, back-calculate from flat 15% discount
            mrp_raw = v.get("mrp")
            mrp     = float(mrp_raw) if mrp_raw not in (None, "", 0) else round(price / 0.85, 2)
            db.execute(
                "INSERT INTO medicine_variants (medicine_id,label,mrp,price,stock,sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                (mid, v["label"], mrp, price, v.get("stock", 0), i)
            )
    return {"id": mid}


@router.put("/medicines/{med_id}")
async def update_medicine(med_id: int, request: Request, admin=Depends(require_admin)):
    """Update an existing medicine record.

    Multipart is parsed with :meth:`Request.form` so every ``images`` file part is
    kept (multiple uploads with the same field name).

    When ``existing_image_urls`` is sent (JSON array of kept ``/uploads/...``
    paths) and/or new ``images`` files, gallery columns are updated. If both are
    omitted, existing images are left unchanged (e.g. status-only updates).

    Args:
        med_id: Medicine ID to update.
        request: Raw request (multipart form).
        admin: Injected admin user from JWT.

    Returns:
        dict: {"ok": True}
    """
    form = await request.form()
    name = str(form.get("name") or "").strip()
    brand = str(form.get("brand") or "").strip()
    if not name or not brand:
        raise HTTPException(422, "name and brand are required")
    try:
        category_id = int(form.get("category_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "invalid category_id")
    requires_rx = int(form.get("requires_rx") or 0)
    is_active = int(form.get("is_active") or 1)
    salt_composition = str(form.get("salt_composition") or "")
    manufacturer = str(form.get("manufacturer") or "")
    uses = str(form.get("uses") or "")
    side_effects = str(form.get("side_effects") or "[]")
    safety_points = str(form.get("safety_points") or "[]")
    warning = str(form.get("warning") or "")
    variants = str(form.get("variants") or "[]")
    existing_raw = form.get("existing_image_urls")
    existing_image_urls: Optional[str] = (
        str(existing_raw) if existing_raw is not None else None
    )

    # Ensure no other medicine (different ID) already uses the same name
    with DB() as db:
        dup = db.fetchone(
            "SELECT id, name FROM medicines WHERE LOWER(name) = LOWER(%s) AND id != %s",
            (name, med_id),
        )
        if dup:
            raise HTTPException(
                409,
                f"Another medicine named '{dup['name']}' already exists "
                f"(ID: {dup['id']}). Choose a different name.",
            )

    uploads = _collect_uploads_multipart(form)
    new_paths = [_save_image(f) for f in uploads]
    touch_gallery = existing_image_urls is not None or len(new_paths) > 0

    with DB() as db:
        base_fields = (name, brand, salt_composition or None, manufacturer or None,
                       category_id, uses, side_effects, safety_points, warning,
                       requires_rx, is_active)

        if touch_gallery:
            kept: list[str] = []
            if existing_image_urls is not None:
                try:
                    parsed = json.loads(existing_image_urls)
                    if isinstance(parsed, list):
                        kept = [str(u).strip() for u in parsed if u and str(u).strip()]
                except json.JSONDecodeError:
                    kept = []
            final_urls = kept + new_paths
            img_json = json.dumps(final_urls) if final_urls else None
            img_first = final_urls[0] if final_urls else None
            db.execute(
                """UPDATE medicines SET
                   name=%s,brand=%s,salt_composition=%s,manufacturer=%s,
                   category_id=%s,uses=%s,side_effects=%s,safety_points=%s,
                   warning=%s,requires_rx=%s,is_active=%s,image_url=%s,image_urls=%s
                   WHERE id=%s""",
                (*base_fields, img_first, img_json, med_id),
            )
        else:
            db.execute(
                """UPDATE medicines SET
                   name=%s,brand=%s,salt_composition=%s,manufacturer=%s,
                   category_id=%s,uses=%s,side_effects=%s,safety_points=%s,
                   warning=%s,requires_rx=%s,is_active=%s
                   WHERE id=%s""",
                (*base_fields, med_id),
            )

        db.execute("DELETE FROM medicine_variants WHERE medicine_id=%s", (med_id,))
        for i, v in enumerate(json.loads(variants)):
            price   = float(v["price"])
            mrp_raw = v.get("mrp")
            mrp     = float(mrp_raw) if mrp_raw not in (None, "", 0) else round(price / 0.85, 2)
            db.execute(
                "INSERT INTO medicine_variants (medicine_id,label,mrp,price,stock,sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                (med_id, v["label"], mrp, price, v.get("stock", 0), i)
            )
    return {"ok": True}


@router.delete("/medicines/{med_id}")
def deactivate(med_id: int, admin=Depends(require_admin)):
    """Soft-delete a medicine by setting is_active = 0.

    Args:
        med_id: Medicine ID to deactivate.
        admin: Injected admin user from JWT.

    Returns:
        dict: {"ok": True}
    """
    with DB() as db:
        db.execute("UPDATE medicines SET is_active=0 WHERE id=%s", (med_id,))
    return {"ok": True}


# ─── Generic Alternatives ────────────────────────────────────────────────────

@router.get("/alternatives")
def list_alternatives(admin=Depends(require_admin)):
    """List all generic alternative mappings with medicine details.

    Args:
        admin: Injected admin user from JWT.

    Returns:
        list[dict]: Each item contains source + alternative medicine info.
    """
    with DB() as db:
        rows = db.fetchall("""
            SELECT
                ma.id,
                ma.source_medicine_id,
                ma.alternative_medicine_id,
                ma.is_active,
                src.name  AS source_name,
                src.brand AS source_brand,
                src.salt_composition AS source_salt,
                COALESCE(MIN(sv.price), 0) AS source_min_price,
                alt.name  AS alt_name,
                alt.brand AS alt_brand,
                alt.salt_composition AS alt_salt,
                COALESCE(MIN(av.price), 0) AS alt_min_price
            FROM medicine_alternatives ma
            JOIN medicines src ON src.id = ma.source_medicine_id
            JOIN medicines alt ON alt.id = ma.alternative_medicine_id
            LEFT JOIN medicine_variants sv ON sv.medicine_id = src.id
            LEFT JOIN medicine_variants av ON av.medicine_id = alt.id
            GROUP BY ma.id
            ORDER BY ma.created_at DESC
        """)
        return [dict(r) for r in rows]


@router.post("/alternatives")
def create_alternative(body: dict, admin=Depends(require_admin)):
    """Create a generic alternative mapping between two medicines.

    Args:
        body: Must contain ``source_medicine_id`` and ``alternative_medicine_id``.
        admin: Injected admin user from JWT.

    Returns:
        dict: {"id": new_mapping_id}

    Raises:
        HTTPException: 400 if both IDs are the same.
        HTTPException: 409 if mapping already exists.
    """
    src = body.get("source_medicine_id")
    alt = body.get("alternative_medicine_id")
    if not src or not alt:
        raise HTTPException(400, "source_medicine_id and alternative_medicine_id are required")
    if src == alt:
        raise HTTPException(400, "Source and alternative cannot be the same medicine")
    with DB() as db:
        existing = db.fetchone(
            "SELECT id FROM medicine_alternatives WHERE source_medicine_id=%s AND alternative_medicine_id=%s",
            (src, alt)
        )
        if existing:
            raise HTTPException(409, "This alternative mapping already exists")
        new_id = db.insert(
            "INSERT INTO medicine_alternatives (source_medicine_id, alternative_medicine_id) VALUES (%s,%s)",
            (src, alt)
        )
    return {"id": new_id}


@router.put("/alternatives/{alt_id}")
def toggle_alternative(alt_id: int, body: dict, admin=Depends(require_admin)):
    """Activate or deactivate a generic alternative mapping.

    Args:
        alt_id: Mapping ID.
        body: Must contain ``is_active`` (0 or 1).
        admin: Injected admin user from JWT.

    Returns:
        dict: {"ok": True}
    """
    is_active = int(body.get("is_active", 1))
    with DB() as db:
        db.execute(
            "UPDATE medicine_alternatives SET is_active=%s WHERE id=%s",
            (is_active, alt_id)
        )
    return {"ok": True}


@router.delete("/alternatives/{alt_id}")
def delete_alternative(alt_id: int, admin=Depends(require_admin)):
    """Permanently remove a generic alternative mapping.

    Args:
        alt_id: Mapping ID.
        admin: Injected admin user from JWT.

    Returns:
        dict: {"ok": True}
    """
    with DB() as db:
        db.execute("DELETE FROM medicine_alternatives WHERE id=%s", (alt_id,))
    return {"ok": True}
