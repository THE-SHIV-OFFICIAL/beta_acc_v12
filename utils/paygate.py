#MADE_BY_NOBITA
"""BETA BOT HUB payment gateway (auto-verified UPI).

Docs: https://betapaymentgateway.up.railway.app/#docs
  POST /api/v1/payments/create   -> create order (QR + pay link)
  GET  /api/v1/payments/<id>     -> {"verified": bool, "order": {"status": PENDING|PAID|EXPIRED}}
"""
import os
import aiohttp

PAYGATE_URL = os.getenv("PAYGATE_URL", "https://betapaymentgateway.up.railway.app").rstrip("/")
PAYGATE_API_KEY = os.getenv("PAYGATE_API_KEY", "").strip()

_TIMEOUT = aiohttp.ClientTimeout(total=20)


class PayGateError(Exception):
    pass


def _headers():
    if not PAYGATE_API_KEY:
        raise PayGateError("PAYGATE_API_KEY is not set")
    return {"Authorization": f"Bearer {PAYGATE_API_KEY}", "Content-Type": "application/json"}


def is_enabled() -> bool:
    return bool(PAYGATE_API_KEY)


async def create_payment(amount: int, note: str = "", customer_email: str = "") -> dict:
    """Returns the order dict: orderId, payAmount, qrImageUrl, upiUri, payUrl, expiresAt ..."""
    body = {"amount": amount, "note": note}
    if customer_email:
        body["customerEmail"] = customer_email
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
        async with s.post(f"{PAYGATE_URL}/api/v1/payments/create", json=body, headers=_headers()) as r:
            data = await r.json(content_type=None)
    if not data.get("success") or not data.get("order", {}).get("orderId"):
        raise PayGateError(str(data.get("error") or data.get("message") or data))
    return data["order"]


async def get_status(order_id: str) -> tuple[str, bool, dict]:
    """Returns (status, verified, order)."""
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
        async with s.get(f"{PAYGATE_URL}/api/v1/payments/{order_id}", headers=_headers()) as r:
            data = await r.json(content_type=None)
    order = data.get("order") or {}
    return str(order.get("status", "PENDING")).upper(), bool(data.get("verified")), order
