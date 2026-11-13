"""Application configuration.

Every setting that differs between machines (secrets, contact details, SMTP,
social links) is read from environment variables, optionally loaded from a
``.env`` file by ``create_app``.  Nothing secret lives in the code.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 at build and run time. Its functions run on a read-only
# filesystem (only /tmp is writable, and it is not shared or permanent) and may
# freeze background threads once the response is sent, so a few defaults change.
ON_VERCEL = bool(os.environ.get("VERCEL"))

# Load .env (if present) *before* the classes below read the environment.
# Real environment variables always win over values in the file.
load_dotenv(BASE_DIR / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    """Read a string setting; a blank value (e.g. ``KEY=`` in .env) counts as unset."""
    value = os.environ.get(name, "").strip()
    return value or default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


class Config:
    """Settings shared by every environment."""

    # -- Core ---------------------------------------------------------------
    SECRET_KEY = _env("SECRET_KEY")
    SITE_URL = _env("SITE_URL").rstrip("/")  # e.g. https://valoradigital.com
    TRUST_PROXY = _env_bool("TRUST_PROXY", ON_VERCEL)  # True when behind nginx / a PaaS router
    MAX_CONTENT_LENGTH = 32 * 1024  # contact form payloads are tiny

    # -- Sessions / cookies -------------------------------------------------
    SESSION_COOKIE_NAME = "valora_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # seconds

    # -- Storage ------------------------------------------------------------
    # On Vercel the app directory is read-only, so fall back to /tmp. That copy is
    # temporary: rely on the e-mail notification (MAIL_*) to receive enquiries there.
    DATABASE = _env("DATABASE_PATH") or (
        "/tmp/valora.sqlite3" if ON_VERCEL else str(BASE_DIR / "instance" / "valora.sqlite3")
    )
    # True when stored data does not survive (serverless hosts). The contact form then
    # treats the e-mail alert as the real delivery and refuses to say "received" if
    # it cannot be sent, instead of silently losing the enquiry.
    EPHEMERAL_STORAGE = _env_bool("EPHEMERAL_STORAGE", ON_VERCEL)

    # -- Contact details shown on the page ----------------------------------
    # The shipped defaults are the placeholders from the original design.
    CONTACT_EMAIL = _env("CONTACT_EMAIL", "hello@valoradigital.example")
    WHATSAPP_NUMBER = _env("WHATSAPP_NUMBER", "000000000000")  # digits only, intl. format

    SOCIAL_URLS = {
        "instagram": _env("SOCIAL_INSTAGRAM"),
        "facebook": _env("SOCIAL_FACEBOOK"),
        "tiktok": _env("SOCIAL_TIKTOK"),
        "linkedin": _env("SOCIAL_LINKEDIN"),
        "x": _env("SOCIAL_X"),
    }

    # -- Contact form protection -------------------------------------------
    CONTACT_RATE_LIMIT = _env_int("CONTACT_RATE_LIMIT", 5)  # submissions ...
    CONTACT_RATE_WINDOW = _env_int("CONTACT_RATE_WINDOW", 3600)  # ... per this many seconds

    # -- Optional e-mail notification of new enquiries ----------------------
    MAIL_SERVER = _env("MAIL_SERVER")
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)  # STARTTLS
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)  # implicit TLS (usually port 465)
    MAIL_USERNAME = _env("MAIL_USERNAME")
    MAIL_PASSWORD = _env("MAIL_PASSWORD")
    MAIL_SENDER = _env("MAIL_SENDER") or _env("MAIL_USERNAME")
    MAIL_RECIPIENT = _env("MAIL_RECIPIENT")  # who receives new-enquiry alerts
    MAIL_TIMEOUT = _env_int("MAIL_TIMEOUT", 8 if ON_VERCEL else 15)  # seconds
    # Send the alert before answering the visitor instead of in a background thread.
    # Needed on serverless hosts, where a thread can be frozen once the response is sent.
    MAIL_BLOCKING = _env_bool("MAIL_BLOCKING", ON_VERCEL)

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self) -> None:
        # An ephemeral key is fine locally; sessions simply reset on restart.
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    # Asset URLs carry a ?v=<mtime> fingerprint, so browsers may cache them for a year.
    SEND_FILE_MAX_AGE_DEFAULT = 31536000

    def __init__(self) -> None:
        if not self.SECRET_KEY or self.SECRET_KEY.lower().startswith(("change", "dev")):
            raise RuntimeError(
                "SECRET_KEY must be set to a long random value in production. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))" '
                "and add it as an environment variable (on Vercel: Project > Settings > "
                "Environment Variables), then redeploy."
            )


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "testing-secret-key"
    # Hermetic: tests must behave the same whatever host or environment runs them.
    TRUST_PROXY = False
    EPHEMERAL_STORAGE = False
    MAIL_BLOCKING = False
    CONTACT_RATE_LIMIT = 3
    CONTACT_RATE_WINDOW = 60
    MAIL_SERVER = ""
    MAIL_RECIPIENT = ""


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
