import logging

log = logging.getLogger(__name__)
COLLECTION = "company_documents"
ADD_BATCH = 100


class VectorStore:
    """Persistent ChromaDB collection. Loads existing data automatically on start."""

    def __init__(self, path):
        import chromadb

        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, document_id, version, filename, chunks, embeddings):
        """Add chunks under a version tag. On failure, remove what was added."""
        try:
            for i in range(0, len(chunks), ADD_BATCH):
                part = chunks[i:i + ADD_BATCH]
                self.collection.add(
                    ids=[f"{document_id}:{version}:{i + j}" for j in range(len(part))],
                    documents=[c["text"] for c in part],
                    embeddings=embeddings[i:i + ADD_BATCH],
                    metadatas=[
                        {
                            "document_id": document_id,
                            "filename": filename,
                            "page": c["page"] or 0,
                            "chunk_index": i + j,
                            "version": version,
                        }
                        for j, c in enumerate(part)
                    ],
                )
        except Exception:
            self.delete_version(document_id, version)
            raise

    def delete_version(self, document_id, version):
        self.collection.delete(where={"$and": [{"document_id": document_id}, {"version": version}]})

    def delete_other_versions(self, document_id, keep_version):
        self.collection.delete(
            where={"$and": [{"document_id": document_id}, {"version": {"$ne": keep_version}}]}
        )

    def delete_document(self, document_id):
        self.collection.delete(where={"document_id": document_id})

    def query(self, embedding, top_k):
        total = self.collection.count()
        if total == 0:
            return []
        res = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({
                "text": text,
                "document_id": meta["document_id"],
                "filename": meta["filename"],
                "page": meta["page"] or None,
                "distance": dist,
            })
        return out

    def count(self):
        return self.collection.count()

    def heartbeat(self):
        self.client.heartbeat()
        return True
