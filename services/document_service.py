import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from .errors import AppError
from .extraction_service import ExtractionError, chunk_pages, extract_text

log = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
PUBLIC_FIELDS = ("document_id", "filename", "extension", "size_bytes", "status", "chunk_count",
                 "page_count", "created_at", "updated_at", "indexed_at", "error")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DocumentService:
    def __init__(self, cfg, embedder, vector_store):
        self.cfg = cfg
        self.embedder = embedder
        self.vector = vector_store
        self.docs_dir = Path(cfg.DOCUMENT_STORAGE_PATH)
        self.meta_dir = self.docs_dir.parent / "metadata"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._recover_interrupted()

    # ---------- metadata helpers ----------
    def _meta_path(self, doc_id):
        return self.meta_dir / f"{doc_id}.json"

    def _read(self, doc_id):
        path = self._meta_path(doc_id)
        if not doc_id.startswith("doc_") or not doc_id[4:].isalnum() or not path.exists():
            raise AppError(404, "document_not_found", "Document not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, doc):
        doc["updated_at"] = _now()
        tmp = self._meta_path(doc["document_id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, self._meta_path(doc["document_id"]))

    def _file_path(self, doc):
        return self.docs_dir / f"{doc['document_id']}{doc['extension']}"

    @staticmethod
    def public(doc):
        return {k: doc.get(k) for k in PUBLIC_FIELDS}

    def _recover_interrupted(self):
        for path in self.meta_dir.glob("doc_*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("status") == "processing":
                doc["status"] = doc.get("previous_status") or "failed"
                doc["error"] = "Processing was interrupted by a restart. Please run it again."
                self._write(doc)

    # ---------- CRUD ----------
    def list(self):
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in self.meta_dir.glob("doc_*.json")]
        docs.sort(key=lambda d: d["created_at"], reverse=True)
        return docs

    def get(self, doc_id):
        return self._read(doc_id)

    def _validate_upload(self, file_storage):
        if file_storage is None or not file_storage.filename:
            raise AppError(400, "missing_file", "Send a file in the 'file' form-data field.")
        ext = Path(file_storage.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise AppError(415, "unsupported_file_type",
                           "Allowed file types: " + ", ".join(sorted(ALLOWED_EXTENSIONS)))
        data = file_storage.read()
        if not data:
            raise AppError(400, "empty_file", "The uploaded file is empty.")
        return ext, data

    def upload(self, file_storage):
        ext, data = self._validate_upload(file_storage)
        digest = hashlib.sha256(data).hexdigest()
        name = secure_filename(file_storage.filename) or f"document{ext}"
        with self._lock:
            for existing in self.list():
                if existing.get("sha256") == digest:
                    raise AppError(409, "duplicate_document",
                                   "This exact file was already uploaded.",
                                   {"document_id": existing["document_id"]})
            doc_id = "doc_" + uuid.uuid4().hex[:12]
            doc = {"document_id": doc_id, "filename": name, "extension": ext,
                   "size_bytes": len(data), "sha256": digest, "status": "uploaded",
                   "chunk_count": 0, "page_count": None, "created_at": _now(),
                   "indexed_at": None, "error": None}
            (self.docs_dir / f"{doc_id}{ext}").write_bytes(data)
            self._write(doc)
        log.info("Uploaded %s as %s (%d bytes)", name, doc_id, len(data))
        return doc

    def delete(self, doc_id):
        doc = self._read(doc_id)
        if doc["status"] == "processing":
            raise AppError(409, "document_busy", "The document is being processed. Try again shortly.")
        self.vector.delete_document(doc_id)
        self._file_path(doc).unlink(missing_ok=True)
        self._meta_path(doc_id).unlink(missing_ok=True)
        log.info("Deleted %s", doc_id)

    # ---------- indexing ----------
    def process(self, doc_id):
        doc = self._read(doc_id)
        if doc["status"] == "indexed":
            raise AppError(409, "already_indexed", "Already indexed. Use /reindex to update it.")
        return self._index(doc_id, new_file=None)

    def reindex(self, doc_id, new_file=None):
        self._read(doc_id)
        return self._index(doc_id, new_file=new_file)

    def _index(self, doc_id, new_file):
        replacement = None
        with self._lock:
            doc = self._read(doc_id)
            if doc["status"] == "processing":
                raise AppError(409, "document_busy", "The document is already being processed.")
            if new_file is not None:
                ext, data = self._validate_upload(new_file)
                if ext != doc["extension"]:
                    raise AppError(400, "extension_mismatch",
                                   f"The new file must be a {doc['extension']} file.")
                replacement = data
            doc["previous_status"] = doc["status"]
            doc["status"] = "processing"
            doc["error"] = None
            self._write(doc)

        final_path = self._file_path(doc)
        temp_path = final_path.with_suffix(final_path.suffix + ".new")
        try:
            source = final_path
            if replacement is not None:
                temp_path.write_bytes(replacement)
                source = temp_path
            pages = extract_text(source, doc["extension"])
            chunks = chunk_pages(pages, self.cfg.CHUNK_SIZE, self.cfg.CHUNK_OVERLAP)
            if not chunks:
                raise ExtractionError("The document produced no text chunks.")
            embeddings = self.embedder.embed([c["text"] for c in chunks])
            version = uuid.uuid4().hex[:8]
            self.vector.add_chunks(doc_id, version, doc["filename"], chunks, embeddings)
            self.vector.delete_other_versions(doc_id, version)  # swap in the new index
            if replacement is not None:
                os.replace(temp_path, final_path)
                doc["sha256"] = hashlib.sha256(replacement).hexdigest()
                doc["size_bytes"] = len(replacement)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            message = exc.message if isinstance(exc, AppError) else (
                str(exc) if isinstance(exc, ExtractionError) else "Unexpected processing error.")
            if not isinstance(exc, (AppError, ExtractionError)):
                log.exception("Processing failed for %s", doc_id)
            else:
                log.warning("Processing failed for %s: %s", doc_id, message)
            with self._lock:
                doc = self._read(doc_id)
                had_index = doc.get("previous_status") == "indexed"
                doc["status"] = "indexed" if had_index else "failed"  # old index is still intact
                doc["error"] = message
                self._write(doc)
            if isinstance(exc, ExtractionError):
                raise AppError(422, "extraction_failed", message)
            raise

        with self._lock:
            doc = self._read(doc_id)
            doc.update(status="indexed", chunk_count=len(chunks), error=None, indexed_at=_now(),
                       page_count=len({c["page"] for c in chunks if c["page"]}) or None)
            doc.pop("previous_status", None)
            self._write(doc)
        log.info("Indexed %s with %d chunks", doc_id, len(chunks))
        return doc
