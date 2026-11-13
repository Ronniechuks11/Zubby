# Valora Digital — Flask site

The Valora Digital landing page as a Flask application: Jinja templates, extracted static assets, and a working contact form (validated, CSRF-protected, rate-limited, stored in SQLite, optional e-mail alert). The design, copy and animations are unchanged from the original single-file page.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # APP_ENV=development is preset
flask --app wsgi run --debug                           # http://127.0.0.1:5000
```

Run the tests with `pytest`.

## Project layout

```
wsgi.py                      entry point (flask --app wsgi / gunicorn wsgi:app)
valora_digital/
  __init__.py                app factory, error pages, template helpers
  config.py                  settings, all read from environment / .env
  content.py                 page copy as data (services, process, work, stats, ...)
  routes.py                  /, POST /contact, /healthz, /robots.txt, /sitemap.xml
  forms.py                   contact-form validation and sanitising
  security.py                CSRF, rate limiter, security headers (CSP, HSTS, ...)
  db.py                      SQLite storage + CLI commands
  mailer.py                  optional SMTP alert for new enquiries
  templates/                 base.html, index.html, partials/ (one per section), errors/
public/static/               css/main.css, js/main.js, img/favicon.svg (served at /static/...)
tests/                       pytest suite
```

## Before you go live

These are still the placeholders from the original design — set them in `.env`/the environment or edit `content.py`:

| What | Where |
| --- | --- |
| WhatsApp number (currently `000000000000`) | `WHATSAPP_NUMBER` |
| Contact e-mail (currently `hello@valoradigital.example`) | `CONTACT_EMAIL` |
| Social links (footer icons currently link to `#`) | `SOCIAL_INSTAGRAM`, `SOCIAL_FACEBOOK`, `SOCIAL_TIKTOK`, `SOCIAL_LINKEDIN`, `SOCIAL_X` |
| "Selected work" cards and the three stats (labelled `PLACEHOLDER`) | `WORK`, `STATS` in `content.py` |
| Illustrative metric chips on the phone mock-up (128.4K reach, ₦1,240 CPL) | `METRIC_CHIPS` in `content.py` |
| Public URL (canonical tag, robots.txt, sitemap) | `SITE_URL` |

## Contact form

- Posts to `/contact`. With JavaScript it submits via `fetch` and shows the result in place; without it the form posts normally and redirects back to the page (`303`) with the message shown.
- Server-side checks: CSRF token, field lengths, email-or-phone format, budget must be one of the listed options, hidden honeypot field, and a per-IP rate limit (default 5 valid submissions per hour).
- Enquiries are saved to SQLite (`instance/valora.sqlite3`, or `DATABASE_PATH`). Only a keyed hash of the visitor's IP is stored, not the address.
- Read them with `flask --app wsgi list-enquiries [--limit N]`.
- Set `MAIL_SERVER` and `MAIL_RECIPIENT` (plus `MAIL_USERNAME`/`MAIL_PASSWORD`) to also get an e-mail per enquiry. It is sent in the background; if SMTP fails the enquiry is still saved and the failure is logged.

## Deploying

```bash
export APP_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export TRUST_PROXY=true            # when behind nginx / a load balancer / a PaaS router
gunicorn wsgi:app --workers 2 --bind 0.0.0.0:8000
```

- Production refuses to start without a real `SECRET_KEY`.
- Terminate HTTPS at your reverse proxy and pass `X-Forwarded-For` / `X-Forwarded-Proto`; with `TRUST_PROXY=true` the app then uses secure cookies and sends HSTS.
- `/healthz` is available for uptime checks.
- Keep `instance/` on persistent storage (or point `DATABASE_PATH` at a persistent volume), otherwise enquiries are lost on redeploy.

## Deploying to Vercel

Vercel detects the Flask preset and uses `wsgi.py` (it looks for an `app` object in `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py` or `asgi.py`). Leave Root Directory as `./`.

**1. Add environment variables first** (Project → Settings → Environment Variables), then redeploy:

| Variable | Needed? | Value |
| --- | --- | --- |
| `SECRET_KEY` | **Required** | A long random string: `python -c "import secrets; print(secrets.token_hex(32))"`. Without it the app refuses to start and Vercel shows *"This page is unavailable"*. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_RECIPIENT` (+ `MAIL_SENDER`) | **Required for the contact form** | Your SMTP details. For Gmail: `smtp.gmail.com`, `587`, your address, and an [App Password](https://myaccount.google.com/apppasswords) (not your normal password), and the address that should receive enquiries. |
| `WHATSAPP_NUMBER`, `CONTACT_EMAIL`, `SITE_URL`, `SOCIAL_*` | Recommended | See "Before you go live". |

You do **not** need `APP_ENV` (defaults to production) or `TRUST_PROXY`/`MAIL_BLOCKING` (switched on automatically when Vercel's `VERCEL` variable is present).

**2. What is different on Vercel**

- **Static files** are served by Vercel's CDN from `public/` (this is why they live in `public/static/`). Flask serves the same folder everywhere else, so URLs are identical.
- **Storage is temporary.** The app folder is read-only and only `/tmp` is writable, and each serverless instance has its own copy, so a SQLite file cannot hold enquiries (see [Vercel's note on SQLite](https://vercel.com/guides/is-sqlite-supported-in-vercel)). The e-mail alert therefore *is* the delivery: it is sent before the visitor gets a reply, and if e-mail is not configured or fails, the form says so instead of claiming success. `flask list-enquiries` is not useful on Vercel.
- **Rate limiting is per instance**, so it only slows casual abuse. For a strict limit use a shared store.
- Want a permanent record of enquiries too? Use a hosted database (e.g. Postgres from the Vercel Marketplace); that is not included here.

**3. If it still fails:** Vercel → your project → Deployments → the latest one → **Logs**. The last lines of the Python traceback name the exact problem.

## Notes and limits

- **Rate limiting is per process.** With several Gunicorn workers each keeps its own counter, so the effective limit is `limit × workers`. For a strict global limit use a shared store (e.g. Flask-Limiter with Redis).
- **CDN scripts.** GSAP, ScrollTrigger (cdnjs) and Lenis (jsDelivr) load from their CDNs exactly as in the original, and the Content-Security-Policy allows only those hosts for scripts. For tighter control, download them into `public/static/js/vendor/`, change the `<script>` tags in `templates/index.html`, and drop the CDN hosts from `CSP` in `security.py`.
- **CSP and styles.** `style-src` keeps `'unsafe-inline'` because GSAP applies inline styles at runtime; there is no inline JavaScript.
- Static files are fingerprinted with their modification time (`?v=…`), so edits to the CSS/JS are picked up immediately even with long cache lifetimes.
