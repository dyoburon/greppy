"""Embeddings via sentence-transformers with Apple Silicon acceleration."""

import gc
import sys
from typing import List

# Lazy load to avoid slow import on every CLI call
_model = None

# Model to use - all-MiniLM-L6-v2 is fast and good quality
MODEL_NAME = "all-MiniLM-L6-v2"

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384

# Batch size for encoding
ENCODE_BATCH_SIZE = 128

# Max characters per text
MAX_TEXT_CHARS = 8000


def _get_device():
    """Get best available device."""
    import torch
    if torch.backends.mps.is_available():
        return "mps"  # Apple Silicon GPU
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _get_model():
    """Lazy load the model on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        device = _get_device()
        print(f"Loading {MODEL_NAME} on {device}...", file=sys.stderr)

        _model = SentenceTransformer(MODEL_NAME, device=device)
        print("Model loaded.", file=sys.stderr)
    return _model


def get_embeddings(
    texts: List[str],
    batch_size: int = ENCODE_BATCH_SIZE,
    show_progress: bool = True,
) -> List[List[float]]:
    """Get embeddings with hardware acceleration.

    Pass ALL texts at once for optimal performance.
    """
    if not texts:
        return []

    model = _get_model()

    # Truncate long texts
    truncated = [
        text[:MAX_TEXT_CHARS] if len(text) > MAX_TEXT_CHARS else text
        for text in texts
    ]

    # Encode with batching
    embeddings = model.encode(
        truncated,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    # Convert to lists for ChromaDB
    result = [emb.tolist() for emb in embeddings]

    # Free memory
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
