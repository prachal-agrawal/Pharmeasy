import json, os, shutil, time
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from database import DB, get_conn
from auth import get_current_user, settings
from config import get_settings
from jose import JWTError, jwt
from invoice import generate_invoice_pdf
from notifications import notify_order_placed

_settings = get_settings()

router = APIRouter(prefix="/api/orders", tags=["Orders"])

class OrderItem(BaseModel):
    """Single line-item in an order.

    Attributes:
        variant_id: FK to medicine_variants.id.
        quantity: Number of units.
    """
    variant_id: int
    quantity: int


class OrderIn(BaseModel):
    """Payload for placing a new order.

    Attributes:
        address_id: FK to the delivery address.
        payment_method: One of ``upi``, ``card``, ``cod``, ``netbanking``.
        payment_ref: Razorpay payment_id populated after successful online payment.
        items: Non-empty list of ordered variants.
        prescription_urls: List of uploaded prescription image URLs.  Required
            (at least one element) when any ordered medicine has ``requires_rx=1``.
    """
    address_id: int
    payment_method: str = "cod"
    payment_ref: str = ""
    items: List[OrderItem]
    prescription_urls: Optional[List[str]] = None

@router.post("/upload-prescription")
async def upload_prescription(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """Upload a prescription image and return its public URL.

    Accepts image files only (jpeg, png, webp, gif).  The file is stored in
    the configured ``UPLOAD_DIR`` and the URL is returned for inclusion in the
    order payload.

    Args:
        file: Prescription image file (jpeg / png / webp / gif).
        user: Injected authenticated user.

    Returns:
        dict: ``{"url": "/uploads/<filename>"}``

    Raises:
        HTTPException: 400 if the uploaded file is not an image.
    """
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Only image files are allowed for prescriptions (jpeg, png, webp, gif)")

    os.makedirs(_settings.UPLOAD_DIR, exist_ok=True)
    ext   = os.path.splitext(file.filename or "file.jpg")[1] or ".jpg"
    fname = f"rx_{int(user['sub'])}_{int(time.time())}{ext}"
    dest  = os.path.join(_settings.UPLOAD_DIR, fname)
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"url": f"/uploads/{fname}"}


@router.get("")
def list_orders(user=Depends(get_current_user)):
    with DB() as db:
        rows = db.fetchall("""
            SELECT o.*, COUNT(oi.id) AS item_count
            FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id
            WHERE o.user_id=%s GROUP BY o.id ORDER BY o.created_at DESC
        """, (int(user["sub"]),))
        return [dict(r) for r in rows]

