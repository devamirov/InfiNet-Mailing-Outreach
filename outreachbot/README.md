# InfiNet outreach bot

Finds businesses **without a website** (Google Places), stores them, and sends promo emails via Zoho (hello@infinetmail.services). Promo text is in `config.yaml`.

## Setup

```bash
cp .env.example .env
# Set GOOGLE_PLACES_API_KEY and SMTP_PASS
pip install -r requirements.txt
python -m src.main validate
```

## Commands

- `python -m src.main validate` – check API key and SMTP config
- `python -m src.main run --mode dry_run` – run pipeline, no real emails
- `python -m src.main run --mode live` – run and send (respects warmup + STOP file)
- `python -m src.main report` – leads count, emails sent, warmup day/cap

## Config

- **Promo / copy:** `config.yaml` (headline, tagline, locations, industries, limits). No code changes needed.
- **Secrets:** `.env` (Google API key, Zoho SMTP password).

## Safety

- Create a file named `STOP` in this folder (same level as `config.yaml`) to stop sending safely.
- Warmup caps and per-minute limit are in `config.yaml`.
