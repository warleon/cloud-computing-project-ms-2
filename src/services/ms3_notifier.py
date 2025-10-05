import os
import httpx
import logging
from typing import TypedDict, Literal, Dict, Any

logger = logging.getLogger("ms3_notifier")

# ============================================================
# Configuración desde variables de entorno
# ============================================================
MS3_NOTIFY_ENABLED = os.getenv("MS3_NOTIFY_ENABLED", "false").lower() == "true"
MS3_NOTIFY_URL = os.getenv("MS3_NOTIFY_URL", "").rstrip("/")
MS3_NOTIFY_TIMEOUT = float(os.getenv("MS3_NOTIFY_TIMEOUT", "2.5"))
MS3_NOTIFY_KEY = os.getenv("MS3_NOTIFY_KEY", "")

EventType = Literal["account.balance.updated"]

class BalanceData(TypedDict):
    accountId: str
    balance: Dict[str, Any]

class BalanceUpdateEvent(TypedDict):
    type: EventType
    data: BalanceData


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if MS3_NOTIFY_KEY:
        headers["x-service-key"] = MS3_NOTIFY_KEY
    return headers


# ============================================================
# Función principal: Notificar cambio de balance al MS3
# ============================================================
async def notify_balance_updated(account_id: str, new_balance: float, currency: str) -> None:
    """Envía un evento HTTP POST al MS3 cuando cambia el balance."""
    if not MS3_NOTIFY_ENABLED or not MS3_NOTIFY_URL:
        logger.debug("MS3 notifications disabled or URL not set.")
        return

    payload: BalanceUpdateEvent = {
        "type": "account.balance.updated",
        "data": {
            "accountId": account_id,
            "balance": {"value": new_balance, "currency": currency},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=MS3_NOTIFY_TIMEOUT) as client:
            response = await client.post(MS3_NOTIFY_URL, json=payload, headers=_headers())
            if response.status_code >= 400:
                logger.warning(f"[MS3] Notification failed ({response.status_code}): {response.text}")
            else:
                logger.info(f"[MS3] Balance update sent for account {account_id}")
    except Exception as e:
        logger.error(f"[MS3] Failed to send balance update: {e}")
