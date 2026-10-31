import logging

import requests
from flask import Blueprint, current_app, jsonify

bp = Blueprint("health", __name__)
log = logging.getLogger(__name__)


@bp.get("/health")
def health():
    cfg = current_app.extensions["cfg"]
    services = current_app.extensions["services"]
    checks = {"flask": "ok"}

    try:
        resp = requests.get(f"{cfg.OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        installed = [m["name"] for m in resp.json().get("models", [])]

        def has(model):
            return any(n == model or n.startswith(model + ":") for n in installed)

        checks["ollama"] = "ok"
        checks["llm_model"] = "ok" if has(cfg.LLM_MODEL) else f"missing: {cfg.LLM_MODEL}"
        checks["embedding_model"] = "ok" if has(cfg.EMBEDDING_MODEL) else f"missing: {cfg.EMBEDDING_MODEL}"
    except Exception:
        checks["ollama"] = "unavailable"

    try:
        services.vector.heartbeat()
        checks["vector_db"] = "ok"
        checks["indexed_chunks"] = services.vector.count()
    except Exception:
        log.exception("Vector DB health check failed")
        checks["vector_db"] = "unavailable"

    healthy = all(v == "ok" for k, v in checks.items() if k != "indexed_chunks")
    return jsonify({"success": healthy, "status": "healthy" if healthy else "degraded",
                    "checks": checks}), (200 if healthy else 503)
