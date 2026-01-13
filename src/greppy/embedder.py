"""Embeddings via CodeRankEmbed (sentence-transformers)."""

import sys
from typing import List

# Lazy load to avoid slow import on every CLI call
_model = None

# Embedding dimension for CodeRankEmbed
EMBEDDING_DIM = 768

# Batch size for encoding
BATCH_SIZE = 64


def _get_model():
    """Lazy load the model on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading CodeRankEmbed model...", file=sys.stderr)
        _model = SentenceTransformer(
            "cornstack/CodeRankEmbed",
            trust_remote_code=True,
        )
        print("Model loaded.", file=sys.stderr)
    return _model


def get_embeddings(
    texts: List[str],
    batch_size: int = BATCH_SIZE,
    show_progress: bool = True,
) -> List[List[float]]:
    """Get embeddings using CodeRankEmbed with true batching."""
    if not texts:
        return []

    model = _get_model()

    # Truncate long texts (CodeRankEmbed has 8192 token context)
    truncated = [text[:32000] if len(text) > 32000 else text for text in texts]

    # Encode with batching - this is truly parallel on GPU/CPU
    embeddings = model.encode(
        truncated,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    # Convert numpy arrays to lists for ChromaDB
    return [emb.tolist() for emb in embeddings]


def get_embedding(text: str) -> List[float]:
    """Get single embedding."""
    return get_embeddings([text], show_progress=False)[0]


def check_model() -> bool:
    """Check if the model can be loaded."""
    try:
        _get_model()
        return True
    except Exception as e:
        print(f"Failed to load model: {e}", file=sys.stderr)
        return False
