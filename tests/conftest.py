import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from services.document_service import DocumentService  # noqa: E402
from services.retrieval_service import RetrievalService  # noqa: E402


class FakeEmbedder:
    fail = False

    def _vec(self, text):
        t = text.lower()
        return [float("course" in t), float("refund" in t), 0.1]

    def embed(self, texts):
        if self.fail:
            raise RuntimeError("boom")
        return [self._vec(t) for t in texts]

    def embed_one(self, text):
        return self._vec(text)


class FakeVector:
    def __init__(self):
        self.rows = []

    def add_chunks(self, document_id, version, filename, chunks, embeddings):
        for c, e in zip(chunks, embeddings):
            self.rows.append({"document_id": document_id, "version": version, "filename": filename,
                              "page": c["page"], "text": c["text"], "emb": e})

    def delete_other_versions(self, document_id, keep):
        self.rows = [r for r in self.rows if not (r["document_id"] == document_id and r["version"] != keep)]

    def delete_document(self, document_id):
        self.rows = [r for r in self.rows if r["document_id"] != document_id]

    def query(self, emb, k):
        def dist(r):
            return sum((a - b) ** 2 for a, b in zip(r["emb"], emb)) ** 0.5
        ranked = sorted(self.rows, key=dist)[:k]
        return [{**r, "distance": dist(r)} for r in ranked]

    def count(self):
        return len(self.rows)

    def heartbeat(self):
        return True


class FakeLLM:
    def answer(self, question, contexts):
        return "Courses: " + contexts[0]["text"][:40]


@pytest.fixture
def env(tmp_path):
    cfg = Config(DOCUMENT_STORAGE_PATH=tmp_path / "documents", VECTOR_DB_PATH=tmp_path / "vdb",
                 MAX_UPLOAD_MB=1, API_KEY="", RELEVANCE_MAX_DISTANCE=0.5)
    embedder, vector = FakeEmbedder(), FakeVector()
    services = SimpleNamespace(
        embedder=embedder, vector=vector, llm=FakeLLM(),
        documents=DocumentService(cfg, embedder, vector),
        retrieval=RetrievalService(embedder, vector, 5, cfg.RELEVANCE_MAX_DISTANCE))
    app = create_app(cfg, services)
    return SimpleNamespace(client=app.test_client(), services=services, cfg=cfg, app=app)


def upload(client, name="courses.txt", content=b"We offer a Python course and a Flask course."):
    return client.post("/api/documents/upload", data={"file": (io.BytesIO(content), name)},
                       content_type="multipart/form-data")
