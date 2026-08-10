"""Load config.yaml and env; expose unified config."""
import os
from pathlib import Path
from typing import Any

import yaml

from .utils import get_env


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return _default_config()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {**_default_config(), **data}


def _default_config() -> dict[str, Any]:
    return {
        "promo": {
            "headline": "Affordable website & app packages this month",
            "tagline": "Professional web, mobile app, automation & security – at a price that fits.",
        },
        "main_site": "https://infinet.services",
        "landing_page": "https://infinetmail.services",
        "opt_out_line": "If you'd prefer I don't contact you again, just reply 'stop'.",
        "locations": {},
        "industries": [],
        "warmup_daily_caps": {1: 5, 2: 8, 3: 10, 4: 12, 5: 15, 6: 18, "default": 20},
        "delay_between_emails_min": 12,
        "delay_between_emails_max": 35,
        "max_emails_per_minute": 3,
    }


def get_smtp_config() -> dict[str, str]:
    return {
        "host": get_env("SMTP_HOST", "smtp.zoho.com"),
        "port": get_env("SMTP_PORT", "587"),
        "use_tls": get_env("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
        "user": get_env("SMTP_USER", "hello@infinetmail.services"),
        "password": get_env("SMTP_PASS", ""),
    }


def get_google_api_key() -> str:
    return get_env("GOOGLE_PLACES_API_KEY", "")


def get_sms_config() -> dict[str, Any]:
    cfg = load_config()
    sms = cfg.get("sms") or {}
    return {
        "sender": (sms.get("sender") or "InfiNet").strip()[:11],
        "body": (sms.get("body") or "InfiNet: https://infinetmail.services").strip(),
        "daily_cap": int(sms.get("daily_cap") or 30),
    }
