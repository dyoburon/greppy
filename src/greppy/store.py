"""ChromaDB vector store."""

import os
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings

from .chunker import CodeChunk
from .embedder import get_embeddings, get_embedding

# Store data in ~/.greppy
GREPPY_DIR = Path.home() / ".greppy"
CHROMA_DIR = GREPPY_DIR / "chroma"


def get_collection_name(project_path: Path) -> str:
    """Generate collection name from project path."""
    # Use path hash to create unique collection name
    import hashlib
    path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
    name = project_path.name.replace("-", "_").replace(".", "_")[:20]
    return f"{name}_{path_hash}"


def get_client() -> chromadb.Client:
    """Get ChromaDB client."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(project_path: Path):
    """Get or create collection for project."""
    client = get_client()
    name = get_collection_name(project_path)
    return client.get_or_create_collection(
        name=name,
        metadata={"project_path": str(project_path.resolve())},
    )


def has_index(project_path: Path) -> bool:
    """Check if project has an index."""
    try:
        collection = get_collection(project_path)
        return collection.count() > 0
    except Exception:
        return False


def index_chunks(project_path: Path, chunks: List[CodeChunk], batch_size: int = 50) -> int:
    """Index chunks into ChromaDB."""
    collection = get_collection(project_path)

    # Clear existing data
    try:
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    total_indexed = 0

    # Process in batches
    batch = []
    for chunk in chunks:
        batch.append(chunk)

        if len(batch) >= batch_size:
            _index_batch(collection, batch)
            total_indexed += len(batch)
            batch = []

    # Index remaining
    if batch:
        _index_batch(collection, batch)
        total_indexed += len(batch)

    return total_indexed


def _index_batch(collection, chunks: List[CodeChunk]):
    """Index a batch of chunks."""
    texts = [c.content for c in chunks]
    embeddings = get_embeddings(texts)

    collection.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in chunks
        ],
    )


def search(project_path: Path, query: str, limit: int = 10) -> List[dict]:
    """Search indexed codebase."""
    collection = get_collection(project_path)

    if collection.count() == 0:
        return []

    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )

    # Format results
    formatted = []
    for i in range(len(results["ids"][0])):
        formatted.append({
            "file_path": results["metadatas"][0][i]["file_path"],
            "start_line": results["metadatas"][0][i]["start_line"],
            "end_line": results["metadatas"][0][i]["end_line"],
            "content": results["documents"][0][i],
            "score": 1 - results["distances"][0][i],  # Convert distance to similarity
        })

    return formatted


def clear_index(project_path: Path):
    """Clear index for project."""
    client = get_client()
    name = get_collection_name(project_path)
    try:
        client.delete_collection(name)
    except Exception:
        pass


def get_stats(project_path: Path) -> dict:
    """Get index stats."""
    try:
        collection = get_collection(project_path)
        return {
            "exists": True,
            "chunks": collection.count(),
            "project": str(project_path.resolve()),
        }
    except Exception:
        return {
            "exists": False,
            "chunks": 0,
            "project": str(project_path.resolve()),
        }
