"""ChromaDB vector store."""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

import chromadb
from chromadb.config import Settings

from .chunker import CodeChunk, chunk_file, get_file_hashes
from .embedder import get_embeddings, get_embedding

# Store data in ~/.greppy
GREPPY_DIR = Path.home() / ".greppy"
CHROMA_DIR = GREPPY_DIR / "chroma"
MANIFEST_DIR = GREPPY_DIR / "manifests"


def get_collection_name(project_path: Path) -> str:
    """Generate collection name from project path."""
    # Use path hash to create unique collection name
    import hashlib
    path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
    name = project_path.name.replace("-", "_").replace(".", "_")[:20]
    return f"{name}_{path_hash}"


def get_manifest_path(project_path: Path) -> Path:
    """Get manifest file path for project."""
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    name = get_collection_name(project_path)
    return MANIFEST_DIR / f"{name}.json"


def load_manifest(project_path: Path) -> Dict[str, str]:
    """Load file hash manifest."""
    manifest_path = get_manifest_path(project_path)
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            return {}
    return {}


def save_manifest(project_path: Path, hashes: Dict[str, str]):
    """Save file hash manifest."""
    manifest_path = get_manifest_path(project_path)
    manifest_path.write_text(json.dumps(hashes, indent=2))


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


def compute_changes(project_path: Path) -> Tuple[Set[str], Set[str], Set[str]]:
    """Compute file changes since last index.

    Returns: (new_files, modified_files, deleted_files)
    """
    old_hashes = load_manifest(project_path)
    new_hashes = get_file_hashes(project_path)

    old_files = set(old_hashes.keys())
    new_files_set = set(new_hashes.keys())

    # Find changes
    added = new_files_set - old_files
    deleted = old_files - new_files_set

    # Find modified (same file, different hash)
    modified = set()
    for f in old_files & new_files_set:
        if old_hashes[f] != new_hashes[f]:
            modified.add(f)

    return added, modified, deleted


def index_chunks(project_path: Path, chunks: List[CodeChunk], batch_size: int = 50) -> int:
    """Index chunks into ChromaDB (full reindex)."""
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

    # Save manifest
    hashes = get_file_hashes(project_path)
    save_manifest(project_path, hashes)

    return total_indexed


def index_incremental(project_path: Path, batch_size: int = 50) -> Tuple[int, int, int]:
    """Incrementally index only changed files.

    Returns: (added_chunks, updated_chunks, deleted_chunks)
    """
    collection = get_collection(project_path)

    added_files, modified_files, deleted_files = compute_changes(project_path)

    # Files that need re-indexing
    files_to_index = added_files | modified_files

    added_count = 0
    deleted_count = 0

    # Delete chunks for modified and deleted files
    files_to_delete = modified_files | deleted_files
    if files_to_delete:
        try:
            # Get all existing chunks
            existing = collection.get(include=["metadatas"])
            ids_to_delete = []
            for i, meta in enumerate(existing["metadatas"]):
                rel_path = str(Path(meta["file_path"]).relative_to(project_path))
                if rel_path in files_to_delete:
                    ids_to_delete.append(existing["ids"][i])

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                deleted_count = len(ids_to_delete)
        except Exception:
            pass

    # Index new/modified files
    if files_to_index:
        chunks = []
        for rel_path in files_to_index:
            file_path = project_path / rel_path
            if file_path.exists():
                chunks.extend(chunk_file(file_path))

        # Process in batches
        batch = []
        for chunk in chunks:
            batch.append(chunk)
            if len(batch) >= batch_size:
                _index_batch(collection, batch)
                added_count += len(batch)
                batch = []

        if batch:
            _index_batch(collection, batch)
            added_count += len(batch)

    # Save updated manifest
    hashes = get_file_hashes(project_path)
    save_manifest(project_path, hashes)

    return added_count, deleted_count, len(files_to_index)


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

    # Also clear manifest
    manifest_path = get_manifest_path(project_path)
    if manifest_path.exists():
        manifest_path.unlink()


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
