import pytest

from valora_digital import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app("testing", {"DATABASE": str(tmp_path / "test.sqlite3")})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf(client):
    """Load the page (which starts the session) and return the CSRF token."""
    client.get("/")
    with client.session_transaction() as sess:
        return sess["_csrf_token"]


VALID_FORM = {
    "name": "Ada Okafor",
    "contact": "ada@example.com",
    "budget": "₦300,000 – ₦750,000",
    "message": "We are launching a new product and need Meta ads.",
    "website": "",
}


@pytest.fixture()
def valid_form():
    return dict(VALID_FORM)


@pytest.fixture()
def post_json(client, csrf):
    """POST to /contact the way the page's JavaScript does."""

    def _post(data, *, token=csrf):
        headers = {"Accept": "application/json", "X-Requested-With": "fetch"}
        if token is not None:
            headers["X-CSRFToken"] = token
        return client.post("/contact", data=data, headers=headers)

    return _post


def count_enquiries(app):
    import sqlite3

    conn = sqlite3.connect(app.config["DATABASE"])
    try:
        return conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
    finally:
        conn.close()
