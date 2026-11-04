import logging
import re

from flask import Blueprint, current_app, jsonify, request

from services.errors import AppError
from services.llm_service import EMAIL_OFFER_MESSAGE, NOT_FOUND_MESSAGE

from .auth import require_api_key

bp = Blueprint("chat", __name__, url_prefix="/api")
log = logging.getLogger(__name__)
MAX_QUESTION_CHARS = 2000


def smalltalk(text):
    t = " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())
    words = len(t.split())
    if re.search(r"\b(how are you|how r u|how are u|whats up)\b", t):
        return ("I'm doing well, thank you for asking! 😊 How can I help you today? ")
    if re.search(r"\b(who are you|what are you|your name)\b", t):
        return ("I'm the CodertechPRO virtual assistant. 😊 I can help you with our courses enquiry, "
                "fees, batch timings, services and contact details.")
    if words <= 5 and re.search(r"\b(thanks|thank you|thankyou|thx)\b", t):
        return "You're most welcome! 😊 If you need anything else, just ask."
    if words <= 4 and re.search(r"\b(bye|goodbye|see you)\b", t):
        return "Thank you for chatting with us! Have a great day. 😊"
    if re.fullmatch(r"(hi+|hello+|hey+|hai|good morning|good afternoon|good evening)( there)?", t):
        return ("Hello! 😊 Welcome to CodertechPRO. How can I help you today? ")
    return None


@bp.post("/chat")
@require_api_key
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("question"), str):
        raise AppError(400, "invalid_request", 'Send JSON like {"question": "..."}.')
    question = data["question"].strip()
    if not question:
        raise AppError(400, "invalid_request", "The question must not be empty.")
    if len(question) > MAX_QUESTION_CHARS:
        raise AppError(400, "question_too_long", f"Max {MAX_QUESTION_CHARS} characters.")

    reply = smalltalk(question)
    if reply:
        return jsonify({"success": True, "question": question, "answer": reply,
                        "answer_found": True, "sources": []})

    services = current_app.extensions["services"]
    store = services.unanswered

    # 1) Has an admin already answered this (or a very similar) question?
    embedding = store.embed(question)
    try:
        saved = store.find_answer(question, embedding)
    except Exception:
        log.exception("Could not look up saved answers")
        saved = None
    if saved:
        return jsonify({"success": True, "question": question, "answer": saved["answer"],
                        "answer_found": True, "answer_source": "admin", "sources": []})

    # 2) Normal document search + LLM
    contexts = services.retrieval.retrieve(question)
    answer = services.llm.answer(question, contexts) if contexts else None

    # 3) Not found: save it (or add 1 to its count) and offer an email update
    if answer is None:
        try:
            question_id = store.record(question, embedding)
        except Exception:
            log.exception("Could not save the unanswered question")
            question_id = None
        body = {"success": True, "question": question, "answer": NOT_FOUND_MESSAGE,
                "answer_found": False, "sources": []}
        if question_id:
            body.update(question_id=question_id, ask_email=True, follow_up=EMAIL_OFFER_MESSAGE)
        return jsonify(body)

    sources, seen = [], set()
    for c in contexts:
        key = (c["document_id"], c["page"])
        if key not in seen:
            seen.add(key)
            sources.append({"document_id": c["document_id"], "filename": c["filename"],
                            "page": c["page"]})
        return jsonify({"success": True, "question": question, "answer": answer,
                    "answer_found": True, "sources": sources})


@bp.post("/chat/notify")
@require_api_key
def notify():
    """The customer chose to receive an email when their unanswered question is answered."""
    data = request.get_json(silent=True)
    if (not isinstance(data, dict) or not isinstance(data.get("question_id"), str)
            or not isinstance(data.get("email"), str)):
        raise AppError(400, "invalid_request", 'Send JSON like {"question_id": "q_abc", "email": "a@b.com"}.')
    current_app.extensions["services"].unanswered.add_email(data["question_id"], data["email"])
    return jsonify({"success": True, "message": "We'll email you as soon as we have an answer."})