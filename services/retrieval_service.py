class RetrievalService:
    def __init__(self, embedder, vector_store, top_k, max_distance):
        self.embedder = embedder
        self.vector_store = vector_store
        self.top_k = top_k
        self.max_distance = max_distance

    def retrieve(self, question):
        embedding = self.embedder.embed_one(question)
        hits = self.vector_store.query(embedding, self.top_k)
        return [h for h in hits if h["distance"] <= self.max_distance]
