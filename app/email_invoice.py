"""Invoice email delivery — Mourad.Soltani / ForgeLedger."""

import os
import smtplib
from email.message import EmailMessage
from typing import Optional


SUPPORTED = ("USD", "EUR", "GBP", "CAD", "AUD", "TND", "MAD", "CHF")


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def build_invoice_email(
    *,
    invoice,
    client,
    brand: dict,
    public_url: str,
) -> dict:
    studio = brand.get("studio_name") or "ForgeLedger"
    to_addr = (client.email or "").strip()
    subject = f"Invoice {invoice.number} from {studio}"
    lines = [
        f"Hello {client.name},",
        "",
        f"Please find invoice {invoice.number} for {invoice.total:,.2f} {invoice.currency}.",
        f"Status: {invoice.status}",
        f"Issue date: {invoice.issue_date}",
        "",
        "Line items:",
    ]
    for item in invoice.items:
        lines.append(
            f"  - {item.description}: {item.qty:g} × {item.unit_price:,.2f} = {item.qty * item.unit_price:,.2f}"
        )
    lines += [
        "",
        f"PDF: {public_url.rstrip('/')}/api/invoices/{invoice.id}/pdf",
        f"Pay online: use Checkout from the {studio} console, or reply to this email.",
        "",
        brand.get("footer") or "ForgeLedger · Mourad.Soltani",
    ]
    if brand.get("show_signature", True):
        lines.append("— Mourad.Soltani")
    body = "\n".join(lines)
    return {
        "to": to_addr,
        "subject": subject,
        "body": body,
        "from": os.environ.get("SMTP_FROM", "noreply@forgeledger.local"),
        "filename": f"{invoice.number}.pdf",
    }


def send_invoice_email(msg: dict, pdf_bytes: Optional[bytes] = None) -> dict:
    """Send via SMTP when configured; otherwise return demo payload."""
    if not msg.get("to"):
        return {
            "sent": False,
            "mode": "error",
            "error": "Client has no email address",
            "author": "Mourad.Soltani",
        }
    if not smtp_configured():
        return {
            "sent": False,
            "mode": "demo",
            "message": "SMTP not configured — preview only. Set SMTP_HOST and SMTP_FROM.",
            "preview": msg,
            "pdf_attached": bool(pdf_bytes),
            "pdf_bytes": len(pdf_bytes or b""),
            "author": "Mourad.Soltani",
        }
    email = EmailMessage()
    email["Subject"] = msg["subject"]
    email["From"] = msg["from"]
    email["To"] = msg["to"]
    email.set_content(msg["body"])
    if pdf_bytes:
        email.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=msg.get("filename") or "invoice.pdf",
        )
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_TLS", "1").lower() in {"1", "true", "yes"}
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(email)
        return {
            "sent": True,
            "mode": "live",
            "to": msg["to"],
            "subject": msg["subject"],
            "pdf_attached": bool(pdf_bytes),
            "author": "Mourad.Soltani",
        }
    except Exception as exc:
        return {
            "sent": False,
            "mode": "error",
            "error": str(exc),
            "author": "Mourad.Soltani",
        }
