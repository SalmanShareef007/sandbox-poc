import html
import logging
import re
import threading
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SANDBOX_REFERENCE = re.compile(r"\bSBX-\d+\b")
_ACCENTS = {"Budget": "#b45309", "Approval": "#b91c1c", "Lifecycle": "#0e7490"}


def base_url() -> str:
    configured = settings.FRONTEND_BASE_URL or (settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "")
    return configured.rstrip("/")


def link_for(title: str, admins: bool) -> str:
    """Deep link to the sandbox named in the title, or to the admin queue / notification list."""
    root = base_url()
    if not root:
        return ""
    match = _SANDBOX_REFERENCE.search(title)
    if match:
        return f"{root}/sandboxes/{match.group(0)}" if not admins else f"{root}/admin/approvals"
    return f"{root}/admin/approvals" if admins else f"{root}/notifications"


def render_email(title: str, category: str, link: str) -> tuple[str, str, str]:
    """Returns (subject, plain text, html). All dynamic values are HTML-escaped."""
    subject = f"Azure Sandbox: {title}"[:200]
    safe_title = html.escape(title)
    accent = _ACCENTS.get(category, "#1d4ed8")
    button = (
        f'<p style="margin:24px 0 0"><a href="{html.escape(link, quote=True)}" '
        f'style="background:{accent};color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;'
        f'font-weight:600;display:inline-block">Open in Azure Sandbox</a></p>'
        if link else ""
    )
    body = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;border:1px solid #e5e7eb;'
        'border-radius:8px;overflow:hidden">'
        f'<div style="background:{accent};color:#ffffff;padding:14px 20px;font-weight:600">'
        f'Azure Sandbox · {html.escape(category)}</div>'
        f'<div style="padding:20px;color:#111827;font-size:15px;line-height:1.5"><p style="margin:0">{safe_title}</p>{button}</div>'
        '<div style="padding:12px 20px;background:#f9fafb;color:#6b7280;font-size:12px">'
        "You are receiving this because of your role on this sandbox.</div></div>"
    )
    plain = f"{title}\n\nOpen: {link}" if link else title
    return subject, plain, body


def _webhook_payload(url: str, category: str, title: str, link: str) -> dict:
    text = f"[{category}] {title}" + (f"\n{link}" if link else "")
    host = urlparse(url).hostname or ""
    if host.endswith("slack.com"):
        return {"text": text}
    card = {
        "type": "AdaptiveCard", "version": "1.4", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {"type": "TextBlock", "text": f"Azure Sandbox · {category}", "weight": "Bolder"},
            {"type": "TextBlock", "text": title, "wrap": True},
        ],
        "actions": [{"type": "Action.OpenUrl", "title": "Open", "url": link}] if link else [],
    }
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}]}


def _post(url: str, payload: dict) -> None:
    try:
        response = httpx.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as exc:  # the webhook must never break the request that triggered it
        logger.warning("Admin webhook delivery failed: %s", type(exc).__name__)


def send_admin_webhook(category: str, title: str, link: str) -> None:
    """Fire-and-forget post to the configured Teams/Slack webhook."""
    if not settings.ADMIN_WEBHOOK_URL:
        return
    url = settings.ADMIN_WEBHOOK_URL.get_secret_value()
    if urlparse(url).scheme != "https":
        logger.warning("ADMIN_WEBHOOK_URL must use https; skipping webhook.")
        return
    threading.Thread(target=_post, args=(url, _webhook_payload(url, category, title, link)), daemon=True).start()
