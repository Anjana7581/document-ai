import logging
import secrets
from logging.handlers import RotatingFileHandler
from types import SimpleNamespace

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from config import BASE_DIR, Config
from services.errors import AppError

log = logging.getLogger("company_document_ai")


def _setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(BASE_DIR / "logs" / "app.log", maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def build_services(cfg):
    from services.document_service import DocumentService
    from services.embedding_service import EmbeddingService
    from services.llm_service import LLMService
    from services.mail_service import MailService
    from services.retrieval_service import RetrievalService
    from services.unanswered_service import UnansweredService
    from services.vector_store_service import VectorStore

    embedder = EmbeddingService(cfg.OLLAMA_BASE_URL, cfg.EMBEDDING_MODEL, cfg.EMBED_TIMEOUT_SECONDS)
    vector = VectorStore(cfg.VECTOR_DB_PATH)  # loads existing data from disk
    return SimpleNamespace(
        embedder=embedder,
        vector=vector,
        documents=DocumentService(cfg, embedder, vector),
        retrieval=RetrievalService(embedder, vector, cfg.TOP_K, cfg.RELEVANCE_MAX_DISTANCE),
        llm=LLMService(cfg.OLLAMA_BASE_URL, cfg.LLM_MODEL, cfg.LLM_TIMEOUT_SECONDS),
        # Unanswered questions live in a second collection of the same Chroma database.
        unanswered=UnansweredService(vector.client, embedder, MailService(cfg),
                                     cfg.UNANSWERED_MATCH_SIMILARITY),
    )


def create_app(config=None, services=None):
    _setup_logging()
    cfg = config or Config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_UPLOAD_MB * 1024 * 1024
    app.extensions["cfg"] = cfg
    app.extensions["services"] = services or build_services(cfg)

    # Admin login uses a signed cookie. Without SECRET_KEY, admins must log in again after a restart.
    app.secret_key = cfg.SECRET_KEY or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=cfg.COOKIE_SECURE)

    from routes.admin_routes import bp as admin_bp
    from routes.chat_routes import bp as chat_bp
    from routes.document_routes import bp as doc_bp
    from routes.health_routes import bp as health_bp
    from routes.unanswered_routes import bp as unanswered_bp

    for bp in (doc_bp, chat_bp, health_bp, admin_bp, unanswered_bp):
        app.register_blueprint(bp)

    # The chat page: http://127.0.0.1:5000
    @app.get("/")
    def home():
        return send_from_directory(BASE_DIR / "frontend", "index.html")

    # The admin login page: http://127.0.0.1:5000/admin
    @app.get("/admin")
    def admin_page():
        return send_from_directory(BASE_DIR / "frontend" / "admin", "index.html")

    def error(status, code, message, details=None):
        body = {"success": False, "error": {"code": code, "message": message}}
        if details:
            body["error"]["details"] = details
        return jsonify(body), status

    @app.errorhandler(AppError)
    def handle_app_error(e):
        return error(e.status, e.code, e.message, e.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        if e.code == 413:
            return error(413, "file_too_large", f"File exceeds the {cfg.MAX_UPLOAD_MB} MB limit.")
        return error(e.code, e.name.lower().replace(" ", "_"), e.description)

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        log.exception("Unhandled error")
        return error(500, "internal_error", "Something went wrong on the server.")

    return app


if __name__ == "__main__":
    config = Config()
    create_app(config).run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)