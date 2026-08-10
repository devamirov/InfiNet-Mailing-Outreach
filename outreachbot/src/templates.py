"""Plain-text email template. Uses config for promo and opt-out. Optional file: email_template.txt."""
from pathlib import Path

from .config_loader import load_config


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _template_file_path() -> Path:
    return _project_root() / "email_template.txt"


def _default_body(landing: str, main_site: str, opt_out: str) -> str:
    return f"""Professional digital solutions for your business — including websites, mobile apps, automation systems, and security audits — delivered at a price that fits your budget.

Whether you're launching a new idea, improving your online presence, or optimizing your operations, InfiNet provides reliable and scalable solutions tailored to your needs.

Explore our packages:
{landing}

Learn more about InfiNet:
{main_site}

Best regards,
InfiNet Team

{opt_out}
"""


def build_email_body(lead_name: str, city: str) -> str:
    cfg = load_config()
    landing = cfg.get("landing_page") or "https://infinetmail.services"
    main_site = cfg.get("main_site") or "https://infinet.services"
    opt_out = cfg.get("opt_out_line") or "If you'd prefer I don't contact you again, just reply 'stop'."

    template_path = _template_file_path()
    if template_path.exists():
        try:
            raw = template_path.read_text(encoding="utf-8")
            return raw.replace("{landing_page}", landing).replace("{main_site}", main_site).replace("{opt_out_line}", opt_out)
        except Exception:
            pass
    return _default_body(landing, main_site, opt_out)


def build_email_body_html(lead_name: str, city: str) -> str:
    """HTML email with same bg/card style as infinet.services booking emails."""
    cfg = load_config()
    promo = cfg.get("promo") or {}
    headline = promo.get("headline") or "Professional Web, App, Automation & Security Solutions"
    landing = (cfg.get("landing_page") or "https://infinetmail.services").strip()
    main_site = (cfg.get("main_site") or "https://infinet.services").strip()
    if not landing.startswith("http"):
        landing = "https://" + landing
    if not main_site.startswith("http"):
        main_site = "https://" + main_site
    opt_out = cfg.get("opt_out_line") or "If you'd prefer I don't contact you again, just reply 'stop'."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InfiNet – {headline[:50]}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #72FF13 0%, #72FF13 30%, #00F0FF 30%, #00F0FF 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #000000; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">InfiNet</h1>
                            <p style="margin: 12px 0 0 0; color: #000000; font-size: 16px; opacity: 0.95;">{headline}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <div style="background: linear-gradient(135deg, #E0F7FF 0%, #E0F7FF 100%); padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #060097;">
                                <p style="margin: 8px 0; color: #000000; font-size: 14px; line-height: 1.6;">Professional digital solutions for your business — including websites, mobile apps, automation systems, and security audits — delivered at a price that fits your budget.</p>
                                <p style="margin: 12px 0 8px 0; color: #000000; font-size: 14px; line-height: 1.6;">Whether you're launching a new idea, improving your online presence, or optimizing your operations, InfiNet provides reliable and scalable solutions tailored to your needs.</p>
                                <p style="margin: 16px 0 4px 0; color: #000000; font-size: 14px; line-height: 1.6;">Explore our packages:</p>
                                <p style="margin: 4px 0 12px 0; color: #000000; font-size: 14px; line-height: 1.6;"><a href="{landing}" target="_blank" style="color: #060097; text-decoration: underline;">{landing}</a></p>
                                <p style="margin: 16px 0 4px 0; color: #000000; font-size: 14px; line-height: 1.6;">Learn more about InfiNet:</p>
                                <p style="margin: 4px 0 0 0; color: #000000; font-size: 14px; line-height: 1.6;"><a href="{main_site}" target="_blank" style="color: #060097; text-decoration: underline;">{main_site}</a></p>
                            </div>
                            <p style="margin: 0 0 16px 0; color: #333333; font-size: 16px; line-height: 1.6;">Best regards,<br>InfiNet Team</p>
                            <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.6;"><strong>{opt_out}</strong></p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px; background: linear-gradient(135deg, #E6FFE6 0%, #E0F7FF 100%); border-top: 1px solid #B0E0FF; text-align: center;">
                            <p style="margin: 0; color: #666666; font-size: 12px;">© InfiNet. All rights reserved.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def build_subject(lead_name: str, city: str) -> str:
    cfg = load_config()
    promo = cfg.get("promo") or {}
    headline = (promo.get("headline") or promo.get("tagline") or "Website & app offer").strip()
    name = (lead_name or "").strip()
    city_part = f" – {city}" if (city or "").strip() else ""
    if name and len(name) < 30:
        return f"{headline} for {name}{city_part}"
    return f"{headline}{city_part}"
