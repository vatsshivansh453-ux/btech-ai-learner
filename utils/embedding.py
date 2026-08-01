from fastembed import TextEmbedding

# fastembed (ONNX) instead of sentence-transformers (PyTorch) — much lighter
# memory footprint, which matters a lot on free-tier hosting (512MB caps).
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def create_embedding(text):
    return list(model.embed([text]))[0]


def create_embeddings(chunks):
    return list(model.embed(chunks))
