"""Send email via Zoho SMTP. Respects per-minute cap and delay."""
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from .config_loader import get_smtp_config, load_config
from .db import is_suppressed, record_email_sent
from .logging_utils import get_logger
from .templates import build_email_body, build_email_body_html, build_subject
from .utils import apply_delay, is_stop_requested

logger = get_logger(__name__)

_minute_sent_times: list[float] = []


def _trim_per_minute_cap(max_per_minute: int) -> None:
    now = time.time()
    global _minute_sent_times
    _minute_sent_times = [t for t in _minute_sent_times if now - t < 60]
    while len(_minute_sent_times) >= max_per_minute:
        time.sleep(1)
        now = time.time()
        _minute_sent_times = [t for t in _minute_sent_times if now - t < 60]


def _apply_delivery_headers(msg: MIMEMultipart, from_addr: str) -> None:
    """Set common headers that help mailbox providers classify outreach mail."""
    msg["Reply-To"] = from_addr
    msg["List-Unsubscribe"] = f"<mailto:{from_addr}?subject=unsubscribe>"


def send_one(
    to_email: str,
    lead_id: int,
    lead_name: str,
    city: str,
    dry_run: bool = False,
) -> bool:
    if is_suppressed(to_email):
        logger.info("Skip (suppressed): %s", to_email)
        return False
    smtp = get_smtp_config()
    if not smtp.get("password"):
        logger.error("SMTP password not set")
        return False
    cfg = load_config()
    subject = build_subject(lead_name, city)
    body_plain = build_email_body(lead_name, city)
    body_html = build_email_body_html(lead_name, city)
    from_addr = smtp["user"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("InfiNet", from_addr))
    msg["To"] = to_email
    _apply_delivery_headers(msg, from_addr)
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if dry_run:
        logger.info("[DRY_RUN] Would send to %s: %s", to_email, subject[:50])
        return True

    max_per_minute = cfg.get("max_emails_per_minute") or 3
    _trim_per_minute_cap(max_per_minute)

    try:
        port = int(smtp.get("port") or 587)
        if smtp.get("use_tls"):
            server = smtplib.SMTP(smtp["host"], port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp["host"], port)
        server.login(smtp["user"], smtp["password"])
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        _minute_sent_times.append(time.time())
        record_email_sent(lead_id, to_email, subject)
        logger.info("Sent to %s: %s", to_email, subject[:50])
        return True
    except Exception as e:
        logger.exception("Send failed to %s: %s", to_email, e)
        return False


def send_test_email(to_email: str, dry_run: bool = False) -> bool:
    """Send one test email (same template as real outreach, name=Test Business, city=Beirut). Does not record in DB."""
    cfg = load_config()
    subject = build_subject("Test Business", "Beirut")
    body_plain = build_email_body("Test Business", "Beirut")
    body_html = build_email_body_html("Test Business", "Beirut")
    if dry_run:
        logger.info("[DRY_RUN] Would send test to %s: %s", to_email, subject[:50])
        return True
    smtp = get_smtp_config()
    if not smtp.get("password"):
        logger.error("SMTP password not set")
        return False
    from_addr = smtp["user"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("InfiNet", from_addr))
    msg["To"] = to_email
    _apply_delivery_headers(msg, from_addr)
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    max_per_minute = cfg.get("max_emails_per_minute") or 3
    _trim_per_minute_cap(max_per_minute)
    try:
        port = int(smtp.get("port") or 587)
        if smtp.get("use_tls"):
            server = smtplib.SMTP(smtp["host"], port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp["host"], port)
        server.login(smtp["user"], smtp["password"])
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        _minute_sent_times.append(time.time())
        logger.info("Test email sent to %s: %s", to_email, subject[:50])
        return True
    except Exception as e:
        logger.exception("Send test failed to %s: %s", to_email, e)
        return False


def send_batch(
    leads: list[dict],
    dry_run: bool,
) -> int:
    cfg = load_config()
    min_d = cfg.get("delay_between_emails_min") or 12
    max_d = cfg.get("delay_between_emails_max") or 35
    sent = 0
    for lead in leads:
        if is_stop_requested():
            logger.info("STOP file detected – stopping send batch safely")
            break
        email = (lead.get("email") or "").strip()
        if not email:
            continue
        if send_one(
            email,
            lead["id"],
            lead.get("name") or "",
            lead.get("city") or "",
            dry_run=dry_run,
        ):
            sent += 1
        apply_delay(min_d, max_d)
    return sent
