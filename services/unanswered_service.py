import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone

from .errors import AppError

log = logging.getLogger(__name__)

COLLECTION = "unanswered_questions"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAILS_PER_QUESTION = 500
MAX_ANSWER_CHARS = 5000


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(text):
    """Lower-case, drop punctuation, collapse spaces: 'Fee?' and 'fee' match."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


class UnansweredService:
    """Unanswered questions, kept in a collection of the SAME Chroma database the documents use.

    One record per distinct question:
      id        q_<random>
      document  the question text
      embedding the question's embedding (used to match reworded questions)
      metadata  normalized, count, status ('pending' | 'answered'), answer, answered_at,
                created_at, updated_at, emails (JSON list of {"email", "notified"})
    """

    def __init__(self, chroma_client, embedder, mail, threshold=0.88):
        self.col = chroma_client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        self.embedder = embedder
        self.mail = mail
        self.max_distance = 1.0 - threshold  # cosine distance = 1 - similarity
        self._lock = threading.RLock()

    # ---------- helpers ----------
    def embed(self, question):
        """Embedding used to match reworded questions. None if Ollama is unavailable."""
        try:
            return self.embedder.embed_one(question)
        except AppError as exc:
            log.warning("Could not embed question for matching: %s", exc.message)
            return None

    def _get(self, qid):
        res = self.col.get(ids=[qid], include=["documents", "metadatas"])
        if not res["ids"]:
            return None
        return res["ids"][0], res["documents"][0], dict(res["metadatas"][0])

    def _find(self, question, embedding, status=None):
        """Exact (normalised) match first, then the closest reworded question."""
        norm = normalize(question)
        where = {"$and": [{"normalized": norm}, {"status": status}]} if status else {"normalized": norm}
        res = self.col.get(where=where, limit=1, include=["documents", "metadatas"])
        if res["ids"]:
            return res["ids"][0], res["documents"][0], dict(res["metadatas"][0])
        if embedding is None or self.col.count() == 0:
            return None
        res = self.col.query(query_embeddings=[embedding], n_results=1,
                             where={"status": status} if status else None,
                             include=["documents", "metadatas", "distances"])
        if res["ids"] and res["ids"][0] and res["distances"][0][0] <= self.max_distance:
            return res["ids"][0][0], res["documents"][0][0], dict(res["metadatas"][0][0])
        return None

    # ---------- chat side ----------
    def find_answer(self, question, embedding=None):
        """Return {'id', 'answer'} if an admin already answered this question, else None."""
        with self._lock:
            found = self._find(question, embedding, status="answered")
            if not found:
                return None
            qid, _, meta = found
            meta["count"] += 1
            meta["updated_at"] = _now()
            self.col.update(ids=[qid], metadatas=[meta])
            return {"id": qid, "answer": meta["answer"]}

    def record(self, question, embedding=None):
        """Save an unanswered question, or add 1 to its count if asked before. Returns its id."""
        embedding = embedding or self.embed(question)
        with self._lock:
            now = _now()
            found = self._find(question, embedding)
            if found:
                qid, _, meta = found
                meta["count"] += 1
                meta["updated_at"] = now
                self.col.update(ids=[qid], metadatas=[meta])
                return qid
            if embedding is None:
                log.warning("Question not saved: the embedding model is unavailable.")
                return None
            qid = "q_" + uuid.uuid4().hex[:12]
            self.col.add(ids=[qid], documents=[question[:2000]], embeddings=[embedding],
                         metadatas=[{"normalized": normalize(question), "count": 1, "status": "pending",
                                     "answer": "", "answered_at": "", "created_at": now,
                                     "updated_at": now, "emails": "[]"}])
            return qid

    def add_email(self, question_id, email):
        """Attach a customer's email to a question. If it is already answered, send the answer now."""
        email = (email or "").strip().lower()
        if len(email) > 254 or not EMAIL_RE.match(email):
            raise AppError(400, "invalid_email", "Please enter a valid email address.")
        with self._lock:
            got = self._get(question_id)
            if not got:
                raise AppError(404, "question_not_found", "Question not found.")
            _, _, meta = got
            emails = json.loads(meta["emails"])
            if len(emails) >= MAX_EMAILS_PER_QUESTION:
                raise AppError(429, "too_many_emails", "Too many email requests for this question.")
            if not any(e["email"] == email for e in emails):
                emails.append({"email": email, "notified": False})
                meta["emails"] = json.dumps(emails)
                self.col.update(ids=[question_id], metadatas=[meta])
            answered = meta["status"] == "answered"
        if answered:
            self.send_updates(question_id)

    # ---------- admin side ----------
    def list(self, status="all"):
        with self._lock:
            res = self.col.get(include=["documents", "metadatas"])
        items = []
        for qid, text, m in zip(res["ids"], res["documents"], res["metadatas"]):
            if status in ("pending", "answered") and m["status"] != status:
                continue
            items.append({"id": qid, "question": text, "count": m["count"], "status": m["status"],
                          "answer": m["answer"], "answered_at": m["answered_at"],
                          "created_at": m["created_at"], "updated_at": m["updated_at"],
                          "emails": json.loads(m["emails"])})
        items.sort(key=lambda i: i["updated_at"], reverse=True)
        items.sort(key=lambda i: (i["status"] != "pending", -i["count"]))
        return items

    def save_answer(self, question_id, answer):
        answer = (answer or "").strip()
        if not answer:
            raise AppError(400, "empty_answer", "Please type an answer first.")
        if len(answer) > MAX_ANSWER_CHARS:
            raise AppError(400, "answer_too_long", f"Max {MAX_ANSWER_CHARS} characters.")
        with self._lock:
            got = self._get(question_id)
            if not got:
                raise AppError(404, "question_not_found", "Question not found.")
            _, _, meta = got
            now = _now()
            meta.update(answer=answer, status="answered", answered_at=now, updated_at=now)
            self.col.update(ids=[question_id], metadatas=[meta])
        return self.send_updates(question_id)

    def send_updates(self, question_id):
        """Email everyone who asked for an update and has not been emailed yet."""
        with self._lock:
            got = self._get(question_id)
            if not got:
                return {"sent": 0, "failed": 0, "mail_disabled": False}
            _, question, meta = got
            answer = meta["answer"]
            waiting = [e["email"] for e in json.loads(meta["emails"]) if not e["notified"]]
        if not waiting:
            return {"sent": 0, "failed": 0, "mail_disabled": False}
        if not self.mail.enabled:
            log.warning("SMTP is not configured; %d customer(s) were not emailed.", len(waiting))
            return {"sent": 0, "failed": len(waiting), "mail_disabled": True}
        sent = self.mail.send_answer(waiting, question, answer)  # slow network call: no lock held
        with self._lock:
            got = self._get(question_id)
            if got:
                _, _, meta = got
                emails = json.loads(meta["emails"])
                for e in emails:
                    if e["email"] in sent:
                        e["notified"] = True
                meta["emails"] = json.dumps(emails)
                self.col.update(ids=[question_id], metadatas=[meta])
        return {"sent": len(sent), "failed": len(waiting) - len(sent), "mail_disabled": False}

    def delete(self, question_id):
        with self._lock:
            if not self._get(question_id):
                raise AppError(404, "question_not_found", "Question not found.")
            self.col.delete(ids=[question_id])