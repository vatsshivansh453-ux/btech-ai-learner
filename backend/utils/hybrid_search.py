import re
from rank_bm25 import BM25Okapi


def _tokenize(text):
    # Strip punctuation so e.g. "(ML)" in a chunk still matches a query for "ml"
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_search(question, pdf_chunks, k=15, user_id=None):
    scoped = [c for c in pdf_chunks if c.get("user_id") == user_id] if user_id is not None else pdf_chunks
    if not scoped:
        return []

    corpus = [_tokenize(c["text"]) for c in scoped]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(question))

    ranked = sorted(zip(scores, scoped), key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in ranked[:k]]
