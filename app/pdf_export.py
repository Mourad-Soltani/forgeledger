"""Invoice PDF export — Mourad.Soltani / ForgeLedger."""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def build_invoice_pdf(invoice, client, brand: dict | None = None) -> bytes:
    """Render a professional invoice PDF. brand enables white-label."""
    brand = brand or {}
    studio_name = brand.get("studio_name") or "ForgeLedger"
    footer = brand.get("footer") or "ForgeLedger · designed by Mourad.Soltani"
    show_signature = brand.get("show_signature", True)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleFL",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0b1020"),
        spaceAfter=6,
    )
    muted = ParagraphStyle(
        "MutedFL",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#5a6478"),
    )
    body = ParagraphStyle(
        "BodyFL",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    story = []
    story.append(Paragraph(studio_name, title_style))
    story.append(Paragraph(f"Invoice {invoice.number}", styles["Heading2"]))
    story.append(Spacer(1, 8))

    meta = [
        ["Issue date", str(invoice.issue_date or "")],
        ["Due date", str(invoice.due_date or "—")],
        ["Status", invoice.status.upper()],
        ["Currency", invoice.currency],
    ]
    meta_tbl = Table(meta, colWidths=[35 * mm, 60 * mm])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1a2238")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(meta_tbl)
    story.append(Spacer(1, 10))

    bill_to = f"<b>Bill to</b><br/>{client.name}"
    if client.company:
        bill_to += f"<br/>{client.company}"
    if client.email:
        bill_to += f"<br/>{client.email}"
    story.append(Paragraph(bill_to, body))
    story.append(Spacer(1, 12))

    rows = [["Description", "Qty", "Unit", "Amount"]]
    for item in invoice.items:
        amount = round(item.qty * item.unit_price, 2)
        rows.append(
            [
                item.description,
                f"{item.qty:g}",
                f"{item.unit_price:,.2f}",
                f"{amount:,.2f}",
            ]
        )
    rows.append(["", "", "Total", f"{invoice.total:,.2f} {invoice.currency}"])

    tbl = Table(rows, colWidths=[90 * mm, 20 * mm, 30 * mm, 30 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#141a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -2), 0.4, colors.HexColor("#d0d6e4")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f3fa")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tbl)

    if invoice.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>Notes</b><br/>{invoice.notes}", body))

    story.append(Spacer(1, 24))
    story.append(Paragraph(footer, muted))
    if show_signature:
        story.append(Paragraph("Signed · Mourad.Soltani", muted))

    doc.build(story)
    return buf.getvalue()
