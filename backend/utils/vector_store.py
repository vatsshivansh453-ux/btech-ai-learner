import faiss
import numpy as np
import pickle
import os


def create_faiss_index(embeddings):
    embeddings = np.array(embeddings).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    return index


def add_embeddings(index, embeddings):
    index.add(np.array(embeddings).astype("float32"))


def search_faiss_scoped(index, query_embedding, chunks, user_id, k=15):
    """
    Search only within a specific user's own chunks (reconstructed
    directly from the shared FAISS index), rather than searching the
    whole shared store and filtering afterwards. Filtering-after can
    silently drop a user's own best-matching chunk once the shared store
    has a lot of other users' content in it — filtering first avoids
    that entirely.
    """
    user_positions = [i for i, c in enumerate(chunks) if c.get("user_id") == user_id]
    if not user_positions:
        return []

    user_vectors = np.array([index.reconstruct(i) for i in user_positions]).astype("float32")
    query_vector = np.array(query_embedding).astype("float32")

    diffs = user_vectors - query_vector
    distances = np.einsum("ij,ij->i", diffs, diffs)
    order = np.argsort(distances)[:k]

    results = []
    for rank in order:
        i = user_positions[rank]
        c = chunks[i]
        results.append({
            "file_name": c["file_name"],
            "page_number": c["page_number"],
            "chunk_number": c["chunk_number"],
            "distance": float(distances[rank]),
            "text": c["text"],
            "user_id": c.get("user_id"),
        })
    return results


def save_vector_store(index, chunks):
    os.makedirs("vector_store", exist_ok=True)
    faiss.write_index(index, "vector_store/faiss.index")
    with open("vector_store/chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)


def load_vector_store():
    if not os.path.exists("vector_store/faiss.index"):
        return None, []
    index = faiss.read_index("vector_store/faiss.index")
    with open("vector_store/chunks.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks
