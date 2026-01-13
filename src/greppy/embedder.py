"""Embeddings via CodeRankEmbed (sentence-transformers)."""

import gc
import sys
from typing import List

# Lazy load to avoid slow import on every CLI call
_model = None

# Embedding dimension for CodeRankEmbed
EMBEDDING_DIM = 768

# Internal batch size for model.encode() - smaller = less peak memory
ENCODE_BATCH_SIZE = 32

# Max characters per text (CodeRankEmbed has 8192 token context)
MAX_TEXT_CHARS = 24000


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
    batch_size: int = ENCODE_BATCH_SIZE,
    show_progress: bool = True,
) -> List[List[float]]:
    """Get embeddings using CodeRankEmbed.

    Pass ALL texts at once - this function handles batching internally
    for optimal performance. Avoid calling this repeatedly with small lists.
    """
    if not texts:
        return []

    model = _get_model()

    # Truncate long texts
    truncated = [
        text[:MAX_TEXT_CHARS] if len(text) > MAX_TEXT_CHARS else text
        for text in texts
    ]

    # Encode with internal batching
    # show_progress_bar shows one progress bar for all batches
    embeddings = model.encode(
        truncated,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    # Convert numpy arrays to lists for ChromaDB
    result = [emb.tolist() for emb in embeddings]

    # Free numpy array memory
    del embeddings
    del truncated
    gc.collect()

    return result


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


def unload_model():
    """Unload model to free memory."""
    global _model
    if _model is not None:
        del _model
        _model = None
        gc.collect()
