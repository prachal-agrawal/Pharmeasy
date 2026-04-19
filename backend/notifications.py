"""
Notification service for MathuraPharmeasy.

Handles transactional email (SMTP) and SMS (Fast2SMS) for:
  - Order confirmation
  - Payment confirmation
  - Order status updates (shipped, delivered, cancelled)

Usage:
    from notifications import notify_order_placed, notify_payment_confirmed

    # In an order route (run in background task)
    await notify_order_placed(user_email, user_name, user_phone, order_data, items)
"""

import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

# ─── Brand constants ─────────────────────────────────────────────────────────

BRAND_NAME = "MathuraPharmeasy"
BRAND_COLOR = "#16a34a"          # green-600
BRAND_LIGHT = "#dcfce7"          # green-100
SUPPORT_EMAIL = "support@mathurapharmeasy.in"
SUPPORT_PHONE = "+91-9876543210"
WEBSITE = "https://mathurapharmeasy.in"


# ─── HTML email templates ─────────────────────────────────────────────────────

def _base_template(title: str, preheader: str, body_html: str) -> str:
    """Wrap an inner body block in the full MathuraPharmeasy branded email shell.

    Args:
        title: Browser / notification title for the email.
        preheader: Short preview text shown in inbox before opening.
        body_html: Inner HTML content to embed inside the card.

    Returns:
        Complete HTML string ready to be sent as email body.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body  {{ background:#f0fdf4; font-family:'Segoe UI',Arial,sans-serif; color:#1f2937; }}
    .wrapper {{ max-width:600px; margin:0 auto; padding:24px 16px; }}
    .header  {{ background:{BRAND_COLOR}; border-radius:16px 16px 0 0; padding:28px 32px; text-align:center; }}
    .header img {{ height:48px; margin-bottom:8px; }}
    .header h1  {{ color:#fff; font-size:22px; font-weight:800; letter-spacing:-0.5px; }}
    .header p   {{ color:#bbf7d0; font-size:13px; margin-top:4px; }}
    .card    {{ background:#fff; border-radius:0 0 16px 16px; padding:32px; box-shadow:0 4px 24px rgba(0,0,0,.06); }}
    .section {{ border:1px solid #e5e7eb; border-radius:12px; padding:16px 20px; margin-bottom:16px; }}
    .section-title {{ font-size:11px; font-weight:700; color:#9ca3af; text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }}
    .badge   {{ display:inline-block; background:{BRAND_LIGHT}; color:{BRAND_COLOR}; font-size:11px; font-weight:700;
                padding:3px 10px; border-radius:999px; }}
    .row     {{ display:flex; justify-content:space-between; align-items:center; font-size:13px; padding:4px 0; }}
    .row + .row {{ border-top:1px solid #f3f4f6; }}
    .row .label {{ color:#6b7280; }}
    .row .value {{ font-weight:600; color:#111827; }}
    .divider {{ border:none; border-top:1px solid #f3f4f6; margin:20px 0; }}
    .total   {{ font-size:22px; font-weight:800; color:{BRAND_COLOR}; }}
    .btn     {{ display:inline-block; background:{BRAND_COLOR}; color:#fff; font-size:14px; font-weight:700;
                padding:13px 32px; border-radius:10px; text-decoration:none; margin:8px 4px; }}
    .btn-outline {{ display:inline-block; border:2px solid {BRAND_COLOR}; color:{BRAND_COLOR}; font-size:14px;
                    font-weight:700; padding:11px 32px; border-radius:10px; text-decoration:none; margin:8px 4px; }}
    .status-badge {{ display:inline-block; padding:5px 14px; border-radius:999px; font-size:12px; font-weight:700; }}
    .status-pending   {{ background:#fef9c3; color:#854d0e; }}
    .status-confirmed {{ background:{BRAND_LIGHT}; color:#14532d; }}
    .status-paid      {{ background:#dcfce7; color:#166534; }}
    .item-row {{ display:flex; justify-content:space-between; padding:8px 0;
                 border-bottom:1px solid #f9fafb; font-size:13px; }}
    .item-name  {{ color:#374151; flex:1; }}
    .item-price {{ font-weight:700; color:#111827; white-space:nowrap; margin-left:8px; }}
    .footer  {{ text-align:center; padding:24px 16px 0; font-size:12px; color:#9ca3af; }}
    .footer a {{ color:{BRAND_COLOR}; text-decoration:none; font-weight:600; }}
    .highlight-box {{ background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:14px 18px; margin-bottom:16px; }}
    .warning-box   {{ background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:14px 18px; margin-bottom:16px; }}
  </style>
</head>
<body>
  <!-- Preheader (hidden preview text) -->
  <span style="display:none;max-height:0;overflow:hidden;">{preheader}</span>

  <div class="wrapper">
    <!-- Header -->
    <div class="header">
      <h1>🌿 {BRAND_NAME}</h1>
      <p>Your trusted online pharmacy</p>
    </div>

    <!-- Card body -->
    <div class="card">
      {body_html}
    </div>

    <!-- Footer -->
    <div class="footer">
      <p>Need help? <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a> · {SUPPORT_PHONE}</p>
      <p style="margin-top:6px;">
        <a href="{WEBSITE}">Visit our website</a>
        &nbsp;·&nbsp;
        <a href="{WEBSITE}/orders">Track Orders</a>
      </p>
      <p style="margin-top:12px; color:#d1d5db;">
        © {BRAND_NAME} · Mathura, Uttar Pradesh, India<br/>
        You received this because you placed an order on our platform.
      </p>
    </div>
  </div>
</body>
</html>"""


