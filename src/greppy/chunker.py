"""Code chunking - splits files into searchable chunks."""

import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Generator, Dict

# File extensions to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".swift",
    ".md", ".txt", ".yaml", ".yml", ".json",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "myenv", "env",
    "dist", "build", ".next", ".nuxt", "target",
    ".idea", ".vscode", "vendor", ".cache",
    "data", "research_data", "research_data2",  # Large data directories
}

# Max chunk size in characters
MAX_CHUNK_SIZE = 2000
OVERLAP_SIZE = 200


@dataclass
class CodeChunk:
    """A chunk of code for indexing."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_hash: str

    @property
    def id(self) -> str:
        return self.chunk_hash


def hash_content(content: str) -> str:
    """Generate hash for content."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def hash_file(file_path: Path) -> str:
    """Generate hash for entire file content."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return hashlib.md5(content.encode()).hexdigest()
    except Exception:
        return ""


# Files to skip
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "composer.lock",
}


def should_index_file(file_path: Path) -> bool:
    """Check if file should be indexed."""
    if file_path.name in SKIP_FILES:
        return False
    return file_path.suffix.lower() in CODE_EXTENSIONS


def should_skip_dir(dir_name: str) -> bool:
    """Check if directory should be skipped."""
    return dir_name in SKIP_DIRS or dir_name.startswith(".")


def chunk_file(file_path: Path) -> List[CodeChunk]:
    """Split a file into chunks."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if not content.strip():
        return []

    lines = content.split("\n")
    chunks = []

    # Simple chunking: split by lines, respecting max size
    current_chunk_lines = []
    current_size = 0
    start_line = 1

    for i, line in enumerate(lines, 1):
        line_size = len(line) + 1  # +1 for newline

        if current_size + line_size > MAX_CHUNK_SIZE and current_chunk_lines:
            # Save current chunk
            chunk_content = "\n".join(current_chunk_lines)
            chunks.append(CodeChunk(
                file_path=str(file_path),
                start_line=start_line,
                end_line=i - 1,
                content=chunk_content,
                chunk_hash=hash_content(f"{file_path}:{start_line}:{chunk_content}"),
            ))

            # Start new chunk with overlap
            overlap_lines = current_chunk_lines[-3:] if len(current_chunk_lines) > 3 else []
            current_chunk_lines = overlap_lines
            current_size = sum(len(l) + 1 for l in overlap_lines)
            start_line = max(1, i - len(overlap_lines))

        current_chunk_lines.append(line)
        current_size += line_size

    # Don't forget the last chunk
    if current_chunk_lines:
        chunk_content = "\n".join(current_chunk_lines)
        chunks.append(CodeChunk(
            file_path=str(file_path),
            start_line=start_line,
            end_line=len(lines),
            content=chunk_content,
            chunk_hash=hash_content(f"{file_path}:{start_line}:{chunk_content}"),
        ))

    return chunks


def walk_codebase(root_path: Path) -> Generator[Path, None, None]:
    """Walk codebase and yield files to index."""
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter out skip directories
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if should_index_file(file_path):
                yield file_path


def chunk_codebase(root_path: Path) -> Generator[CodeChunk, None, None]:
    """Chunk entire codebase."""
    for file_path in walk_codebase(root_path):
        for chunk in chunk_file(file_path):
            yield chunk


def get_file_hashes(root_path: Path) -> Dict[str, str]:
    """Get hash of each file in codebase."""
    hashes = {}
    for file_path in walk_codebase(root_path):
        rel_path = str(file_path.relative_to(root_path))
        hashes[rel_path] = hash_file(file_path)
    return hashes