@router.get("/{order_id}")
def get_order(order_id: int, user=Depends(get_current_user)):
    with DB() as db:
        order = db.fetchone("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, int(user["sub"])))
        if not order:
            raise HTTPException(404, "Order not found")
        items         = db.fetchall("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
        log           = db.fetchall("SELECT * FROM order_status_log WHERE order_id=%s ORDER BY created_at", (order_id,))
        prescriptions = db.fetchall("SELECT id, url, created_at FROM order_prescriptions WHERE order_id=%s ORDER BY id", (order_id,))
        return {
            **dict(order),
            "items":         [dict(i) for i in items],
            "status_log":    [dict(l) for l in log],
            "prescriptions": [dict(p) for p in prescriptions],
        }

@router.post("")
def place_order(body: OrderIn, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    uid  = int(user["sub"])
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        enriched = []
        subtotal = 0.0
        requires_rx = False

        for item in body.items:
            cur.execute(
                """SELECT mv.*, m.name AS med_name, m.requires_rx
                   FROM medicine_variants mv
                   JOIN medicines m ON m.id = mv.medicine_id
                   WHERE mv.id = %s FOR UPDATE""",
                (item.variant_id,)
            )
            v = cur.fetchone()
            if not v:
                raise HTTPException(400, f"Variant {item.variant_id} not found")
            if v["stock"] < item.quantity:
                raise HTTPException(400, f"Insufficient stock for {v['med_name']} ({v['label']})")
            if v["requires_rx"]:
                requires_rx = True
            subtotal += float(v["price"]) * item.quantity
            enriched.append({"item": item, "variant": v})

        # Validate prescription when any ordered medicine requires one
        if requires_rx and not body.prescription_urls:
            raise HTTPException(
                400,
                "A valid prescription image is required for one or more medicines in your order. "
                "Please upload a prescription and try again."
            )

        delivery = 0.0 if subtotal >= 500 else 49.0
        discount = round(subtotal * 0.05) if subtotal >= 1000 else 0.0
        total    = subtotal + delivery - discount

        ts = int(datetime.utcnow().timestamp()) % 1000000
        order_number = f"MK-{ts:06d}"

        cur.execute("SELECT * FROM addresses WHERE id=%s AND user_id=%s", (body.address_id, uid))
        addr = cur.fetchone()

        # payment_status: cod stays pending; razorpay marks paid after verify
        pay_status = "paid" if body.payment_method != "cod" and body.payment_ref else "pending"

        cur.execute("""
            INSERT INTO orders (order_number,user_id,address_id,address_snapshot,status,
                                subtotal,delivery_charge,discount,total,payment_method,
                                payment_status,payment_ref)
            VALUES (%s,%s,%s,%s,'pending',%s,%s,%s,%s,%s,%s,%s)
        """, (order_number, uid, body.address_id, json.dumps(addr, default=str),
              subtotal, delivery, discount, total, body.payment_method,
              pay_status, body.payment_ref or None))
        order_id = cur.lastrowid

        # Insert each prescription image into the mapping table
        for rx_url in (body.prescription_urls or []):
            if rx_url:
                cur.execute(
                    "INSERT IGNORE INTO order_prescriptions (order_id, url) VALUES (%s, %s)",
                    (order_id, rx_url),
                )

        for e in enriched:
            v, it = e["variant"], e["item"]
            cur.execute("""
                INSERT INTO order_items (order_id,variant_id,medicine_id,name,variant_label,price,quantity,subtotal)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (order_id, it.variant_id, v["medicine_id"], v["med_name"],
                  v["label"], float(v["price"]), it.quantity, float(v["price"]) * it.quantity))
            cur.execute("UPDATE medicine_variants SET stock=stock-%s WHERE id=%s", (it.quantity, it.variant_id))

        cur.execute("INSERT INTO order_status_log (order_id,status,note,changed_by) VALUES (%s,'pending','Order placed',%s)",
                    (order_id, uid))
        inv_number = f"INV-{order_number}"
        cur.execute("INSERT INTO invoices (order_id,invoice_number) VALUES (%s,%s)", (order_id, inv_number))
        conn.commit()

        # Fetch user details for notifications
        cur.execute("SELECT name, email, phone FROM users WHERE id=%s", (uid,))
        db_user = cur.fetchone()

        # Generate PDF (non-blocking)
        generate_invoice_pdf(order_id, inv_number, enriched, {
            "total": total, "subtotal": subtotal, "delivery_charge": delivery,
            "discount": discount, "order_number": order_number,
            "addr": addr, "payment_method": body.payment_method,
            "payment_status": pay_status,
        })

        # Build a flat items list for the email template
        notification_items = [
            {
                "med_name":      e["variant"]["med_name"],
                "label":         e["variant"]["label"],
                "price":         float(e["variant"]["price"]),
                "quantity":      e["item"].quantity,
            }
            for e in enriched
        ]

        # Queue order confirmation email + SMS without blocking the response
        if db_user:
            background_tasks.add_task(
                notify_order_placed,
                user_email=db_user["email"],
                user_name=db_user["name"],
                user_phone=db_user.get("phone") or (addr.get("phone") if addr else None),
                order_number=order_number,
                order_id=order_id,
                items=notification_items,
                subtotal=subtotal,
                delivery_charge=delivery,
                discount=discount,
                total=total,
                payment_method=body.payment_method,
                payment_status=pay_status,
                addr=addr,
            )

        return {"order_id": order_id, "order_number": order_number, "total": total}
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback(); raise HTTPException(400, str(e))
    finally:
        cur.close(); conn.close()

@router.get("/{order_id}/invoice")
def download_invoice(
    order_id: int,
    token: Optional[str] = Query(default=None),
    user=Depends(get_current_user),
):
    """Download invoice PDF. Supports both Authorization header and ?token= query param
    so the browser can navigate directly to the URL for file download."""
    # If a query-param token is provided, decode it to get the user
    if token:
        try:
            user = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise HTTPException(401, "Invalid or expired token")

    with DB() as db:
        # Admins can download any invoice; regular users are restricted to their own orders.
        if user.get("role") == "admin":
            inv = db.fetchone(
                "SELECT i.* FROM invoices i JOIN orders o ON o.id=i.order_id WHERE o.id=%s",
                (order_id,)
            )
        else:
            inv = db.fetchone(
                "SELECT i.* FROM invoices i JOIN orders o ON o.id=i.order_id WHERE o.id=%s AND o.user_id=%s",
                (order_id, int(user["sub"]))
            )
    if not inv:
        raise HTTPException(404, "Invoice not found")
    path = f"./public/invoices/{inv['invoice_number']}.pdf"
    if not os.path.exists(path):
        raise HTTPException(404, "PDF not yet ready, try again")
    return FileResponse(path, media_type="application/pdf", filename=inv["invoice_number"] + ".pdf")
