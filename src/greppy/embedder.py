"""Embeddings via Ollama."""

import sys
import requests
from typing import List

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text"

# Embedding dimension for nomic-embed-text
EMBEDDING_DIM = 768


def get_embeddings(texts: List[str], model: str = DEFAULT_MODEL) -> List[List[float]]:
    """Get embeddings from Ollama with robust error handling."""
    embeddings = []

    for i, text in enumerate(texts):
        try:
            # Truncate very long texts that may cause issues
            truncated = text[:8000] if len(text) > 8000 else text

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": truncated},
                timeout=60,
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding", [])

            # Validate embedding is non-empty
            if not embedding or len(embedding) == 0:
                print(f"Warning: Empty embedding for chunk {i}, using zero vector", file=sys.stderr)
                embeddings.append([0.0] * EMBEDDING_DIM)
            else:
                embeddings.append(embedding)

        except Exception as e:
            # Catch ALL exceptions - network, JSON parsing, KeyError, etc.
            print(f"Warning: Embedding failed for chunk {i}: {e}, using zero vector", file=sys.stderr)
            embeddings.append([0.0] * EMBEDDING_DIM)

    return embeddings


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
