"""
WSGI entrypoint for cPanel's "Setup Python App" (and DirectAdmin's
equivalent) — both use Phusion Passenger, which looks for this exact
filename and an `application` object in it. Nothing else reads this
file; `app.py` is the real application, this is just the adapter cPanel
expects.

If you ever deploy behind a different WSGI server (gunicorn, uWSGI on a
real VPS), point it at `app:app` directly instead — this file is not
needed there.
"""
from app import app as application  # noqa: F401
