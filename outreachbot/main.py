"""
InfiNet outreach bot – discover businesses (no website/app), store leads, send promo emails.
Commands: validate | run --mode dry_run | run --mode live | report
"""
import argparse
import sys
from pathlib import Path

# Load .env from project root before any config/DB
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from datetime import datetime, timezone

from .config_loader import get_google_api_key, load_config, get_smtp_config, get_sms_config
from .db import (
    count_emails_sent_today,
    count_emails_sent_total,
    count_leads,
    count_leads_with_email,
    get_leads_with_email_not_sent,
    get_leads_with_phone_not_sent_sms,
    get_run_state,
    init_db,
    is_suppressed,
    record_sms_sent,
    set_run_state,
    count_sms_sent_today,
)
from .dedupe import ensure_place_id_unique
from .google_places import fetch_and_store_leads
from .logging_utils import get_logger, setup_logging
from .mailer import send_batch, send_test_email
from .sendpulse_sms import normalize_phone, send_sms
from .utils import is_stop_requested, project_root

logger = get_logger(__name__)

WARMUP_START_KEY = "warmup_start_date"


def _warmup_day() -> int:
    """Day 1, 2, 3... from warmup start. If never set, today is day 1."""
    start = get_run_state(WARMUP_START_KEY)
    if not start:
        set_run_state(WARMUP_START_KEY, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        return 1
    try:
        start_d = datetime.strptime(start, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        delta = (today - start_d).days
        return max(1, delta + 1)
    except Exception:
        return 1


def _daily_cap() -> int:
    cfg = load_config()
    caps = cfg.get("warmup_daily_caps") or {}
    day = _warmup_day()
    if day in caps:
        return int(caps[day])
    return int(caps.get("default") or 20)


def cmd_validate() -> int:
    setup_logging()
    logger.info("Validating configuration...")
    key = get_google_api_key()
    if not key:
        logger.error("GOOGLE_PLACES_API_KEY not set (check .env)")
        return 1
    smtp = get_smtp_config()
    if not smtp.get("password"):
        logger.warning("SMTP_PASS not set – sending will fail")
    else:
        logger.info("SMTP configured for %s", smtp.get("user"))
    cfg = load_config()
    locs = list(cfg.get("locations") or {})
    inds = len(cfg.get("industries") or [])
    logger.info("Config: %s locations, %s industries", len(locs), inds)
    logger.info("Validate OK")
    return 0


def cmd_run(mode: str) -> int:
    setup_logging()
    if mode not in ("dry_run", "live"):
        logger.error("Mode must be dry_run or live")
        return 1
    dry_run = mode == "dry_run"
    if dry_run:
        logger.info("DRY_RUN – no emails will be sent")

    init_db()
    ensure_place_id_unique()

    cfg = load_config()
    locations = cfg.get("locations") or {}
    industries = cfg.get("industries") or []

    # 1) Discover and store leads (no website filter in google_places)
    logger.info("Fetching leads from Google Places (no website / no app)...")
    try:
        added = fetch_and_store_leads(locations, industries)
        logger.info("Stored %s new target leads", added)
    except Exception as e:
        logger.exception("Places fetch failed: %s", e)
        return 1

    if is_stop_requested():
        logger.info("STOP file detected – exiting safely")
        return 0

    # 2) Cap by warmup
    cap = _daily_cap()
    sent_today = count_emails_sent_today()
    remaining = max(0, cap - sent_today)
    if remaining <= 0:
        logger.info("Daily cap reached (%s). Sent today: %s. Exiting.", cap, sent_today)
        return 0

    # 3) Get leads with email, not yet sent, not suppressed
    candidates = get_leads_with_email_not_sent(limit=remaining)
    if not candidates:
        logger.info("No leads with email left to contact")
        return 0

    logger.info("Sending to %s leads (cap %s, sent today %s)", len(candidates), cap, sent_today)
    sent = send_batch(candidates, dry_run=dry_run)
    logger.info("Done. Sent (or dry-run) %s emails.", sent)
    return 0


def cmd_send_test(to_email: str | None, dry_run: bool) -> int:
    setup_logging()
    cfg = load_config()
    email = (to_email or (cfg.get("test_email") or "").strip()) or None
    if not email:
        logger.error("No test email. Set test_email in config.yaml or use --to your@email.com")
        return 1
    init_db()
    ok = send_test_email(email, dry_run=dry_run)
    return 0 if ok else 1


def cmd_send_test_sms(dry_run: bool) -> int:
    """Send a single test SMS to test_phone (config), e.g. +17473508060."""
    setup_logging()
    cfg = load_config()
    raw = (cfg.get("test_phone") or "+17473508060").strip()
    phone_e164 = "".join(c for c in raw if c.isdigit())
    if not phone_e164 or len(phone_e164) < 10:
        phone_e164 = "17473508060"
    sms_cfg = get_sms_config()
    test_body = f'{sms_cfg["body"]} [test {datetime.now(timezone.utc).strftime("%H%M%S")}]'
    if dry_run:
        logger.info("DRY_RUN SMS to %s: %s", phone_e164, test_body[:70] + "...")
        return 0
    result = send_sms(
        phones=[phone_e164],
        body=test_body,
        sender=sms_cfg["sender"],
        emulate=False,
    )
    if not result.get("result"):
        logger.error("Test SMS failed: %s", result.get("error", result))
        return 1
    logger.info("Test SMS sent to %s", phone_e164)
    return 0


def cmd_run_sms(dry_run: bool) -> int:
    """Send SMS to leads with phone (from Google Places) via SendPulse. Respects daily cap."""
    setup_logging()
    if dry_run:
        logger.info("SMS DRY_RUN – no SMS will be sent")

    init_db()
    ensure_place_id_unique()

    cfg = load_config()
    locations = cfg.get("locations") or {}
    industries = cfg.get("industries") or []

    logger.info("Fetching leads from Google Places (no website)...")
    try:
        added = fetch_and_store_leads(locations, industries)
        logger.info("Stored %s new target leads", added)
    except Exception as e:
        logger.exception("Places fetch failed: %s", e)
        return 1

    if is_stop_requested():
        logger.info("STOP file detected – exiting safely")
        return 0

    sms_cfg = get_sms_config()
    cap = sms_cfg["daily_cap"]
    sent_today = count_sms_sent_today()
    remaining = max(0, cap - sent_today)
    if remaining <= 0:
        logger.info("SMS daily cap reached (%s). Sent today: %s. Exiting.", cap, sent_today)
        return 0

    candidates = get_leads_with_phone_not_sent_sms(limit=remaining)
    if not candidates:
        logger.info("No leads with phone left to contact (SMS)")
        return 0

    # Normalize phones to E.164; skip suppressed
    to_send: list[tuple[int, str]] = []
    for lead in candidates:
        phone_e164 = normalize_phone(lead.get("phone") or "", lead.get("country") or "")
        if not phone_e164:
            continue
        if is_suppressed(phone_e164):
            continue
        to_send.append((lead["id"], phone_e164))

    if not to_send:
        logger.info("No valid E.164 phones after normalization/suppression")
        return 0

    logger.info("Sending SMS to %s leads (cap %s, sent today %s)", len(to_send), cap, sent_today)
    if dry_run:
        for lead_id, phone in to_send:
            logger.info("DRY_RUN SMS to lead_id=%s phone=%s", lead_id, phone)
        return 0

    phones = [p for _, p in to_send]
    lead_ids = [lid for lid, _ in to_send]
    result = send_sms(
        phones=phones,
        body=sms_cfg["body"],
        sender=sms_cfg["sender"],
        emulate=False,
    )
    if not result.get("result"):
        logger.error("SendPulse SMS failed: %s", result.get("error", result))
        return 1
    for lead_id, phone in to_send:
        record_sms_sent(lead_id, phone)
    logger.info("Sent %s SMS via SendPulse.", len(to_send))
    return 0


def cmd_report() -> int:
    setup_logging()
    init_db()
    total_leads = count_leads()
    with_email = count_leads_with_email()
    sent_total = count_emails_sent_total()
    sent_today = count_emails_sent_today()
    cap = _daily_cap()
    day = _warmup_day()
    logger.info("--- Report ---")
    logger.info("Leads in DB: %s (with email: %s)", total_leads, with_email)
    logger.info("Emails sent total: %s | today: %s", sent_total, sent_today)
    logger.info("Warmup day: %s | daily cap: %s", day, cap)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="InfiNet outreach bot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    run_p = sub.add_parser("run")
    run_p.add_argument("--mode", choices=("dry_run", "live"), required=True)
    sub.add_parser("report")
    sms_p = sub.add_parser("run_sms")
    sms_p.add_argument("--dry_run", action="store_true", help="Log only, do not send SMS")
    test_p = sub.add_parser("send_test")
    test_p.add_argument("--to", dest="test_to", default=None, help="Override test email address")
    test_p.add_argument("--dry_run", action="store_true", help="Log only, do not send")
    test_sms_p = sub.add_parser("send_test_sms")
    test_sms_p.add_argument("--dry_run", action="store_true", help="Log only, do not send SMS")

    args = parser.parse_args()
    if args.command == "validate":
        return cmd_validate()
    if args.command == "run":
        return cmd_run(args.mode)
    if args.command == "report":
        return cmd_report()
    if args.command == "run_sms":
        return cmd_run_sms(getattr(args, "dry_run", False))
    if args.command == "send_test":
        return cmd_send_test(args.test_to, args.dry_run)
    if args.command == "send_test_sms":
        return cmd_send_test_sms(getattr(args, "dry_run", False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
