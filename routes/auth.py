import hmac
from functools import wraps

from flask import current_app, request, session

from services.errors import AppError


def is_admin():
    """True when the person has logged in to the admin panel."""
    return bool(session.get("admin"))


def require_admin(fn):
    """Only a logged-in admin may call this endpoint."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            raise AppError(401, "unauthorized", "Please log in as admin.")
        return fn(*args, **kwargs)

    return wrapper


def require_api_key(fn):
    """If API_KEY is set, require it in the X-API-Key header."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.extensions["cfg"].API_KEY
        if expected:
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                raise AppError(401, "unauthorized", "Missing or invalid API key.")
        return fn(*args, **kwargs)

    return wrapper