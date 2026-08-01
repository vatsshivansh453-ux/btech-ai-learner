"""
PDF Q&A retrieval + generation — same hybrid-search-then-filter-first
architecture proven out in PDF-LEARNER.
"""

from utils.embedding import create_embedding
from utils.vector_store import search_faiss_scoped
from utils.hybrid_search import bm25_search
from utils.llm import stream_pdf_answer, rewrite_question, generate_chat_title
from utils.memory import add_message, update_session_title
import json


def retrieve_context(search_question, query_embedding, faiss_index, pdf_chunks, user_id):
    k = 15

    faiss_sources = search_faiss_scoped(faiss_index, query_embedding, pdf_chunks, user_id, k=k) if faiss_index else []
    bm25_sources = bm25_search(search_question, pdf_chunks, k=k, user_id=user_id)

    merged, seen = [], set()
    for source in faiss_sources + bm25_sources:
        key = (source["file_name"], source["chunk_number"])
        if key not in seen:
            seen.add(key)
            merged.append(source)

    sources = merged[:15]

    context = "\n\n".join(
        f"SOURCE {i+1}\nFile: {s['file_name']}\nPage: {s['page_number']}\n\nCONTENT:\n{s['text']}"
        for i, s in enumerate(sources)
    )

    return context, sources


def stream_answer(question, faiss_index, pdf_chunks, session_id, history, user_id):
    search_question = rewrite_question(question, history) if history else question

    if not history:
        title = generate_chat_title(question)
        update_session_title(session_id, title)

    query_embedding = create_embedding(search_question)
    context, sources = retrieve_context(search_question, query_embedding, faiss_index, pdf_chunks, user_id)

    add_message(session_id, "user", question)

    full_answer = ""
    for token in stream_pdf_answer(question, context, history):
        full_answer += token
        yield json.dumps({"type": "token", "content": token}) + "\n"

    yield json.dumps({
        "type": "sources",
        "sources": [
            {"file_name": s["file_name"], "page_number": s["page_number"], "chunk_number": s["chunk_number"], "text": s["text"]}
            for s in sources
        ]
    }) + "\n"

    add_message(session_id, "assistant", full_answer)
