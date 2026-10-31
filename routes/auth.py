import hmac
from functools import wraps

from flask import current_app, request

from services.errors import AppError


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
