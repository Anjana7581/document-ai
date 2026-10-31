import logging

import requests

from .errors import AppError

log = logging.getLogger(__name__)
BATCH_SIZE = 32


class EmbeddingService:
    def __init__(self, base_url, model, timeout):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def embed(self, texts):
        vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[i:i + BATCH_SIZE]))
        return vectors

    def embed_one(self, text):
        return self._embed_batch([text])[0]

    def _embed_batch(self, batch):
        try:
            resp = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": batch},
                timeout=self.timeout,
            )
        except requests.Timeout:
            raise AppError(504, "embedding_timeout", "The embedding model timed out.")
        except requests.ConnectionError:
            raise AppError(503, "ollama_unavailable", "Cannot reach Ollama. Is it running?")
        if resp.status_code == 404:
            raise AppError(503, "embedding_model_missing",
                           f"Embedding model '{self.model}' is not installed in Ollama.")
        if resp.status_code != 200:
            log.error("Ollama embed error %s: %s", resp.status_code, resp.text[:300])
            raise AppError(502, "embedding_failed", "The embedding model returned an error.")
        embeddings = resp.json().get("embeddings")
        if not embeddings or len(embeddings) != len(batch):
            raise AppError(502, "embedding_failed", "Unexpected response from the embedding model.")
        return embeddings
