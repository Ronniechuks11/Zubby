import os
import pathlib
import re
import sqlite3
import subprocess
import sys

import pytest

from valora_digital import create_app, mailer
from valora_digital.forms import validate_contact

from conftest import count_enquiries


# --------------------------------------------------------------------------
# Pages & static files
# --------------------------------------------------------------------------
def test_index_renders_every_section(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    for section_id in ("home", "manifesto", "services", "meta-ads", "process", "work", "contact"):
        assert f'id="{section_id}"' in html
    assert "We make brands" in html
    assert html.count('class="service-card"') == 6
    assert html.count('class="process-card"') == 4
    assert html.count('class="work-card"') == 3
    assert html.count('class="echo"') == 5
    assert html.count('class="marquee-item"') == 12  # 6 items rendered twice for the loop
    assert html.count('class="feed-post"') == 4  # 3 posts + first repeated


def test_every_anchor_link_has_a_target(client):
    html = client.get("/").get_data(as_text=True)
    targets = set(re.findall(r'href="/#([a-z-]+)"', html))
    assert {"services", "meta-ads", "process", "work", "contact", "home"} <= targets
    for target in targets:
        assert f'id="{target}"' in html, f"missing #{target}"


def test_static_assets_are_served_and_fingerprinted(client):
    html = client.get("/").get_data(as_text=True)
    css = re.search(r'href="(/static/css/main\.css\?v=\d+)"', html)
    js = re.search(r'src="(/static/js/main\.js\?v=\d+)"', html)
    assert css and js
    assert client.get(css.group(1)).status_code == 200
    assert client.get(js.group(1)).status_code == 200
    assert client.get("/static/img/favicon.svg").status_code == 200


def test_security_headers(client):
    res = client.get("/")
    assert "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net" in res.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in res.headers["Content-Security-Policy"].split("script-src")[1].split(";")[0]
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Cache-Control"] == "private, no-cache"


def test_utility_routes(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}
    robots = client.get("/robots.txt")
    assert robots.mimetype == "text/plain" and "Sitemap:" in robots.get_data(as_text=True)
    sitemap = client.get("/sitemap.xml")
    assert sitemap.mimetype == "application/xml" and "<loc>" in sitemap.get_data(as_text=True)
    assert client.get("/favicon.ico").status_code == 302


def test_404_page_is_branded(client):
    res = client.get("/does-not-exist")
    assert res.status_code == 404
    assert "Error 404" in res.get_data(as_text=True)


def test_contact_endpoint_rejects_get(client):
    assert client.get("/contact").status_code == 405


def test_site_url_and_contact_settings_flow_into_page(tmp_path):
    app = create_app("testing", {
        "DATABASE": str(tmp_path / "t.sqlite3"),
        "SITE_URL": "https://valora.test",
        "WHATSAPP_NUMBER": "+234 801 234 5678",
        "CONTACT_EMAIL": "team@valora.test",
        "SOCIAL_URLS": {"instagram": "https://instagram.com/valora", "facebook": "", "tiktok": "",
                        "linkedin": "", "x": ""},
    })
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'rel="canonical" href="https://valora.test/"' in html
    assert "https://wa.me/2348012345678" in html
    assert "mailto:team@valora.test" in html
    assert 'href="https://instagram.com/valora"' in html


# --------------------------------------------------------------------------
# Contact form
# --------------------------------------------------------------------------
def test_valid_submission_is_saved(app, post_json, valid_form):
    res = post_json(valid_form)
    assert res.status_code == 200
    assert res.get_json()["ok"] is True
    conn = sqlite3.connect(app.config["DATABASE"])
    row = conn.execute("SELECT name, contact, budget, message, ip_hash FROM enquiries").fetchone()
    conn.close()
    assert row[:4] == (valid_form["name"], valid_form["contact"], valid_form["budget"], valid_form["message"])
    assert row[4] and "127.0.0.1" not in row[4]  # only a keyed hash is stored, never the raw IP


def test_missing_csrf_token_is_rejected(app, post_json, valid_form):
    assert post_json(valid_form, token=None).status_code == 400
    assert post_json(valid_form, token="wrong").status_code == 400
    assert count_enquiries(app) == 0


def test_csrf_token_in_form_field_is_accepted(app, client, csrf, valid_form):
    res = client.post("/contact", data={**valid_form, "csrf_token": csrf})
    assert res.status_code == 303
    assert count_enquiries(app) == 1


@pytest.mark.parametrize("field,value,error_key", [
    ("name", "", "name"),
    ("name", "A", "name"),
    ("contact", "not-an-email", "contact"),
    ("contact", "", "contact"),
    ("budget", "Free please", "budget"),
    ("budget", "", "budget"),
    ("message", "short", "message"),
    ("message", "x" * 2001, "message"),
])
def test_invalid_fields_return_422(app, post_json, valid_form, field, value, error_key):
    valid_form[field] = value
    res = post_json(valid_form)
    assert res.status_code == 422
    body = res.get_json()
    assert body["ok"] is False and error_key in body["errors"]
    assert count_enquiries(app) == 0


@pytest.mark.parametrize("contact", ["ada@example.com", "+234 801 234 5678", "08012345678"])
def test_email_and_phone_contacts_are_accepted(post_json, valid_form, contact):
    valid_form["contact"] = contact
    assert post_json(valid_form).status_code == 200


def test_honeypot_submissions_are_silently_discarded(app, post_json, valid_form):
    valid_form["website"] = "http://spam.example"
    res = post_json(valid_form)
    assert res.status_code == 200 and res.get_json()["ok"] is True  # bots learn nothing
    assert count_enquiries(app) == 0


def test_rate_limit_applies_after_valid_submissions(app, post_json, valid_form):
    for _ in range(app.config["CONTACT_RATE_LIMIT"]):
        assert post_json(valid_form).status_code == 200
    res = post_json(valid_form)
    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0
    assert count_enquiries(app) == app.config["CONTACT_RATE_LIMIT"]


def test_validation_errors_do_not_burn_the_rate_limit(app, post_json, valid_form):
    bad = {**valid_form, "message": "short"}
    for _ in range(app.config["CONTACT_RATE_LIMIT"] + 2):
        assert post_json(bad).status_code == 422
    assert post_json(valid_form).status_code == 200


def test_form_without_javascript_redirects_and_shows_success(client, csrf, valid_form):
    res = client.post("/contact", data={**valid_form, "csrf_token": csrf})
    assert res.status_code == 303 and res.headers["Location"].endswith("/#contact")
    page = client.get("/").get_data(as_text=True)
    assert 'id="formSuccess" role="status">Thanks' in page.replace("\n", "")
    assert "form-success show" in page
    # shown once only
    assert "form-success show" not in client.get("/").get_data(as_text=True)


def test_form_without_javascript_repopulates_values_and_errors(client, csrf, valid_form):
    valid_form.update(contact="nope", name="Ada <b>Okafor</b>")
    client.post("/contact", data={**valid_form, "csrf_token": csrf})
    page = client.get("/").get_data(as_text=True)
    assert "Enter a valid email address or WhatsApp number." in page
    assert 'aria-invalid="true"' in page
    assert "Ada &lt;b&gt;Okafor&lt;/b&gt;" in page  # echoed back escaped, not as markup
    assert "<b>Okafor</b>" not in page


def test_input_is_sanitised():
    form = {"name": "Ada\r\nBcc: evil@example.com", "contact": "ada@example.com",
            "budget": "Let's discuss", "message": "Hello\x00 there, this is long enough."}
    sub = validate_contact(form)
    assert "\n" not in sub.name and "\r" not in sub.name
    assert "\x00" not in sub.message


# --------------------------------------------------------------------------
# Notification e-mail
# --------------------------------------------------------------------------
class FakeSMTP:
    sent = []
    started_tls = False
    logged_in = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        FakeSMTP.started_tls = True

    def login(self, user, password):
        FakeSMTP.logged_in = (user, password)

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture()
def mail_app(tmp_path, monkeypatch):
    FakeSMTP.sent, FakeSMTP.started_tls, FakeSMTP.logged_in = [], False, None
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    return create_app("testing", {
        "DATABASE": str(tmp_path / "mail.sqlite3"),
        "MAIL_SERVER": "smtp.test", "MAIL_PORT": 587, "MAIL_USE_TLS": True,
        "MAIL_USERNAME": "bot@valora.test", "MAIL_PASSWORD": "pw",
        "MAIL_SENDER": "bot@valora.test", "MAIL_RECIPIENT": "team@valora.test",
    })


def test_notification_email_is_sent_and_recorded(mail_app, valid_form):
    from valora_digital import db

    with mail_app.test_request_context():
        sub = validate_contact(valid_form)
        enquiry_id = db.save_enquiry(name=sub.name, contact=sub.contact, budget=sub.budget,
                                     message=sub.message, ip_hash="x", user_agent="pytest")
        mailer.notify_new_enquiry(enquiry_id, sub, blocking=True)
        notified = db.get_db().execute("SELECT notified FROM enquiries WHERE id=?", (enquiry_id,)).fetchone()[0]

    assert notified == 1
    assert FakeSMTP.started_tls and FakeSMTP.logged_in == ("bot@valora.test", "pw")
    (msg,) = FakeSMTP.sent
    assert msg["To"] == "team@valora.test"
    assert msg["Reply-To"] == "ada@example.com"
    assert valid_form["message"] in msg.get_content()


def test_mail_failure_never_breaks_the_enquiry(mail_app, valid_form, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("smtp down")

    monkeypatch.setattr(mailer.smtplib, "SMTP", boom)
    with mail_app.test_request_context():
        from valora_digital import db

        sub = validate_contact(valid_form)
        enquiry_id = db.save_enquiry(name=sub.name, contact=sub.contact, budget=sub.budget,
                                     message=sub.message, ip_hash="x", user_agent="pytest")
        mailer.notify_new_enquiry(enquiry_id, sub, blocking=True)  # must not raise
        assert db.get_db().execute("SELECT notified FROM enquiries").fetchone()[0] == 0


def test_no_email_when_smtp_not_configured(app, valid_form):
    with app.test_request_context():
        assert mailer.mail_enabled(app) is False


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def test_production_requires_a_real_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr("valora_digital.config.Config.SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_unknown_environment_is_rejected():
    with pytest.raises(ValueError):
        create_app("staging-ish")


def test_development_gets_an_ephemeral_secret(monkeypatch, tmp_path):
    monkeypatch.setattr("valora_digital.config.Config.SECRET_KEY", "")
    monkeypatch.setattr("valora_digital.config.Config.DATABASE", str(tmp_path / "dev.sqlite3"))
    app = create_app("development")
    assert len(app.config["SECRET_KEY"]) >= 32 and app.debug


# --------------------------------------------------------------------------
# Serverless hosts (Vercel): read-only disk, temporary storage, e-mail as delivery
# --------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
UNWRITABLE_DB = "/proc/nope/valora.sqlite3"  # any attempt to create it raises OSError


def _serverless_app(tmp_path, **extra):
    cfg = {"DATABASE": str(tmp_path / "s.sqlite3"), "EPHEMERAL_STORAGE": True, "MAIL_BLOCKING": True}
    cfg.update(extra)
    return create_app("testing", cfg)


def _post_valid(app, form):
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as sess:
        token = sess["_csrf_token"]
    return client.post(
        "/contact", data=form,
        headers={"Accept": "application/json", "X-Requested-With": "fetch", "X-CSRFToken": token},
    )


def _use_fake_smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.started_tls, FakeSMTP.logged_in = [], False, None
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)


MAIL = {"MAIL_SERVER": "smtp.test", "MAIL_RECIPIENT": "team@valora.test", "MAIL_SENDER": "bot@valora.test"}


def test_serverless_without_mail_refuses_instead_of_losing_the_enquiry(tmp_path, valid_form):
    app = _serverless_app(tmp_path)
    res = _post_valid(app, valid_form)
    assert res.status_code == 503
    body = res.get_json()
    assert body["ok"] is False and "isn't available" in body["message"]
    assert count_enquiries(app) == 0


def test_serverless_with_mail_sends_before_replying(tmp_path, valid_form, monkeypatch):
    _use_fake_smtp(monkeypatch)
    app = _serverless_app(tmp_path, **MAIL)
    res = _post_valid(app, valid_form)
    assert res.status_code == 200 and res.get_json()["ok"] is True
    assert len(FakeSMTP.sent) == 1  # already sent when the response came back (no thread)


def test_serverless_reports_mail_failure_instead_of_claiming_success(tmp_path, valid_form, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("smtp down")

    monkeypatch.setattr(mailer.smtplib, "SMTP", boom)
    app = _serverless_app(tmp_path, **MAIL)
    res = _post_valid(app, valid_form)
    assert res.status_code == 503
    assert res.get_json()["ok"] is False and "couldn't send" in res.get_json()["message"]


def test_serverless_still_delivers_when_the_disk_is_unwritable(tmp_path, valid_form, monkeypatch):
    _use_fake_smtp(monkeypatch)
    app = _serverless_app(tmp_path, DATABASE=UNWRITABLE_DB, **MAIL)  # must not crash at start-up
    assert app.test_client().get("/").status_code == 200
    res = _post_valid(app, valid_form)
    assert res.status_code == 200 and len(FakeSMTP.sent) == 1


def test_normal_host_reports_storage_failure_but_page_still_loads(valid_form):
    app = create_app("testing", {"DATABASE": UNWRITABLE_DB})
    assert app.test_client().get("/").status_code == 200
    res = _post_valid(app, valid_form)
    assert res.status_code == 503 and res.get_json()["ok"] is False


def _run_app_code(code, **env):
    """Run Python in a clean subprocess with exactly this environment (as a host would)."""
    full = {"PATH": os.environ.get("PATH", ""), "APP_ENV": "production", "DATABASE_PATH": "",
            "MAIL_SERVER": "", "MAIL_RECIPIENT": "", "TRUST_PROXY": "", "SECRET_KEY": "", **env}
    prelude = f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    return subprocess.run([sys.executable, "-I", "-c", prelude + code], cwd=str(ROOT),
                          env=full, capture_output=True, text=True, timeout=60)


def test_vercel_environment_gets_safe_defaults_and_page_loads():
    result = _run_app_code(
        "import wsgi\n"
        "c = wsgi.app.config\n"
        "r = wsgi.app.test_client().get('/', base_url='https://example.com')\n"
        "print(c['DATABASE'], c['TRUST_PROXY'], c['MAIL_BLOCKING'], c['EPHEMERAL_STORAGE'], "
        "c['SESSION_COOKIE_SECURE'], r.status_code)\n",
        VERCEL="1", SECRET_KEY="k" * 40,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["/tmp/valora.sqlite3", "True", "True", "True", "True", "200"]


def test_vercel_start_survives_an_unwritable_database_path():
    result = _run_app_code(
        "import wsgi\nprint(wsgi.app.test_client().get('/', base_url='https://example.com').status_code)",
        VERCEL="1", SECRET_KEY="k" * 40, DATABASE_PATH=UNWRITABLE_DB,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


@pytest.mark.skipif((ROOT / ".env").exists(), reason="a local .env could supply SECRET_KEY")
def test_missing_secret_key_fails_with_an_actionable_message():
    result = _run_app_code("import wsgi", VERCEL="1")
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr and "Environment Variables" in result.stderr
