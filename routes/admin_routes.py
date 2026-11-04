import hmac
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, session

from services.errors import AppError
from services.extraction_service import ExtractionError, extract_text

from .auth import is_admin, require_admin

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

MAX_FAILED_LOGINS = 5      # wrong attempts allowed ...
LOCK_SECONDS = 300         # ... within this many seconds, per computer
_failed = {}               # ip address -> times of wrong attempts


def _recent_failures(ip):
    now = time.time()
    _failed[ip] = [t for t in _failed.get(ip, []) if now - t < LOCK_SECONDS]
    return _failed[ip]


def _docs():
    return current_app.extensions["services"].documents


# ---------- login ----------
@bp.post("/login")
def login():
    cfg = current_app.extensions["cfg"]
    if not cfg.ADMIN_PASSWORD:
        raise AppError(503, "admin_disabled", "The admin panel is disabled. Set ADMIN_PASSWORD in the .env file.")
    ip = request.remote_addr or "unknown"
    if len(_recent_failures(ip)) >= MAX_FAILED_LOGINS:
        raise AppError(429, "too_many_attempts", "Too many wrong attempts. Please wait 5 minutes and try again.")

    data = request.get_json(silent=True) or {}
    user_ok = hmac.compare_digest(str(data.get("username", "")).encode(), cfg.ADMIN_USERNAME.encode())
    pass_ok = hmac.compare_digest(str(data.get("password", "")).encode(), cfg.ADMIN_PASSWORD.encode())
    if not (user_ok and pass_ok):
        _failed.setdefault(ip, []).append(time.time())
        raise AppError(401, "invalid_credentials", "Wrong username or password.")

    _failed.pop(ip, None)
    session.clear()
    session["admin"] = True
    return jsonify({"success": True})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@bp.get("/me")
def me():
    return jsonify({"success": True, "logged_in": is_admin()})


# ---------- document management (the same operations as the Postman requests) ----------
@bp.get("/documents")
@require_admin
def list_documents():
    docs = [_docs().public(d) for d in _docs().list()]
    return jsonify({"success": True, "count": len(docs), "documents": docs})


@bp.post("/documents")
@require_admin
def upload_document():
    """Upload a file and index it in one step. If indexing fails, the file stays listed so it can be retried."""
    doc = _docs().upload(request.files.get("file"))
    doc = _docs().process(doc["document_id"])
    return jsonify({"success": True, "document": _docs().public(doc)}), 201


@bp.post("/documents/<document_id>/process")
@require_admin
def process_document(document_id):
    doc = _docs().process(document_id)
    return jsonify({"success": True, "document": _docs().public(doc)})


@bp.post("/documents/<document_id>/reindex")
@require_admin
def reindex_document(document_id):
    """Re-read the saved file, or replace it first when a new file is sent."""
    doc = _docs().reindex(document_id, request.files.get("file"))
    return jsonify({"success": True, "document": _docs().public(doc)})


@bp.delete("/documents/<document_id>")
@require_admin
def delete_document(document_id):
    _docs().delete(document_id)
    return jsonify({"success": True, "document_id": document_id})

    

# ---------- view and download a document ----------
MAX_VIEW_CHARS = 200_000   # the viewer shows at most this much text


def _saved_file(document_id):
    """Return the document record and the path of its saved file."""
    doc = _docs().get(document_id)
    cfg = current_app.extensions["cfg"]
    path = Path(cfg.DOCUMENT_STORAGE_PATH) / f"{doc['document_id']}{doc['extension']}"
    if not path.exists():
        raise AppError(404, "file_missing", "The saved file could not be found.")
    return doc, path


@bp.get("/documents/<document_id>/content")
@require_admin
def document_content(document_id):
    """The text the AI reads from this document, page by page."""
    doc, path = _saved_file(document_id)
    try:
        pages = extract_text(path, doc["extension"])
    except ExtractionError as e:
        raise AppError(422, "extraction_failed", str(e))
    out, used = [], 0
    for number, text in pages:
        room = MAX_VIEW_CHARS - used
        if room <= 0:
            break
        out.append({"page": number, "text": text[:room]})
        used += len(text[:room])
    truncated = used < sum(len(text) for _, text in pages)
    return jsonify({"success": True, "filename": doc["filename"], "pages": out, "truncated": truncated})


@bp.get("/documents/<document_id>/download")
@require_admin
def download_document(document_id):
    doc, path = _saved_file(document_id)
    return send_file(path, as_attachment=True, download_name=doc["filename"])