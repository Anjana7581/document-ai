import io

from tests.conftest import upload


def test_upload_process_status_list_chat(env):
    c = env.client
    r = upload(c)
    assert r.status_code == 201
    doc_id = r.get_json()["document_id"]
    assert r.get_json()["status"] == "uploaded"

    r = c.post(f"/api/documents/{doc_id}/process")
    assert r.status_code == 200 and r.get_json()["status"] == "indexed"

    assert c.get(f"/api/documents/{doc_id}").get_json()["status"] == "indexed"
    assert c.get("/api/documents").get_json()["count"] == 1

    r = c.post("/api/chat", json={"question": "What courses do you offer?"})
    body = r.get_json()
    assert body["answer_found"] is True
    assert body["sources"][0]["document_id"] == doc_id


def test_chat_without_relevant_documents(env):
    r = env.client.post("/api/chat", json={"question": "What is the refund policy?"})
    body = r.get_json()
    assert r.status_code == 200 and body["answer_found"] is False and body["sources"] == []


def test_validation_errors(env):
    c = env.client
    assert c.post("/api/documents/upload").status_code == 400
    assert upload(c, "bad.exe").status_code == 415
    assert upload(c, "empty.txt", b"").status_code == 400
    assert c.post("/api/chat", json={}).status_code == 400
    assert c.get("/api/documents/doc_missing").status_code == 404
    assert c.get("/api/documents/..%2Fsecret").status_code == 404


def test_duplicate_upload(env):
    upload(env.client)
    r = upload(env.client, "copy.txt")
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "duplicate_document"


def test_upload_too_large(env):
    r = upload(env.client, "big.txt", b"a" * (2 * 1024 * 1024))
    assert r.status_code == 413


def test_reindex_replaces_old_chunks(env):
    c = env.client
    doc_id = upload(c).get_json()["document_id"]
    c.post(f"/api/documents/{doc_id}/process")
    r = c.post(f"/api/documents/{doc_id}/reindex",
               data={"file": (io.BytesIO(b"New refund policy text."), "x.txt")},
               content_type="multipart/form-data")
    assert r.status_code == 200
    texts = [row["text"] for row in env.services.vector.rows]
    assert texts == ["New refund policy text."]


def test_failed_reindex_keeps_old_index(env):
    c = env.client
    doc_id = upload(c).get_json()["document_id"]
    c.post(f"/api/documents/{doc_id}/process")
    before = list(env.services.vector.rows)
    env.services.embedder.fail = True
    r = c.post(f"/api/documents/{doc_id}/reindex")
    assert r.status_code == 500
    assert env.services.vector.rows == before
    assert c.get(f"/api/documents/{doc_id}").get_json()["status"] == "indexed"


def test_delete_removes_everything(env):
    c = env.client
    doc_id = upload(c).get_json()["document_id"]
    c.post(f"/api/documents/{doc_id}/process")
    assert c.delete(f"/api/documents/{doc_id}").status_code == 200
    assert env.services.vector.rows == []
    assert c.get(f"/api/documents/{doc_id}").status_code == 404


def test_api_key_required_when_configured(env):
    env.cfg.API_KEY = "secret"
    assert env.client.get("/api/documents").status_code == 401
    assert env.client.get("/api/documents", headers={"X-API-Key": "secret"}).status_code == 200


def test_health_degraded_without_ollama(env):
    r = env.client.get("/health")
    assert r.status_code in (200, 503)
    assert r.get_json()["checks"]["flask"] == "ok"


def test_chunker_respects_size_and_overlap():
    from services.extraction_service import chunk_text
    chunks = chunk_text("word " * 500, 200, 40)
    assert len(chunks) > 1 and all(len(ch) <= 200 for ch in chunks)
