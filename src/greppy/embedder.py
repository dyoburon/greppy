"""Embeddings via Ollama."""

import requests
from typing import List

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text"


def get_embeddings(texts: List[str], model: str = DEFAULT_MODEL) -> List[List[float]]:
    """Get embeddings from Ollama."""
    embeddings = []

    for text in texts:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30,
        )
        response.raise_for_status()
        embeddings.append(response.json()["embedding"])

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
