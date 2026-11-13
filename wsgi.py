"""WSGI entry point.

    Development:  flask --app wsgi run --debug
    Production:   gunicorn wsgi:app --workers 2 --bind 0.0.0.0:8000
"""
from valora_digital import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
