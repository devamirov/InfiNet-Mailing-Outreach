# InfiNet outreach – setup guide

Deploy is done. **Do not run the bot** until you have:

1. Google Places API key  
2. Zoho Mail (hello@infinetmail.services) configured  
3. Zoho **app password** for SMTP  

---

## 1. Google Places API key

The bot uses **Google Places API** (Text Search + Place Details) to find businesses. You need a Google Cloud project and an API key.

### Steps

1. **Go to Google Cloud Console**  
   https://console.cloud.google.com/

2. **Create or select a project**  
   - Top bar: click the project name → **New Project** (e.g. “InfiNet Outreach”).  
   - Or use an existing project.

3. **Enable billing**  
   - **Billing** → link a billing account (Places API is paid; there is a free tier/credits for new accounts).

4. **Enable the Places API**  
   - **APIs & Services** → **Library**.  
   - Search for **“Places API”** (the one that says “Places API”, not “Places API (New)”).  
   - Open it → **Enable**.

5. **Create an API key**  
   - **APIs & Services** → **Credentials**.  
   - **+ Create Credentials** → **API key**.  
   - Copy the key (e.g. `AIzaSy...`).

6. **Restrict the key (recommended)**  
   - Click the new key → **API restrictions** → “Restrict key”.  
   - Select **Places API** only.  
   - Save.

7. **Put the key in the bot**  
   On the server (only in `/var/www/infinetmail.services/outreachbot/`):

   ```bash
   cd /var/www/infinetmail.services/outreachbot
   cp .env.example .env
   nano .env   # or vim
   ```

   Set:

   ```env
   GOOGLE_PLACES_API_KEY=your_key_here
   ```

   Save and exit. Do **not** commit `.env` or share the key.

**Docs:**  
https://developers.google.com/maps/documentation/places/web-service/get-api-key

---

## 2. Zoho Mail (hello@infinetmail.services)

You said you’re setting up Zoho for **hello@infinetmail.services**. Make sure:

- Domain **infinetmail.services** is added in Zoho (Mail → Domains).  
- MX (and any other records Zoho asks for) point to Zoho so mail is delivered.  
- You can log in to **hello@infinetmail.services** at https://mail.zoho.com (or your Zoho Mail URL).

No need to change anything in other server dirs; this is just the mailbox the bot will use.

---

## 3. Zoho app password (for SMTP)

The bot sends mail via **Zoho SMTP** (hello@infinetmail.services). Zoho requires an **app password**, not your normal account password.

### Steps

1. **Turn on 2FA**  
   - Go to https://accounts.zoho.com and sign in with the account that owns **hello@infinetmail.services**.  
   - **Security** → **Two-Factor Authentication** → enable it (SMS or authenticator app).

2. **Create an app password**  
   - Still in https://accounts.zoho.com → **Security** → **App Passwords**.  
   - **Generate New Password**.  
   - **App name**: e.g. `InfiNet Outreach Bot` (for your reference).  
   - **Generate** → you’ll get a **16-character password**.  
   - Copy it **once**; Zoho won’t show it again.

3. **Put it in the bot’s `.env`**  
   On the server, in `/var/www/infinetmail.services/outreachbot/.env`:

   ```env
   SMTP_HOST=smtp.zoho.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USER=hello@infinetmail.services
   SMTP_PASS=paste_the_16_char_app_password_here
   ```

   Use the **app password**, not your normal Zoho password.

**Zoho SMTP:**  
https://www.zoho.com/mail/help/zoho-smtp.html

---

## 4. After both are set

On the server, **only** in `/var/www/infinetmail.services/outreachbot/`:

```bash
cd /var/www/infinetmail.services/outreachbot
python3 -m src.main validate
```

If that passes, you can run:

- `python3 -m src.main run --mode dry_run`  (no real emails)  
- `python3 -m src.main run --mode live`     (real sends, warmup + limits apply)

**Reminder:** Nothing in this guide changes any other directory or site on your server; only `/var/www/infinetmail.services` is used.
