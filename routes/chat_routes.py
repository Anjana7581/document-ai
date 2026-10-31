import re

from flask import Blueprint, current_app, jsonify, request

from services.errors import AppError
from services.llm_service import NOT_FOUND_MESSAGE

from .auth import require_api_key

bp = Blueprint("chat", __name__, url_prefix="/api")
MAX_QUESTION_CHARS = 2000


def smalltalk(text):
    t = " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())
    words = len(t.split())
    if re.search(r"\b(how are you|how r u|how are u|whats up)\b", t):
        return ("I'm doing well, thank you for asking! 😊 How can I help you today? "
                "You can ask me about our Python Algo Class, fees, batch timings or services.")
    if re.search(r"\b(who are you|what are you|your name)\b", t):
        return ("I'm the CodertechPRO virtual assistant. 😊 I can help you with our Python Algo Class, "
                "fees, batch timings, services and contact details.")
    if words <= 5 and re.search(r"\b(thanks|thank you|thankyou|thx)\b", t):
        return "You're most welcome! 😊 If you need anything else, just ask."
    if words <= 4 and re.search(r"\b(bye|goodbye|see you)\b", t):
        return "Thank you for chatting with us! Have a great day. 😊"
    if re.fullmatch(r"(hi+|hello+|hey+|hai|good morning|good afternoon|good evening)( there)?", t):
        return ("Hello! 😊 Welcome to CodertechPRO. How can I help you today? "
                "You can ask me about our Python Algo Class, fees, batch timings or our services.")
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
    contexts = services.retrieval.retrieve(question)
    answer = services.llm.answer(question, contexts) if contexts else None
    if answer is None:
        return jsonify({"success": True, "question": question, "answer": NOT_FOUND_MESSAGE,
                        "answer_found": False, "sources": []})

    sources, seen = [], set()
    for c in contexts:
        key = (c["document_id"], c["page"])
        if key not in seen:
            seen.add(key)
            sources.append({"document_id": c["document_id"], "filename": c["filename"],
                            "page": c["page"]})
    return jsonify({"success": True, "question": question, "answer": answer,
                    "answer_found": True, "sources": sources})