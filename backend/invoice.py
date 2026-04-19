import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

GREEN       = colors.HexColor("#0F6E56")
GREEN_LIGHT = colors.HexColor("#E1F5EE")
GREEN_DARK  = colors.HexColor("#0A4D3C")
AMBER       = colors.HexColor("#BA7517")

# Usable page width: A4 210mm − 18mm left − 18mm right = 174mm
PAGE_W = 174 * mm

def generate_invoice_pdf(order_id: int, invoice_number: str, enriched: list, meta: dict) -> str:
    """Generate a professional invoice PDF for an order.

    Args:
        order_id: Database ID of the order.
        invoice_number: Human-readable invoice identifier (e.g. INV-ORD-123456).
        enriched: List of dicts with keys 'variant' and 'item'.
        meta: Dict containing total, subtotal, delivery_charge, discount,
              order_number, addr, payment_method, payment_status.

    Returns:
        Absolute file path of the generated PDF, or empty string on failure.
    """
    try:
        os.makedirs("./public/invoices", exist_ok=True)
        path = f"./public/invoices/{invoice_number}.pdf"

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            leftMargin=18*mm, rightMargin=18*mm,
            topMargin=18*mm, bottomMargin=16*mm,
        )

        def style(name, **kw):
            return ParagraphStyle(name, **kw)

        brand   = style("Brand",  fontSize=20, textColor=GREEN,    fontName="Helvetica-Bold", leading=24)
        tagline = style("Tag",    fontSize=8,  textColor=colors.HexColor("#666666"), leading=12, spaceBefore=2)
        h2      = style("H2",     fontSize=10, textColor=GREEN,    fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
        normal  = style("Nm",     fontSize=9,  textColor=colors.HexColor("#333333"), leading=14)
        right   = style("Rt",     fontSize=9,  alignment=TA_RIGHT, textColor=colors.HexColor("#333333"), leading=15)
        footer  = style("Ft",     fontSize=8,  alignment=TA_CENTER, textColor=colors.gray, spaceBefore=6, leading=13)

        story = []

        # ── Header: left = brand block, right = invoice meta ─────────────
        # Use fixed mm column widths to avoid ReportLab percentage rendering issues.
        left_w  = PAGE_W * 0.55   # ~95.7 mm
        right_w = PAGE_W * 0.45   # ~78.3 mm

        # Merged into one Paragraph: avoids ReportLab multi-flowable cell-height
        # mis-calculation that caused the header to overlap content below.
        # leading=30 gives enough clearance for the 20pt brand glyph ascenders.
        brand_cell = Paragraph(
            "<font name='Helvetica-Bold' size='20' color='#0F6E56'>MathuraPharmeasy</font><br/>"
            "<font size='8' color='#666666'>Online Pharmacy &amp; Healthcare</font>",
            style("BrandBlock", leading=30, spaceBefore=0, spaceAfter=0),
        )
        meta_cell = Paragraph(
            "<b>TAX INVOICE</b><br/>"
            f"Invoice No: &nbsp;<b>{invoice_number}</b><br/>"
            f"Order No: &nbsp;<b>{meta['order_number']}</b><br/>"
            f"Date: &nbsp;<b>{datetime.now().strftime('%d %B %Y')}</b>",
            right,
        )

        header_tbl = Table([[brand_cell, meta_cell]], colWidths=[left_w, right_w])
        header_tbl.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_tbl)
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=2.5, color=GREEN, spaceAfter=10))

        # ── Address + Payment ────────────────────────────────
        addr = meta.get("addr") or {}
        pay_map = {"upi":"UPI Payment","card":"Card Payment","cod":"Cash on Delivery","netbanking":"Net Banking","razorpay":"Razorpay"}

        # Determine human-readable payment status label
        payment_method = meta.get("payment_method", "")
        payment_status = meta.get("payment_status", "pending")
        if payment_status == "paid":
            status_label = "Paid"
            status_color = "#0F6E56"
        else:
            status_label = "Pending – Pay on Delivery" if payment_method == "cod" else "Pending"
            status_color = "#BA7517"

        half_w = PAGE_W / 2

        addr_tbl = Table([[
            [Paragraph("<b>Delivery Address</b>", h2),
             Paragraph(
                 f"{addr.get('name','')}<br/>"
                 f"{addr.get('line1','')} {addr.get('line2') or ''}<br/>"
                 f"{addr.get('city','')} - {addr.get('pin','')}<br/>"
                 f"Ph: {addr.get('phone','')}",
                 normal,
             )],
            [Paragraph("<b>Payment Details</b>", h2),
             Paragraph(
                 f"Method: {pay_map.get(payment_method, '—')}<br/>"
                 f"Status: <font color='{status_color}'><b>{status_label}</b></font><br/>"
                 f"Amount: <b>Rs.{meta['total']:.2f}</b>",
                 normal,
             )],
        ]], colWidths=[half_w, half_w])
        addr_tbl.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("BACKGROUND",(0,0),(0,-1),GREEN_LIGHT),
            ("BACKGROUND",(1,0),(1,-1),colors.HexColor("#FFF8ED")),
            ("BOX",(0,0),(-1,-1),0.5,colors.lightgrey),
            ("LINEAFTER",(0,0),(0,-1),0.5,colors.lightgrey),
            ("TOPPADDING",(0,0),(-1,-1),8),
            ("BOTTOMPADDING",(0,0),(-1,-1),8),
            ("LEFTPADDING",(0,0),(-1,-1),10),
        ]))
        story.append(addr_tbl)
        story.append(Spacer(1, 10))

        # ── Items table ───────────────────────────────────────
        story.append(Paragraph("Order Items", h2))
        rows = [["#", "Medicine", "Variant / Pack", "Qty", "Unit Price", "Amount"]]
        for idx, e in enumerate(enriched, 1):
            v, item = e["variant"], e["item"]
            rows.append([
                str(idx),
                v["med_name"],
                v["label"],
                str(item.quantity),
                f"Rs.{float(v['price']):.2f}",
                f"Rs.{float(v['price']) * item.quantity:.2f}"
            ])

        # Column widths must sum to PAGE_W (174 mm)
        items_tbl = Table(rows, colWidths=[8*mm, 63*mm, 46*mm, 14*mm, 22*mm, 21*mm])
        items_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0),  GREEN),
            ("TEXTCOLOR",    (0,0), (-1,0),  colors.white),
            ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREEN_LIGHT]),
            ("GRID",         (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
            ("ALIGN",        (3,0), (-1,-1), "RIGHT"),
            ("ALIGN",        (0,0), (0,-1),  "CENTER"),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ]))
        story.append(items_tbl)
        story.append(Spacer(1, 10))

        # ── Summary ───────────────────────────────────────────
        summary = [
            ["", "Subtotal",       f"Rs.{meta['subtotal']:.2f}"],
            ["", "Delivery Charge", "Free" if meta["delivery_charge"]==0 else f"Rs.{meta['delivery_charge']:.2f}"],
        ]
        if meta.get("discount", 0) > 0:
            summary.append(["", "Discount (5%)", f"- Rs.{meta['discount']:.2f}"])
        summary.append(["", "GRAND TOTAL", f"Rs.{meta['total']:.2f}"])

        # Spacer col (88mm) + label col (52mm) + amount col (34mm) = 174mm
        sum_tbl = Table(summary, colWidths=[88*mm, 52*mm, 34*mm], hAlign="RIGHT")
        sum_style = [
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("ALIGN",       (2,0), (2,-1),  "RIGHT"),
            ("LINEABOVE",   (1,-1), (-1,-1), 1.5, GREEN),
            ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
            ("TEXTCOLOR",   (1,-1), (-1,-1), GREEN),
            ("FONTSIZE",    (0,-1), (-1,-1), 11),
            ("TOPPADDING",  (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ]
        sum_tbl.setStyle(TableStyle(sum_style))
        story.append(sum_tbl)
        story.append(Spacer(1, 16))

        # ── Footer ────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=4))
        story.append(Paragraph(
            "Thank you for choosing <b>MathuraPharmeasy</b>! &nbsp;|&nbsp; "
            "support@mathurapharmeasy.in &nbsp;|&nbsp; www.mathurapharmeasy.in",
            footer,
        ))
        story.append(Paragraph(
            "<font color='gray' size='7'>"
            "This is a computer-generated invoice and does not require a signature."
            "</font>",
            footer,
        ))

        doc.build(story)
        return path
    except Exception as e:
        print(f"[Invoice PDF Error] {e}")
        return ""
