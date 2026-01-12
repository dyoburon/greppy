"""Code chunking - splits files into searchable chunks."""

import os
import subprocess
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Generator, Dict, Optional, Tuple

# File extensions to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".swift",
    ".md", ".txt", ".yaml", ".yml", ".json",
}

# Directories to skip (fallback when not in git repo)
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "myenv", "env",
    "dist", "build", ".next", ".nuxt", "target",
    ".idea", ".vscode", "vendor", ".cache",
    "data", "research_data", "research_data2",
}

# Files to skip
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "composer.lock",
}

# Max chunk size in characters
MAX_CHUNK_SIZE = 2000
OVERLAP_SIZE = 200

# Max file size (512 KB)
MAX_FILE_SIZE = 512 * 1024

# Max line length before considering file as minified
MAX_LINE_LENGTH = 2000


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


@dataclass
class SkippedFiles:
    """Track skipped files by reason."""
    large: List[str] = field(default_factory=list)
    binary: List[str] = field(default_factory=list)
    minified: List[str] = field(default_factory=list)
    empty: List[str] = field(default_factory=list)
    encoding: List[str] = field(default_factory=list)
    error: List[str] = field(default_factory=list)

    def total(self) -> int:
        return len(self.large) + len(self.binary) + len(self.minified) + len(self.empty) + len(self.encoding) + len(self.error)

    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "large": self.large,
            "binary": self.binary,
            "minified": self.minified,
            "empty": self.empty,
            "encoding": self.encoding,
            "error": self.error,
        }


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


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_git_files(root_path: Path) -> Optional[List[Path]]:
    """Get files using git ls-files (respects .gitignore)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                file_path = root_path / line
                if file_path.exists() and file_path.is_file():
                    files.append(file_path)
        return files
    except Exception:
        return None


def is_valid_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Check if file is suitable for indexing.

    Returns (valid, skip_reason).
    """
    try:
        size = file_path.stat().st_size
    except (OSError, IOError):
        return False, "error"

    # Empty file
    if size == 0:
        return False, "empty"

    # File too large
    if size > MAX_FILE_SIZE:
        return False, "large"

    # Read first chunk to detect binary/minified
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(8192)
    except (IOError, OSError):
        return False, "error"

    # Binary detection: check for null bytes
    if b'\x00' in sample:
        return False, "binary"

    # Try to decode as text
    try:
        text_sample = sample.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text_sample = sample.decode('latin-1')
        except Exception:
            return False, "encoding"

    # Minified detection: very long lines
    lines = text_sample.split('\n')
    for line in lines[:10]:
        if len(line) > MAX_LINE_LENGTH:
            return False, "minified"

    return True, None


def is_valid_chunk(content: str) -> bool:
    """Check if chunk content is suitable for embedding."""
    stripped = content.strip()

    # Skip empty/whitespace-only
    if not stripped:
        return False

    # Skip if too short
    if len(stripped) < 10:
        return False

    # Skip if mostly non-alphanumeric (binary garbage)
    alnum_count = sum(1 for c in stripped if c.isalnum() or c.isspace())
    if alnum_count / len(stripped) < 0.3:
        return False

    return True


def should_index_file(file_path: Path) -> bool:
    """Check if file should be indexed based on extension."""
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

    current_chunk_lines = []
    current_size = 0
    start_line = 1

    for i, line in enumerate(lines, 1):
        line_size = len(line) + 1

        if current_size + line_size > MAX_CHUNK_SIZE and current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)

            # Only add valid chunks
            if is_valid_chunk(chunk_content):
                chunks.append(CodeChunk(
                    file_path=str(file_path),
                    start_line=start_line,
                    end_line=i - 1,
                    content=chunk_content,
                    chunk_hash=hash_content(f"{file_path}:{start_line}:{chunk_content}"),
                ))

            overlap_lines = current_chunk_lines[-3:] if len(current_chunk_lines) > 3 else []
            current_chunk_lines = overlap_lines
            current_size = sum(len(l) + 1 for l in overlap_lines)
            start_line = max(1, i - len(overlap_lines))

        current_chunk_lines.append(line)
        current_size += line_size

    # Last chunk
    if current_chunk_lines:
        chunk_content = "\n".join(current_chunk_lines)
        if is_valid_chunk(chunk_content):
            chunks.append(CodeChunk(
                file_path=str(file_path),
                start_line=start_line,
                end_line=len(lines),
                content=chunk_content,
                chunk_hash=hash_content(f"{file_path}:{start_line}:{chunk_content}"),
            ))

    return chunks


def walk_codebase(root_path: Path) -> Generator[Path, None, None]:
    """Walk codebase and yield files to index (fallback for non-git repos)."""
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if should_index_file(file_path):
                yield file_path


def chunk_codebase(root_path: Path, skipped: Optional[SkippedFiles] = None) -> Generator[CodeChunk, None, None]:
    """Chunk entire codebase.

    Uses git ls-files if in a git repo (respects .gitignore),
    falls back to walk_codebase otherwise.

    Args:
        root_path: Root directory to index
        skipped: Optional SkippedFiles to track skipped files
    """
    if skipped is None:
        skipped = SkippedFiles()

    # Try git ls-files first
    if is_git_repo(root_path):
        files = get_git_files(root_path)
        if files is not None:
            for file_path in files:
                # Check extension
                if not should_index_file(file_path):
                    continue

                # Validate file
                rel_path = str(file_path.relative_to(root_path))
                valid, reason = is_valid_file(file_path)
                if not valid:
                    getattr(skipped, reason).append(rel_path)
                    continue

                for chunk in chunk_file(file_path):
                    yield chunk
            return

    # Fallback to manual walking
    for file_path in walk_codebase(root_path):
        rel_path = str(file_path.relative_to(root_path))
        valid, reason = is_valid_file(file_path)
        if not valid:
            getattr(skipped, reason).append(rel_path)
            continue

        for chunk in chunk_file(file_path):
            yield chunk


def get_file_hashes(root_path: Path) -> Dict[str, str]:
    """Get hash of each file in codebase."""
    hashes = {}

    # Try git ls-files first
    if is_git_repo(root_path):
        files = get_git_files(root_path)
        if files is not None:
            for file_path in files:
                if not should_index_file(file_path):
                    continue
                valid, _ = is_valid_file(file_path)
                if not valid:
                    continue
                rel_path = str(file_path.relative_to(root_path))
                hashes[rel_path] = hash_file(file_path)
            return hashes

    # Fallback
    for file_path in walk_codebase(root_path):
        valid, _ = is_valid_file(file_path)
        if not valid:
            continue
        rel_path = str(file_path.relative_to(root_path))
        hashes[rel_path] = hash_file(file_path)
    return hashes
