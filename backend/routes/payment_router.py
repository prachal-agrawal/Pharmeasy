"""
╔══════════════════════════════════════════════════════════════╗
║  💳  RAZORPAY — COMPLETE IMPLEMENTATION                      ║
║  Steps:                                                      ║
║  1. Add to .env:                                             ║
║       RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXXXX              ║
║       RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX   ║
║  2. Already installed via requirements.txt (razorpay)        ║
║  3. Run backend — payment endpoints are live immediately      ║
╚══════════════════════════════════════════════════════════════╝
"""
import hmac, hashlib, time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from database import DB
from auth import get_current_user
from config import get_settings
from notifications import notify_payment_confirmed
import razorpay

settings = get_settings()
router   = APIRouter(prefix="/api/payment", tags=["Payment"])

def get_razorpay_client():
    if not settings.RAZORPAY_KEY_ID or settings.RAZORPAY_KEY_ID.startswith("rzp_test_XXXX"):
        raise HTTPException(503, "Razorpay credentials not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# ── Models ───────────────────────────────────────────────────
class CreateOrderIn(BaseModel):
    amount: float           # in INR rupees

class VerifyIn(BaseModel):
    razorpay_order_id:  str
    razorpay_payment_id: str
    razorpay_signature: str
    internal_order_id:  int  # your DB order id

class RefundIn(BaseModel):
    payment_id: str
    amount: float           # partial refund in INR (0 = full refund)

# ── 1. Create Razorpay Order ─────────────────────────────────
@router.post("/create-order")
def create_razorpay_order(body: CreateOrderIn, user=Depends(get_current_user)):
    """
    Frontend calls this BEFORE showing the Razorpay modal.
    Returns razorpay order_id + your public key for the JS SDK.
    """
    client = get_razorpay_client()
    amount_paise = int(body.amount * 100)      # Razorpay works in paise

    rzp_order = client.order.create({
        "amount":   amount_paise,
        "currency": "INR",
        "receipt":  f"mathurapharmeasy_{int(time.time())}",
        "notes": {"user_id": user["sub"]},
    })
    return {
        "razorpay_order_id": rzp_order["id"],
        "amount":            rzp_order["amount"],
        "currency":          rzp_order["currency"],
        "key_id":            settings.RAZORPAY_KEY_ID,
    }

# ── 2. Verify Payment Signature ──────────────────────────────
@router.post("/verify")
def verify_payment(body: VerifyIn, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """
    Called by frontend AFTER Razorpay payment modal closes successfully.
    Verifies HMAC-SHA256 signature to confirm payment is genuine.
    Then marks the order as paid in your database.
    """
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Razorpay secret not configured")

    # HMAC verification
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(400, "Payment signature mismatch — possible fraud attempt")

    # Mark order as paid
    with DB() as db:
        db.execute(
            "UPDATE orders SET payment_status='paid', payment_ref=%s WHERE id=%s AND user_id=%s",
            (body.razorpay_payment_id, body.internal_order_id, int(user["sub"]))
        )
        db.execute(
            "INSERT INTO order_status_log (order_id,status,note) VALUES (%s,'confirmed','Payment verified via Razorpay')",
            (body.internal_order_id,)
        )
        db.execute(
            "UPDATE orders SET status='confirmed' WHERE id=%s",
            (body.internal_order_id,)
        )

        # Fetch order + user info to send payment confirmation notifications
        order_row = db.fetchone(
            """SELECT o.order_number, o.total, u.email, u.name, u.phone
               FROM orders o JOIN users u ON u.id = o.user_id
               WHERE o.id = %s""",
            (body.internal_order_id,)
        )

    if order_row:
        background_tasks.add_task(
            notify_payment_confirmed,
            user_email=order_row["email"],
            user_name=order_row["name"],
            user_phone=order_row.get("phone"),
            order_number=order_row["order_number"],
            order_id=body.internal_order_id,
            total=float(order_row["total"]),
            payment_id=body.razorpay_payment_id,
        )

    return {
        "verified":    True,
        "payment_id":  body.razorpay_payment_id,
        "order_status": "confirmed",
    }

# ── 3. Fetch Payment Details (admin / debug) ─────────────────
@router.get("/details/{payment_id}")
def get_payment_details(payment_id: str, user=Depends(get_current_user)):
    """Fetch Razorpay payment details for a given payment_id."""
    client = get_razorpay_client()
    payment = client.payment.fetch(payment_id)
    return payment

# ── 4. Refund ────────────────────────────────────────────────
@router.post("/refund")
def refund_payment(body: RefundIn, user=Depends(get_current_user)):
    """
    Issue full or partial refund.
    amount=0 → full refund.
    """
    if user.get("role") != "admin":
        raise HTTPException(403, "Only admins can issue refunds")
    client = get_razorpay_client()
    params: dict = {}
    if body.amount > 0:
        params["amount"] = int(body.amount * 100)   # partial refund in paise

    refund = client.payment.refund(body.payment_id, params)
    # Update DB
    with DB() as db:
        db.execute(
            "UPDATE orders SET payment_status='refunded' WHERE payment_ref=%s",
            (body.payment_id,)
        )
    return {"refund_id": refund["id"], "status": refund["status"], "amount": refund["amount"] / 100}

# ── 5. Webhook (Razorpay → Your Server) ──────────────────────
from fastapi import Request

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """
    Razorpay sends events here automatically.
    Configure in Razorpay Dashboard → Settings → Webhooks.
    URL: https://yourdomain.com/api/payment/webhook
    Secret: set RAZORPAY_WEBHOOK_SECRET in .env and verify below.
    """
    body_bytes = await request.body()
    signature  = request.headers.get("X-Razorpay-Signature", "")

    # Verify webhook signature
    if settings.RAZORPAY_KEY_SECRET:
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(400, "Invalid webhook signature")

    import json
    event = json.loads(body_bytes)
    event_type = event.get("event")

    if event_type == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        payment_id = payment["id"]
        with DB() as db:
            db.execute(
                "UPDATE orders SET payment_status='paid', status='confirmed' WHERE payment_ref=%s",
                (payment_id,)
            )

    elif event_type == "payment.failed":
        payment = event["payload"]["payment"]["entity"]
        payment_id = payment["id"]
        with DB() as db:
            db.execute(
                "UPDATE orders SET payment_status='failed' WHERE payment_ref=%s",
                (payment_id,)
            )

    elif event_type == "refund.created":
        refund = event["payload"]["refund"]["entity"]
        with DB() as db:
            db.execute(
                "UPDATE orders SET payment_status='refunded' WHERE payment_ref=%s",
                (refund.get("payment_id"),)
            )

    return {"status": "ok", "event": event_type}
