"""Valora Digital website — Flask application factory."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from . import content, db, mailer, security
from .config import BASE_DIR, CONFIGS
from .routes import bp as main_bp
from .routes import social_url, wants_json
from .security import SlidingWindowLimiter, get_csrf_token


def create_app(config_name: str | None = None, test_config: dict | None = None) -> Flask:
    # Static files live in public/static: Vercel serves public/** from its CDN
    # (it ignores Flask's own static folder), and Flask serves the same folder
    # locally and on any normal server, so the URLs are identical everywhere.
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "public" / "static"),
        static_url_path="/static",
    )

    env = (config_name or os.environ.get("APP_ENV") or "production").lower()
    if env not in CONFIGS:
        raise ValueError(f"Unknown APP_ENV {env!r}; choose one of: {', '.join(CONFIGS)}")
    app.config.from_object(CONFIGS[env]())
    if test_config:
        app.config.update(test_config)
    app.config["APP_ENV"] = env

    if not app.testing:
        logging.basicConfig(
            level=logging.DEBUG if app.debug else logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    if app.config["TRUST_PROXY"]:
        # Trust exactly one proxy hop for client IP, scheme and host.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.extensions["contact_limiter"] = SlidingWindowLimiter(
        app.config["CONTACT_RATE_LIMIT"], app.config["CONTACT_RATE_WINDOW"]
    )

    db.init_app(app)
    security.init_app(app)
    app.register_blueprint(main_bp)
    _register_error_handlers(app)
    _register_template_helpers(app)

    # A storage problem (e.g. unwritable disk) must not take the whole site down:
    # the page still renders and the contact form reports the problem instead.
    with app.app_context():
        try:
            db.init_db()
        except (sqlite3.Error, OSError):
            app.logger.exception("Could not initialise the database at %s", app.config["DATABASE"])

    if app.config["EPHEMERAL_STORAGE"] and not app.testing and not mailer.mail_enabled(app):
        app.logger.warning(
            "Temporary-storage host without MAIL_SERVER/MAIL_RECIPIENT: the site will load, "
            "but the contact form will refuse submissions until e-mail is configured."
        )

    return app


def _register_template_helpers(app: Flask) -> None:
    static_root = Path(app.static_folder or "")

    def static_url(filename: str) -> str:
        """URL for a static file, fingerprinted with its mtime so edits bust caches."""
        try:
            version = int((static_root / filename).stat().st_mtime)
        except OSError:
            version = None
        return url_for("static", filename=filename, v=version)

    @app.context_processor
    def inject_globals() -> dict:
        cfg = app.config
        return {
            "site": content.SITE,
            "logo_path": content.LOGO_PATH,
            "nav_links": content.NAV_LINKS,
            "footer_links": content.FOOTER_LINKS,
            "marquee": content.MARQUEE,
            "services": content.SERVICES,
            "ads_checklist": content.ADS_CHECKLIST,
            "feed_posts": content.FEED_POSTS,
            "metric_chips": content.METRIC_CHIPS,
            "funnel": content.FUNNEL,
            "process_steps": content.PROCESS,
            "work_items": content.WORK,
            "stats": content.STATS,
            "budget_options": content.BUDGET_OPTIONS,
            "socials": content.SOCIALS,
            "contact_email": cfg["CONTACT_EMAIL"],
            "canonical_url": cfg["SITE_URL"],
            "current_year": datetime.now(timezone.utc).year,
            "csrf_token": get_csrf_token,
            "static_url": static_url,
            "social_url": social_url,
        }


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        if request.path == "/contact" and wants_json():
            return jsonify(ok=False, message=err.description or err.name), err.code
        return (
            render_template(
                "errors/error.html", code=err.code, title=err.name, description=err.description
            ),
            err.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        if app.debug:
            raise err  # let the interactive debugger show the traceback in development
        app.logger.exception("Unhandled error: %s", err)
        if request.path == "/contact" and wants_json():
            return jsonify(ok=False, message="Something went wrong on our side. Please try again."), 500
        return (
            render_template(
                "errors/error.html",
                code=500,
                title="Something went wrong",
                description="An unexpected error occurred. Please try again in a moment.",
            ),
            500,
        )
