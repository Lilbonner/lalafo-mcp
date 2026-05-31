"""Notification channels for subscription matches (stdlib only, all env-gated).

Configure any subset via env; messages go to every configured channel:
  - NTFY_TOPIC_URL          e.g. https://ntfy.sh/my-lalafo-topic
  - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  - WEBHOOK_URL             receives JSON {title, body, items}
If none are set, send() is a no-op and returns [].
"""
import json
import os
import urllib.request

_TIMEOUT = 15


def _post(url, *, data: bytes | None = None, json_body=None, headers=None):
    h = {"User-Agent": "lalafo-mcp/0.1"}
    if headers:
        h.update(headers)
    body = data
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return r.status


def configured_channels() -> list[str]:
    ch = []
    if os.getenv("NTFY_TOPIC_URL"):
        ch.append("ntfy")
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        ch.append("telegram")
    if os.getenv("WEBHOOK_URL"):
        ch.append("webhook")
    return ch


def send(title: str, body: str, items: list | None = None) -> list[str]:
    """Send to every configured channel. Returns the list of channels that succeeded."""
    sent = []

    url = os.getenv("NTFY_TOPIC_URL")
    if url:
        try:  # title in body to avoid non-ASCII HTTP header issues
            _post(url, data=f"{title}\n\n{body}".encode("utf-8"))
            sent.append("ntfy")
        except Exception:
            pass

    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            _post(f"https://api.telegram.org/bot{tok}/sendMessage",
                  json_body={"chat_id": chat, "text": f"{title}\n\n{body}"[:4000],
                             "disable_web_page_preview": True})
            sent.append("telegram")
        except Exception:
            pass

    wh = os.getenv("WEBHOOK_URL")
    if wh:
        try:
            _post(wh, json_body={"title": title, "body": body, "items": items or []})
            sent.append("webhook")
        except Exception:
            pass

    return sent
