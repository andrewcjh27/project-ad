"""WSGI entry point for hosting the web console (gunicorn wsgi:app)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp"))
from app import app   # noqa: E402  (webapp/app.py)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
