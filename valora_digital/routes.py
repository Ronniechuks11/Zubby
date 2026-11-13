"""URL routes: the landing page, the contact endpoint and a few site basics."""
from __future__ import annotations

import logging
import sqlite3

from flask import (
    Blueprint, Response, current_app, jsonify, redirect, render_template,
    request, session, url_for,
)

from . import db, mailer
from .forms import validate_contact
from .security import csrf_is_valid, hash_ip

log = logging.getLogger(__name__)
bp = Blueprint("main", __name__)

SESSION_STATE_KEY = "contact_state"
SUCCESS_MESSAGE = "Thanks — your message has been received. We'll be in touch soon."
STORAGE_ERROR_MESSAGE = (
    "Sorry, we couldn't save your message just now. Please try again shortly or message us on WhatsApp."
)
UNAVAILABLE_MESSAGE = (
    "Our contact form isn't available right now. Please reach us on WhatsApp or by email instead."
)
SEND_FAILED_MESSAGE = (
    "We couldn't send your message just now. Please try again shortly or message us on WhatsApp."
)
SESSION_EXPIRED_MESSAGE = "Your session expired. Please try sending your message again."
RATE_LIMIT_MESSAGE = "You've sent several messages recently. Please try again a little later."


def wants_json() -> bool:
    """True for the fetch() call made by the page's JavaScript."""
    return (
        request.headers.get("X-Requested-With") == "fetch"
        or request.accept_mimetypes.best == "application/json"
    )


def _contact_redirect() -> Response:
    return redirect(url_for("main.index") + "#contact", code=303)


def _respond(ok: bool, message: str, *, status: int, errors: dict | None = None,
             values: dict | None = None, headers: dict | None = None) -> Response:
    """Answer the contact form: JSON for the JS client, redirect (PRG) otherwise."""
    if wants_json():
        body = {"ok": ok, "message": message}
        if errors:
            body["errors"] = errors
        response = jsonify(body)
        response.status_code = status
    else:
        session[SESSION_STATE_KEY] = {
            "status": "success" if ok else "error",
            "message": message,
            "errors": errors or {},
            "values": values or {},
        }
        response = _contact_redirect()
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@bp.get("/")
def index():
    state = session.pop(SESSION_STATE_KEY, None) or {}
    return render_template(
        "index.html",
        form_status=state.get("status"),
        form_message=state.get("message", ""),
        form_errors=state.get("errors", {}),
        form_values=state.get("values", {}),
    )


@bp.post("/contact")
def contact():
    if not csrf_is_valid():
        return _respond(False, SESSION_EXPIRED_MESSAGE, status=400)

    sub = validate_contact(request.form)

    # Honeypot: real visitors never see this field.  Answer "success" so bots
    # learn nothing, but store and send nothing.
    if sub.is_bot:
        log.info("Honeypot triggered; submission discarded")
        return _respond(True, SUCCESS_MESSAGE, status=200)

    if not sub.is_valid:
        return _respond(
            False, "Please check the highlighted fields.", status=422,
            errors=sub.errors, values=sub.values(),
        )

    # On hosts whose storage is temporary (e.g. Vercel) the e-mail IS the delivery.
    # Without it a message would be accepted and then lost, so say so honestly instead.
    ephemeral = current_app.config["EPHEMERAL_STORAGE"]
    if ephemeral and not mailer.mail_enabled(current_app):
        log.error(
            "Contact form refused: this host has temporary storage and no e-mail is "
            "configured. Set MAIL_SERVER and MAIL_RECIPIENT (see README)."
        )
        return _respond(False, UNAVAILABLE_MESSAGE, status=503, values=sub.values())

    limiter = current_app.extensions["contact_limiter"]
    key = hash_ip(request, current_app.config["SECRET_KEY"])
    if not limiter.allow(key):
        return _respond(
            False, RATE_LIMIT_MESSAGE, status=429, values=sub.values(),
            headers={"Retry-After": str(limiter.retry_after(key))},
        )

    enquiry_id = 0
    try:
        db.init_db()  # cheap (CREATE IF NOT EXISTS); recovers if storage was unavailable at start-up
        enquiry_id = db.save_enquiry(
            name=sub.name, contact=sub.contact, budget=sub.budget, message=sub.message,
            ip_hash=key, user_agent=request.headers.get("User-Agent", ""),
        )
        log.info("Enquiry #%s saved", enquiry_id)
    except (sqlite3.Error, OSError):
        log.exception("Could not store enquiry")
        if not ephemeral:
            return _respond(False, STORAGE_ERROR_MESSAGE, status=503, values=sub.values())
        # Temporary storage is only a convenience here; the e-mail below still delivers it.

    sent = mailer.notify_new_enquiry(enquiry_id, sub, blocking=current_app.config["MAIL_BLOCKING"])
    if ephemeral and not sent:
        return _respond(False, SEND_FAILED_MESSAGE, status=503, values=sub.values())
    return _respond(True, SUCCESS_MESSAGE, status=200)


# --------------------------------------------------------------------------
# Site basics
# --------------------------------------------------------------------------
@bp.get("/healthz")
def healthz():
    """Liveness probe for hosting platforms and uptime monitors."""
    return jsonify(status="ok")


@bp.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="img/favicon.svg"), code=302)


@bp.get("/robots.txt")
def robots():
    base = current_app.config["SITE_URL"] or request.url_root.rstrip("/")
    body = f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    base = current_app.config["SITE_URL"] or request.url_root.rstrip("/")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{base}/</loc></url>\n"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")


# --------------------------------------------------------------------------
# Template helpers
# --------------------------------------------------------------------------
def social_url(key: str) -> str:
    if key == "whatsapp":
        number = "".join(ch for ch in current_app.config["WHATSAPP_NUMBER"] if ch.isdigit())
        return f"https://wa.me/{number}"
    return current_app.config["SOCIAL_URLS"].get(key) or "#"
