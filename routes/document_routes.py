from flask import Blueprint, current_app, jsonify, request

from .auth import require_api_key

bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _svc():
    return current_app.extensions["services"].documents


def _body(doc, status=200, **extra):
    payload = {"success": True, "document_id": doc["document_id"], "status": doc["status"],
               "document": _svc().public(doc)}
    payload.update(extra)
    return jsonify(payload), status


@bp.post("/upload")
@require_api_key
def upload():
    doc = _svc().upload(request.files.get("file"))
    return _body(doc, 201, message="Uploaded. Call POST /api/documents/{id}/process next.")


@bp.post("/<document_id>/process")
@require_api_key
def process(document_id):
    doc = _svc().process(document_id)
    return _body(doc, message="Document indexed.", chunks_indexed=doc["chunk_count"])


@bp.post("/<document_id>/reindex")
@require_api_key
def reindex(document_id):
    doc = _svc().reindex(document_id, request.files.get("file"))
    return _body(doc, message="Document re-indexed.", chunks_indexed=doc["chunk_count"])


@bp.get("/<document_id>")
@require_api_key
def get_one(document_id):
    return _body(_svc().get(document_id))


@bp.get("")
@require_api_key
def list_all():
    docs = [_svc().public(d) for d in _svc().list()]
    return jsonify({"success": True, "count": len(docs), "documents": docs})


@bp.delete("/<document_id>")
@require_api_key
def delete(document_id):
    _svc().delete(document_id)
    return jsonify({"success": True, "message": "Document and its vector records were deleted.",
                    "document_id": document_id})
