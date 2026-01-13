"""Embeddings via Ollama."""

import sys
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text"

# Embedding dimension for nomic-embed-text
EMBEDDING_DIM = 768

# Max parallel requests to Ollama
MAX_WORKERS = 10


def _embed_single(args: Tuple[int, str, str]) -> Tuple[int, List[float]]:
    """Embed a single text. Returns (index, embedding) for ordering."""
    i, text, model = args

    try:
        truncated = text[:8000] if len(text) > 8000 else text

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": model, "prompt": truncated},
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        embedding = data.get("embedding", [])

        if not embedding or len(embedding) == 0:
            print(f"Warning: Empty embedding for chunk {i}, using zero vector", file=sys.stderr)
            return (i, [0.0] * EMBEDDING_DIM)

        return (i, embedding)

    except Exception as e:
        print(f"Warning: Embedding failed for chunk {i}: {e}, using zero vector", file=sys.stderr)
        return (i, [0.0] * EMBEDDING_DIM)


def get_embeddings(
    texts: List[str],
    model: str = DEFAULT_MODEL,
    max_workers: int = MAX_WORKERS,
) -> List[List[float]]:
    """Get embeddings from Ollama with parallel requests."""
    if not texts:
        return []

    # Prepare args: (index, text, model)
    args = [(i, text, model) for i, text in enumerate(texts)]

    # Process in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_embed_single, args))

    # Sort by index to maintain order
    results.sort(key=lambda x: x[0])

    # Extract embeddings
    return [embedding for _, embedding in results]


def get_embedding(text: str, model: str = DEFAULT_MODEL) -> List[float]:
    """Get single embedding from Ollama."""
    return get_embeddings([text], model)[0]


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def check_model(model: str = DEFAULT_MODEL) -> bool:
    """Check if the model is available."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            return any(model in m for m in models)
        return False
    except requests.exceptions.ConnectionError:
        return False
