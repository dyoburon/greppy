"""ChromaDB vector store."""

import gc
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

import chromadb
from chromadb.config import Settings

from .chunker import CodeChunk, chunk_file, get_file_hashes, should_index_file, is_valid_file
from .embedder import get_embeddings, get_embedding

# Batch size for storing to ChromaDB (after embeddings computed)
CHROMA_BATCH_SIZE = 500

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


def index_chunks(project_path: Path, chunks: List[CodeChunk]) -> int:
    """Index chunks into ChromaDB (full reindex).

    Embeds ALL chunks in one call for efficiency, then stores in batches.
    """
    collection = get_collection(project_path)

    # Clear existing data
    try:
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    if not chunks:
        return 0

    # Extract texts for embedding
    texts = [c.content for c in chunks]

    # Get ALL embeddings in one call (much faster than batched calls)
    print(f"Embedding {len(texts)} chunks...", file=sys.stderr)
    embeddings = get_embeddings(texts)

    # Store to ChromaDB in batches (to avoid memory issues)
    total_indexed = 0
    for i in range(0, len(chunks), CHROMA_BATCH_SIZE):
        batch_end = min(i + CHROMA_BATCH_SIZE, len(chunks))
        batch_chunks = chunks[i:batch_end]
        batch_embeddings = embeddings[i:batch_end]
        batch_texts = texts[i:batch_end]

        collection.add(
            ids=[c.id for c in batch_chunks],
            embeddings=batch_embeddings,
            documents=batch_texts,
            metadatas=[
                {
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                }
                for c in batch_chunks
            ],
        )
        total_indexed += len(batch_chunks)

        # Free memory between batches
        gc.collect()

    # Save manifest
    hashes = get_file_hashes(project_path)
    save_manifest(project_path, hashes)

    return total_indexed


def index_incremental(project_path: Path) -> Tuple[int, int, int]:
    """Incrementally index only changed files.

    Returns: (added_chunks, deleted_chunks, files_updated)
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
            if not file_path.exists():
                continue
            # Apply same filters as full index
            if not should_index_file(file_path):
                continue
            valid, reason = is_valid_file(file_path)
            if not valid:
                continue
            chunks.extend(chunk_file(file_path))

        if chunks:
            # Get all embeddings in one call
            texts = [c.content for c in chunks]
            embeddings = get_embeddings(texts, show_progress=False)

            # Store to ChromaDB in batches
            for i in range(0, len(chunks), CHROMA_BATCH_SIZE):
                batch_end = min(i + CHROMA_BATCH_SIZE, len(chunks))
                batch_chunks = chunks[i:batch_end]
                batch_embeddings = embeddings[i:batch_end]
                batch_texts = texts[i:batch_end]

                collection.add(
                    ids=[c.id for c in batch_chunks],
                    embeddings=batch_embeddings,
                    documents=batch_texts,
                    metadatas=[
                        {
                            "file_path": c.file_path,
                            "start_line": c.start_line,
                            "end_line": c.end_line,
                        }
                        for c in batch_chunks
                    ],
                )
                added_count += len(batch_chunks)

    # Save updated manifest
    hashes = get_file_hashes(project_path)
    save_manifest(project_path, hashes)

    return added_count, deleted_count, len(files_to_index)


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