def _order_items_html(items: List[Dict[str, Any]]) -> str:
    """Render the list of order items as HTML table rows.

    Args:
        items: List of enriched order item dicts with keys
               ``med_name`` / ``name``, ``label`` / ``variant_label``,
               ``price``, ``quantity``.

    Returns:
        HTML string of item rows.
    """
    rows = []
    for it in items:
        name  = it.get("med_name") or it.get("name", "Medicine")
        label = it.get("label") or it.get("variant_label", "")
        qty   = it.get("quantity", 1)
        price = float(it.get("price", 0))
        rows.append(
            f'<div class="item-row">'
            f'<span class="item-name">{name} <span style="color:#9ca3af;font-size:12px;">({label})</span> × {qty}</span>'
            f'<span class="item-price">₹{price * qty:.0f}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def build_order_confirmation_email(
    user_name: str,
    order_number: str,
    order_id: int,
    items: List[Dict[str, Any]],
    subtotal: float,
    delivery_charge: float,
    discount: float,
    total: float,
    payment_method: str,
    payment_status: str,
    addr: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the HTML body for an order confirmation email.

    Args:
        user_name: Customer's display name.
        order_number: Human-readable order number (e.g. ``MK-123456``).
        order_id: DB primary key used in the invoice URL.
        items: List of ordered items (dicts with name, label, price, quantity).
        subtotal: Order subtotal before adjustments.
        delivery_charge: Delivery fee (0 if free).
        discount: Discount amount applied.
        total: Final payable amount.
        payment_method: One of ``upi``, ``card``, ``cod``, ``netbanking``.
        payment_status: ``paid`` or ``pending``.
        addr: Delivery address dict (optional, used for address section).

    Returns:
        Complete HTML email string.

    Example:
        >>> html = build_order_confirmation_email("Alice", "MK-001", 1, [...], 500, 0, 25, 475, "upi", "paid")
    """
    pay_label_map = {
        "upi": "UPI Payment", "card": "Card Payment",
        "cod": "Cash on Delivery", "netbanking": "Net Banking",
        "razorpay": "Razorpay",
    }
    pay_label = pay_label_map.get(payment_method, payment_method.title())
    is_cod = payment_method == "cod"

    pay_note = (
        '<div class="warning-box">💵 <strong>Keep cash ready!</strong> '
        f'Please keep <strong>₹{total:.0f}</strong> ready at the time of delivery.</div>'
        if is_cod else
        '<div class="highlight-box">✅ Payment received. Your order is being processed.</div>'
    )

    addr_html = ""
    if addr:
        addr_html = f"""
        <div class="section">
          <div class="section-title">📦 Delivery Address</div>
          <p style="font-weight:700;font-size:14px;">{addr.get('name','')}</p>
          <p style="color:#6b7280;font-size:13px;margin-top:4px;line-height:1.6;">
            {addr.get('line1','')}{',' + addr.get('line2','') if addr.get('line2') else ''}<br/>
            {addr.get('city','')}, {addr.get('state','')} – {addr.get('pin','')}
          </p>
          {f'<p style="color:#6b7280;font-size:13px;margin-top:4px;">📞 {addr.get("phone","")}</p>' if addr.get("phone") else ''}
        </div>"""

    discount_row = (
        f'<div class="row"><span class="label">🎉 Discount</span>'
        f'<span class="value" style="color:{BRAND_COLOR};">−₹{discount:.0f}</span></div>'
        if discount > 0 else ""
    )

    body = f"""
      <h2 style="font-size:20px;font-weight:800;margin-bottom:4px;">Order Confirmed! 🎉</h2>
      <p style="color:#6b7280;font-size:14px;margin-bottom:20px;">
        Hi <strong>{user_name}</strong>, thank you for your order. We're preparing it now!
      </p>

      {pay_note}

      <!-- Order meta -->
      <div class="section">
        <div class="section-title">Order Details</div>
        <div class="row">
          <span class="label">Order Number</span>
          <span class="value"><span class="badge">{order_number}</span></span>
        </div>
        <div class="row">
          <span class="label">Payment Method</span>
          <span class="value">{pay_label}</span>
        </div>
        <div class="row">
          <span class="label">Payment Status</span>
          <span class="value">
            <span class="status-badge {'status-paid' if payment_status == 'paid' else 'status-pending'}">
              {'✓ Paid' if payment_status == 'paid' else '⏳ Pending (COD)'}
            </span>
          </span>
        </div>
        <div class="row">
          <span class="label">Estimated Delivery</span>
          <span class="value">4–6 hours</span>
        </div>
      </div>

      <!-- Items -->
      <div class="section">
        <div class="section-title">🛒 Items Ordered</div>
        {_order_items_html(items)}
      </div>

      <!-- Price summary -->
      <div class="section">
        <div class="section-title">💰 Price Summary</div>
        <div class="row"><span class="label">Subtotal</span><span class="value">₹{subtotal:.0f}</span></div>
        <div class="row"><span class="label">Delivery</span><span class="value">{'Free' if delivery_charge == 0 else f'₹{delivery_charge:.0f}'}</span></div>
        {discount_row}
        <hr class="divider" />
        <div class="row" style="padding-top:8px;">
          <span style="font-weight:800;font-size:16px;">Total {'Due on Delivery' if is_cod else 'Paid'}</span>
          <span class="total">₹{total:.0f}</span>
        </div>
      </div>

      {addr_html}

      <!-- CTA buttons -->
      <div style="text-align:center;margin-top:24px;">
        <a href="{WEBSITE}/orders" class="btn">Track Your Order</a>
        <a href="{WEBSITE}/orders/{order_id}/invoice" class="btn-outline">📄 Download Invoice</a>
      </div>

      <p style="text-align:center;font-size:12px;color:#9ca3af;margin-top:20px;">
        Medicines will be delivered in tamper-proof packaging. 💊
      </p>
    """

    return _base_template(
        title=f"Order {order_number} Confirmed – {BRAND_NAME}",
        preheader=f"Your order {order_number} for ₹{total:.0f} has been placed successfully!",
        body_html=body,
    )


def build_payment_confirmed_email(
    user_name: str,
    order_number: str,
    order_id: int,
    total: float,
    payment_id: str,
) -> str:
    """Build the HTML body for a payment confirmation email.

    Args:
        user_name: Customer's display name.
        order_number: Human-readable order number.
        order_id: DB primary key used in the invoice URL.
        total: Amount successfully paid.
        payment_id: Razorpay payment ID for reference.

    Returns:
        Complete HTML email string.
    """
    body = f"""
      <h2 style="font-size:20px;font-weight:800;margin-bottom:4px;">Payment Successful! ✅</h2>
      <p style="color:#6b7280;font-size:14px;margin-bottom:20px;">
        Hi <strong>{user_name}</strong>, your payment has been verified and your order is confirmed.
      </p>

      <div class="highlight-box">
        💳 <strong>₹{total:.0f} paid successfully</strong> via Razorpay.
        Your order is now being prepared for dispatch.
      </div>

      <div class="section">
        <div class="section-title">Payment Details</div>
        <div class="row"><span class="label">Order Number</span><span class="value"><span class="badge">{order_number}</span></span></div>
        <div class="row"><span class="label">Amount Paid</span><span class="value total">₹{total:.0f}</span></div>
        <div class="row"><span class="label">Payment Reference</span><span class="value" style="font-size:12px;color:#6b7280;">{payment_id}</span></div>
        <div class="row"><span class="label">Status</span><span class="value"><span class="status-badge status-paid">✓ Confirmed</span></span></div>
      </div>

      <div style="text-align:center;margin-top:24px;">
        <a href="{WEBSITE}/orders" class="btn">Track Your Order</a>
        <a href="{WEBSITE}/orders/{order_id}/invoice" class="btn-outline">📄 Download Invoice</a>
      </div>
    """

    return _base_template(
        title=f"Payment Confirmed – {order_number} – {BRAND_NAME}",
        preheader=f"₹{total:.0f} paid successfully for order {order_number}.",
        body_html=body,
    )


def build_status_update_email(
    user_name: str,
    order_number: str,
    order_id: int,
    new_status: str,
    note: str = "",
) -> str:
    """Build the HTML body for an order status update email.

    Args:
        user_name: Customer's display name.
        order_number: Human-readable order number.
        order_id: DB primary key.
        new_status: New order status string (e.g. ``shipped``, ``delivered``, ``cancelled``).
        note: Optional admin note to display in the email.

    Returns:
        Complete HTML email string.
    """
    status_config = {
        "confirmed": ("✅", "Order Confirmed", BRAND_COLOR, "status-confirmed",
                      "Great news! Your order has been confirmed and will be dispatched shortly."),
        "shipped":   ("🚚", "Order Shipped", "#2563eb", "status-confirmed",
                      "Your medicines are on the way! Track your delivery using the button below."),
        "delivered": ("🎉", "Order Delivered", "#16a34a", "status-paid",
                      "Your order has been delivered. We hope you're satisfied with your purchase!"),
        "cancelled": ("❌", "Order Cancelled", "#dc2626", "status-pending",
                      "Your order has been cancelled. If you have any questions, please contact support."),
    }
    emoji, label, color, badge_cls, desc = status_config.get(
        new_status,
        ("📦", new_status.title(), BRAND_COLOR, "status-pending", "Your order status has been updated.")
    )

    note_html = (
        f'<div class="section" style="border-color:#e5e7eb;">'
        f'<div class="section-title">Note from our team</div>'
        f'<p style="font-size:13px;color:#374151;">{note}</p></div>'
        if note else ""
    )

    body = f"""
      <h2 style="font-size:20px;font-weight:800;margin-bottom:4px;">{emoji} {label}</h2>
      <p style="color:#6b7280;font-size:14px;margin-bottom:20px;">
        Hi <strong>{user_name}</strong>, {desc}
      </p>

      <div class="section">
        <div class="section-title">Order Update</div>
        <div class="row"><span class="label">Order Number</span><span class="value"><span class="badge">{order_number}</span></span></div>
        <div class="row">
          <span class="label">New Status</span>
          <span class="value"><span class="status-badge {badge_cls}" style="background-color:unset;color:{color};">
            {label}
          </span></span>
        </div>
      </div>

      {note_html}

      <div style="text-align:center;margin-top:24px;">
        <a href="{WEBSITE}/orders/{order_id}" class="btn">View Order Details</a>
      </div>
    """

    return _base_template(
        title=f"{label} – {order_number} – {BRAND_NAME}",
        preheader=f"Order {order_number} is now {new_status}.",
        body_html=body,
    )


# ─── SMS templates ────────────────────────────────────────────────────────────

def build_order_sms(order_number: str, total: float, payment_method: str) -> str:
    """Build the SMS text for an order confirmation.

    Args:
        order_number: Human-readable order number.
        total: Order total amount in INR.
        payment_method: Payment method used.

    Returns:
        Plain text SMS string (kept under 160 characters where possible).
    """
    pay = "COD" if payment_method == "cod" else "Online"
    return (
        f"Your {BRAND_NAME} order {order_number} is confirmed! "
        f"Total: Rs.{total:.0f} ({pay}). "
        f"Track at {WEBSITE}/orders. "
        f"Help: {SUPPORT_PHONE}"
    )


def build_payment_sms(order_number: str, total: float, payment_id: str) -> str:
    """Build the SMS text for a payment confirmation.

    Args:
        order_number: Human-readable order number.
        total: Amount paid in INR.
        payment_id: Razorpay payment reference ID.

    Returns:
        Plain text SMS string.
    """
    return (
        f"Payment of Rs.{total:.0f} confirmed for order {order_number} "
        f"at {BRAND_NAME}. Ref: {payment_id[:12]}... "
        f"Track: {WEBSITE}/orders"
    )


def build_status_sms(order_number: str, new_status: str) -> str:
    """Build the SMS text for an order status update.

    Args:
        order_number: Human-readable order number.
        new_status: New status string.

    Returns:
        Plain text SMS string.
    """
    status_msgs = {
        "confirmed": "confirmed and being prepared",
        "shipped":   "shipped and on its way",
        "delivered": "delivered. Enjoy!",
        "cancelled": "cancelled. Contact us for queries.",
    }
    msg = status_msgs.get(new_status, f"updated to '{new_status}'")
    return f"{BRAND_NAME}: Order {order_number} is {msg}. Track: {WEBSITE}/orders"


# ─── Transport layer ─────────────────────────────────────────────────────────

async def _send_email_async(to_email: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP in an async-friendly way.

    Runs the blocking SMTP call in a thread-pool executor so the event loop
    is not blocked.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: Full HTML email body string.

    Returns:
        True on success, False on any failure (error is logged, not raised).
    """
    if not _settings.SMTP_USER or not _settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — skipping email to %s", to_email)
        return False

    def _smtp_send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{_settings.FROM_NAME} <{_settings.FROM_EMAIL or _settings.SMTP_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(_settings.SMTP_HOST, _settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(_settings.SMTP_USER, _settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send)
        logger.info("Email sent to %s — subject: %s", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


async def _send_sms_fast2sms(phone: str, message: str) -> bool:
    """Send an SMS via the Fast2SMS Quick route API.

    Strips country code prefix and validates the number is 10 digits
    before sending.

    Args:
        phone: Mobile phone number (with or without +91 / 91 prefix).
        message: Plain-text message body.

    Returns:
        True on success, False on any failure (error is logged, not raised).

    Raises:
        No exceptions are raised; all errors are logged.
    """
    if not _settings.FAST2SMS_API_KEY:
        logger.warning("Fast2SMS API key not configured — skipping SMS to %s", phone)
        return False

    # Normalize to 10-digit Indian mobile
    digits = "".join(filter(str.isdigit, phone))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10:
        logger.warning("Invalid phone number for SMS: %s", phone)
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": _settings.FAST2SMS_API_KEY},
                data={
                    "route":    "q",        # Quick (non-DLT) route for dev/testing
                    "numbers":  digits,
                    "message":  message,
                    "language": "english",
                    "flash":    0,
                },
            )
            result = resp.json()
            if result.get("return"):
                logger.info("SMS sent to %s", digits)
                return True
            else:
                logger.error("Fast2SMS error for %s: %s", digits, result)
                return False
    except Exception as exc:
        logger.error("Failed to send SMS to %s: %s", phone, exc)
        return False


# ─── Public notification helpers ─────────────────────────────────────────────

async def notify_order_placed(
    user_email: str,
    user_name: str,
    user_phone: Optional[str],
    order_number: str,
    order_id: int,
    items: List[Dict[str, Any]],
    subtotal: float,
    delivery_charge: float,
    discount: float,
    total: float,
    payment_method: str,
    payment_status: str,
    addr: Optional[Dict[str, Any]] = None,
) -> None:
    """Send order confirmation email and SMS to the customer.

    Designed to be called as a FastAPI BackgroundTask so it never blocks the
    HTTP response.

    Args:
        user_email: Customer's email address.
        user_name: Customer's display name.
        user_phone: Customer's mobile number (may be None).
        order_number: Human-readable order number.
        order_id: DB primary key.
        items: Enriched order items list.
        subtotal: Order subtotal.
        delivery_charge: Delivery fee.
        discount: Applied discount.
        total: Final total.
        payment_method: Payment method string.
        payment_status: ``paid`` or ``pending``.
        addr: Delivery address dict (optional).

    Example:
        >>> from fastapi import BackgroundTasks
        >>> bg = BackgroundTasks()
        >>> bg.add_task(notify_order_placed, email, name, phone, ...)
    """
    html = build_order_confirmation_email(
        user_name=user_name,
        order_number=order_number,
        order_id=order_id,
        items=items,
        subtotal=subtotal,
        delivery_charge=delivery_charge,
        discount=discount,
        total=total,
        payment_method=payment_method,
        payment_status=payment_status,
        addr=addr,
    )
    await _send_email_async(
        to_email=user_email,
        subject=f"✅ Order {order_number} Confirmed – {BRAND_NAME}",
        html_body=html,
    )

    if user_phone:
        sms = build_order_sms(order_number, total, payment_method)
        await _send_sms_fast2sms(user_phone, sms)


async def notify_payment_confirmed(
    user_email: str,
    user_name: str,
    user_phone: Optional[str],
    order_number: str,
    order_id: int,
    total: float,
    payment_id: str,
) -> None:
    """Send payment confirmation email and SMS to the customer.

    Args:
        user_email: Customer's email address.
        user_name: Customer's display name.
        user_phone: Customer's mobile number (may be None).
        order_number: Human-readable order number.
        order_id: DB primary key.
        total: Amount paid.
        payment_id: Razorpay payment reference ID.
    """
    html = build_payment_confirmed_email(
        user_name=user_name,
        order_number=order_number,
        order_id=order_id,
        total=total,
        payment_id=payment_id,
    )
    await _send_email_async(
        to_email=user_email,
        subject=f"💳 Payment Confirmed – {order_number} – {BRAND_NAME}",
        html_body=html,
    )

    if user_phone:
        sms = build_payment_sms(order_number, total, payment_id)
        await _send_sms_fast2sms(user_phone, sms)


async def notify_order_status_changed(
    user_email: str,
    user_name: str,
    user_phone: Optional[str],
    order_number: str,
    order_id: int,
    new_status: str,
    note: str = "",
) -> None:
    """Send order status update email and SMS to the customer.

    Args:
        user_email: Customer's email address.
        user_name: Customer's display name.
        user_phone: Customer's mobile number (may be None).
        order_number: Human-readable order number.
        order_id: DB primary key.
        new_status: New order status string.
        note: Optional admin note to include in the email.
    """
    # Only notify for meaningful status changes
    notify_statuses = {"confirmed", "shipped", "delivered", "cancelled"}
    if new_status not in notify_statuses:
        return

    html = build_status_update_email(
        user_name=user_name,
        order_number=order_number,
        order_id=order_id,
        new_status=new_status,
        note=note,
    )
    await _send_email_async(
        to_email=user_email,
        subject=f"📦 Order {order_number} – {new_status.title()} – {BRAND_NAME}",
        html_body=html,
    )

    if user_phone:
        sms = build_status_sms(order_number, new_status)
        await _send_sms_fast2sms(user_phone, sms)
