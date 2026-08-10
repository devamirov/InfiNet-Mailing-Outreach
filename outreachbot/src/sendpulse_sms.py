"""SendPulse SMS: OAuth token and send via POST /sms/send. Phones in E.164."""
import re
from typing import Optional

import requests

from .logging_utils import get_logger
from .utils import get_env

logger = get_logger(__name__)

OAUTH_URL = "https://api.sendpulse.com/oauth/access_token"
SMS_SEND_URL = "https://api.sendpulse.com/sms/send"

# Country name (from Places) -> dial code for E.164 (no +)
COUNTRY_DIAL_CODES: dict[str, str] = {
    "lebanon": "961",
    "united arab emirates": "971",
    "uae": "971",
    "canada": "1",
    "australia": "61",
}


def _dial_code_for_country(country: str) -> Optional[str]:
    if not country:
        return None
    key = (country or "").strip().lower()
    return COUNTRY_DIAL_CODES.get(key)


def normalize_phone(phone: str, country: str) -> Optional[str]:
    """
    Normalize to E.164 digits only (no +). e.g. 04 266 8733 + UAE -> 97142668733.
    Returns None if phone empty or country unknown.
    """
    digits = re.sub(r"\D", "", (phone or "").strip())
    if not digits:
        return None
    code = _dial_code_for_country(country)
    if not code:
        logger.debug("Unknown country for dial code: %s", country)
        return None
    # If number already starts with country code, use as-is (digits only)
    if digits.startswith(code) and len(digits) >= len(code) + 6:
        return digits
    # UAE local 04... -> 971 4...
    if code == "971" and digits.startswith("4") and len(digits) == 9:
        return code + digits
    if code == "971" and digits.startswith("0") and len(digits) == 10:
        return code + digits[1:]
    # Lebanon 0... or 05... 01...
    if code == "961":
        if digits.startswith("961") and len(digits) >= 11:
            return digits
        if digits.startswith("0"):
            digits = digits[1:]
        if len(digits) == 8:
            return code + digits
    # Canada 10 digits
    if code == "1" and len(digits) == 10:
        return code + digits
    if code == "1" and digits.startswith("1") and len(digits) == 11:
        return digits
    # Australia 9 digits after 0
    if code == "61":
        if digits.startswith("61") and len(digits) >= 11:
            return digits
        if digits.startswith("0"):
            digits = digits[1:]
        if 9 <= len(digits) <= 10:
            return code + digits
    # Fallback: prepend country code if number looks local
    if len(digits) >= 6 and len(digits) <= 12:
        return code + digits.lstrip("0") if digits.startswith("0") else code + digits
    return None


def get_token() -> Optional[str]:
    """Get SendPulse OAuth access token (client_credentials)."""
    client_id = get_env("SENDPULSE_CLIENT_ID", "").strip()
    client_secret = get_env("SENDPULSE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        logger.error("SENDPULSE_CLIENT_ID and SENDPULSE_CLIENT_SECRET required in .env")
        return None
    try:
        r = requests.post(
            OAUTH_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("access_token") or "").strip() or None
    except Exception as e:
        logger.exception("SendPulse OAuth failed: %s", e)
        return None


def send_sms(
    phones: list[str],
    body: str,
    sender: str,
    route: Optional[dict[str, str]] = None,
    emulate: bool = False,
) -> dict:
    """
    Send SMS via SendPulse POST /sms/send.
    phones: list of E.164 digits (no +), e.g. ["97142668733"].
    Returns {"result": bool, "campaign_id": int, "counters": {"sends": N, "exceptions": N}}.
    """
    if not phones or not body or not sender:
        return {"result": False, "error": "phones, body, sender required"}
    token = get_token()
    if not token:
        return {"result": False, "error": "No SendPulse token"}
    payload = {
        "sender": sender[:11],
        "phones": phones,
        "body": body,
        "emulate": emulate,
    }
    if route:
        payload["route"] = route
    try:
        r = requests.post(
            SMS_SEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        logger.exception("SendPulse SMS send failed: %s", e)
        return {"result": False, "error": str(e)}
