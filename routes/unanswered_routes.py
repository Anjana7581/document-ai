from flask import Blueprint, current_app, jsonify, request

from services.errors import AppError

from .auth import require_admin

bp = Blueprint("unanswered", __name__, url_prefix="/api/admin/unanswered")


def _svc():
    return current_app.extensions["services"].unanswered


@bp.get("")
@require_admin
def list_questions():
    items = _svc().list(request.args.get("status", "all"))
    return jsonify({"success": True, "count": len(items), "questions": items})


@bp.put("/<question_id>/answer")
@require_admin
def save_answer(question_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise AppError(400, "invalid_request", 'Send JSON like {"answer": "..."}.')
    result = _svc().save_answer(question_id, data["answer"])
    return jsonify({"success": True, "emails": result})


@bp.delete("/<question_id>")
@require_admin
def delete_question(question_id):
    _svc().delete(question_id)
    return jsonify({"success": True, "question_id": question_id})