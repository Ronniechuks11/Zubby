"""Optional e-mail notification when a new enquiry arrives.

Enabled only when MAIL_SERVER and MAIL_RECIPIENT are configured.  Sending runs
in a background thread so a slow SMTP server never delays the visitor, and any
failure is logged rather than shown to them — the enquiry is already saved.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

from flask import Flask, current_app

from . import db
from .forms import ContactSubmission

log = logging.getLogger(__name__)


def mail_enabled(app: Flask) -> bool:
    return bool(app.config.get("MAIL_SERVER") and app.config.get("MAIL_RECIPIENT"))


def build_message(app: Flask, enquiry_id: int, sub: ContactSubmission) -> EmailMessage:
    cfg = app.config
    msg = EmailMessage()
    # Header values come from user input; _clean() already stripped newlines and
    # EmailMessage refuses any header that still contains one.
    ref = f" #{enquiry_id}" if enquiry_id else ""  # no id when storage is unavailable
    msg["Subject"] = f"New enquiry{ref} from {sub.name[:60]}"
    msg["From"] = cfg["MAIL_SENDER"] or cfg["MAIL_RECIPIENT"]
    msg["To"] = cfg["MAIL_RECIPIENT"]
    if sub.contact_is_email:
        msg["Reply-To"] = sub.contact
    msg.set_content(
        "A new enquiry came in through the Valora Digital website.\n\n"
        f"Name:    {sub.name}\n"
        f"Contact: {sub.contact}\n"
        f"Budget:  {sub.budget}\n\n"
        f"Message:\n{sub.message}\n"
    )
    return msg


def _deliver(app: Flask, msg: EmailMessage) -> None:
    cfg = app.config
    timeout = cfg["MAIL_TIMEOUT"]
    if cfg["MAIL_USE_SSL"]:
        server = smtplib.SMTP_SSL(
            cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=timeout)
    with server:
        if cfg["MAIL_USE_TLS"] and not cfg["MAIL_USE_SSL"]:
            server.starttls(context=ssl.create_default_context())
        if cfg["MAIL_USERNAME"]:
            server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        server.send_message(msg)


def _worker(app: Flask, enquiry_id: int, msg: EmailMessage) -> bool:
    """Send the e-mail; True if it was delivered to the SMTP server."""
    with app.app_context():
        try:
            _deliver(app, msg)
        except Exception:  # noqa: BLE001 - never let a mail problem crash a worker
            log.exception("Could not send notification for enquiry #%s", enquiry_id)
            return False
        log.info("Enquiry #%s notification sent", enquiry_id)
        # Bookkeeping must never turn a delivered e-mail into a reported failure.
        try:
            db.mark_notified(enquiry_id)
        except Exception:  # noqa: BLE001
            log.warning("Could not mark enquiry #%s as notified", enquiry_id, exc_info=True)
        return True


def notify_new_enquiry(enquiry_id: int, sub: ContactSubmission, *, blocking: bool = False) -> bool:
    """Send the alert e-mail, in the background unless ``blocking`` is True.

    Returns True if the e-mail was sent (blocking) or handed to a background thread,
    and False if e-mail is not configured or could not be sent.
    """
    app = current_app._get_current_object()  # noqa: SLF001 - needed to hand over to a thread
    if not mail_enabled(app):
        return False
    try:
        msg = build_message(app, enquiry_id, sub)
    except ValueError:
        log.exception("Could not build notification for enquiry #%s", enquiry_id)
        return False
    if blocking:
        return _worker(app, enquiry_id, msg)
    threading.Thread(target=_worker, args=(app, enquiry_id, msg), daemon=True).start()
    return True
