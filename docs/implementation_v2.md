# Greppy Implementation Plan v2

## Overview

Build a local CLI tool that replaces grep in Claude Code via hook-based blocking. Semantic search runs 100% locally with no external API costs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code                              │
├─────────────────────────────────────────────────────────────┤
│  User: "Find authentication logic"                          │
│                      │                                       │
│                      ▼                                       │
│  Claude tries: Grep("auth")                                  │
│                      │                                       │
│                      ▼                                       │
│  ┌─────────────────────────────────────┐                    │
│  │  PreToolUse Hook                    │                    │
│  │  matcher: "Grep"                    │                    │
│  │  decision: BLOCK                    │                    │
│  │  message: "Use greppy instead"      │                    │
│  └─────────────────────────────────────┘                    │
│                      │                                       │
│                      ▼                                       │
│  Claude adapts: Bash("greppy search 'authentication'")      │
│                      │                                       │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Greppy CLI                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Indexer    │    │   Search     │    │   Output     │  │
│  │              │    │              │    │   Formatter  │  │
│  │ - Tree-sitter│    │ - Semantic   │    │              │  │
│  │ - Chunking   │    │ - BM25       │    │ - grep-like  │  │
│  │ - Embedding  │    │ - Hybrid     │    │ - JSON       │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Local Storage (~/.greppy/)              │   │
│  │                                                      │   │
│  │  ChromaDB (vectors)  +  Tantivy (BM25)  +  SQLite   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## CLI Interface

### Commands

```bash
# Indexing
greppy index [path]              # Index a directory (default: current)
greppy index --watch [path]      # Index and watch for changes
greppy status                    # Show index status
greppy clear [path]              # Clear index for a path

# Searching
greppy search <query> [options]  # Semantic search (default)
greppy exact <pattern> [options] # Exact pattern match (ripgrep wrapper)

# Configuration
greppy config                    # Show current config
greppy config set <key> <value>  # Update config
```

### Search Options

```bash
greppy search "authentication logic" \
  --top 10           # Number of results (default: 10)
  --threshold 0.5    # Minimum similarity score
  --path ./src       # Limit to directory
  --type py,ts       # Filter by file type
  --context 3        # Lines of context around match
  --json             # Output as JSON
```

### Output Format

Default output mimics grep for familiarity:

```
src/auth/login.ts:45: async function validateUser(token: string) {
src/auth/login.ts:46:   const decoded = jwt.verify(token, SECRET);
src/auth/login.ts:47:   return await User.findById(decoded.userId);
--
src/middleware/auth.ts:12: export const requireAuth = (req, res, next) => {
src/middleware/auth.ts:13:   const token = req.headers.authorization;
src/middleware/auth.ts:14:   if (!token) return res.status(401).send();
--
Score: 0.89 | 2 files | 6 chunks matched
```

JSON output for programmatic use:

```json
{
  "results": [
    {
      "file": "src/auth/login.ts",
      "start_line": 45,
      "end_line": 52,
      "score": 0.92,
      "content": "async function validateUser...",
      "symbol": "validateUser",
      "symbol_type": "function"
    }
  ],
  "metadata": {
    "query": "authentication logic",
    "total_results": 10,
    "search_time_ms": 45
  }
}
```

---

## Components

### 1. Chunker (Tree-sitter)

**Purpose**: Split code into semantic chunks (functions, classes, methods)

**Languages Supported** (Phase 1):
- Python
- TypeScript/JavaScript
- Go
- Rust

**Chunk Types**:
```python
@dataclass
class CodeChunk:
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None      # e.g., "validateUser"
    symbol_type: str | None      # e.g., "function", "class", "method"
    language: str
    hash: str                    # For incremental indexing
```

**Chunking Strategy**:
1. Parse AST with tree-sitter
2. Extract top-level definitions (functions, classes)
3. For large files without clear structure, fall back to sliding window (500 tokens, 100 overlap)
4. Include imports/headers as context

### 2. Embedder

**Model**: `sentence-transformers/all-MiniLM-L6-v2` (default)
- 384 dimensions
- Fast on CPU (~50 chunks/sec)
- Good code understanding

**Alternative** (better for code): `jinaai/jina-embeddings-v2-base-code`
- 768 dimensions
- Trained on code specifically
- Slower but higher quality

**Implementation**:
```python
from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, show_progress_bar=True)

    def embed_query(self, query: str) -> np.ndarray:
        return self.model.encode([query])[0]
```

### 3. Vector Store (ChromaDB)

**Why ChromaDB**:
- Embedded (no separate server)
- Persistent storage
- Simple Python API
- Handles embeddings internally if needed

**Schema**:
```python
collection.add(
    ids=[chunk.hash],
    embeddings=[embedding],
    documents=[chunk.content],
    metadatas=[{
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "symbol_name": chunk.symbol_name,
        "symbol_type": chunk.symbol_type,
        "language": chunk.language,
    }]
)
```

### 4. BM25 Store (Tantivy) - Phase 2

**Why Tantivy**:
- Rust-based, extremely fast
- Python bindings (`tantivy-py`)
- Handles exact keyword matching well

**Schema**:
```python
schema = (
    SchemaBuilder()
    .add_text_field("content", stored=True)
    .add_text_field("file_path", stored=True)
    .add_integer_field("start_line", stored=True)
    .add_text_field("symbol_name", stored=True)
    .build()
)
```

### 5. Hybrid Search

**Reciprocal Rank Fusion (RRF)**:
```python
def hybrid_search(query: str, top_k: int = 10) -> list[Result]:
    # Get results from both systems
    semantic_results = vector_store.search(embed(query), limit=top_k * 2)
    bm25_results = tantivy_index.search(query, limit=top_k * 2)

    # RRF merge
    scores = defaultdict(float)
    k = 60  # RRF constant

    for rank, result in enumerate(semantic_results):
        scores[result.id] += 1 / (k + rank + 1)

    for rank, result in enumerate(bm25_results):
        scores[result.id] += 1 / (k + rank + 1)

    # Sort by combined score
    merged = sorted(scores.items(), key=lambda x: -x[1])
    return [get_result(id) for id, _ in merged[:top_k]]
```

### 6. Incremental Indexer

**Strategy**: Hash-based change detection

```python
def needs_reindex(file_path: str) -> bool:
    current_hash = hash_file(file_path)
    stored_hash = db.get_file_hash(file_path)
    return current_hash != stored_hash

def index_directory(path: str):
    for file in walk_files(path):
        if needs_reindex(file):
            chunks = chunker.chunk(file)
            embeddings = embedder.embed([c.content for c in chunks])
            vector_store.upsert(chunks, embeddings)
            db.update_file_hash(file, hash_file(file))
```

**File Watching** (optional):
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IndexHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if should_index(event.src_path):
            reindex_file(event.src_path)
```

---

## Project Structure

```
greppy/
├── pyproject.toml
├── README.md
├── src/
│   └── greppy/
│       ├── __init__.py
│       ├── cli.py              # Click/Typer CLI
│       ├── chunker.py          # Tree-sitter chunking
│       ├── embedder.py         # Sentence transformers
│       ├── vector_store.py     # ChromaDB wrapper
│       ├── bm25_store.py       # Tantivy wrapper (Phase 2)
│       ├── search.py           # Hybrid search logic
│       ├── indexer.py          # Incremental indexing
│       ├── watcher.py          # File watching
│       ├── output.py           # Formatters (grep-like, JSON)
│       └── config.py           # Configuration management
├── tests/
│   ├── test_chunker.py
│   ├── test_search.py
│   └── fixtures/
└── .claude/
    ├── settings.json           # Hook configuration
    └── hooks/
        └── block-grep.sh       # Grep blocker
```

---

## Claude Code Integration

### Hook Configuration

**.claude/settings.json**:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Grep",
        "command": "echo 'BLOCKED: grep is disabled. Use: greppy search \"<query>\" for semantic search, or greppy exact \"<pattern>\" for exact matches.'",
        "decision": "block"
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(greppy:*)"
    ]
  }
}
```

### CLAUDE.md Instructions

```markdown
## Code Search

This project uses `greppy` for code search. grep is disabled.

### Commands

- `greppy search "<query>"` - Semantic search (use for concepts, logic, intent)
- `greppy exact "<pattern>"` - Exact pattern match (use for specific strings, symbols)
- `greppy status` - Check if index is current

### Examples

| Task | Command |
|------|---------|
| Find authentication logic | `greppy search "authentication"` |
| Find all TODO comments | `greppy exact "TODO"` |
| Find where errors are handled | `greppy search "error handling"` |
| Find specific function | `greppy exact "def processPayment"` |

### When to Use Which

- **Semantic** (`greppy search`): "How does X work?", "Where is Y handled?", concepts
- **Exact** (`greppy exact`): Specific strings, function names, imports, TODOs
```

---

## Dependencies

```toml
[project]
name = "greppy"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "click>=8.0",                    # CLI framework
    "sentence-transformers>=2.2",    # Embeddings
    "chromadb>=0.4",                 # Vector store
    "tree-sitter>=0.20",             # AST parsing
    "tree-sitter-python>=0.20",      # Python grammar
    "tree-sitter-javascript>=0.20", # JS/TS grammar
    "watchdog>=3.0",                 # File watching
    "rich>=13.0",                    # Pretty output
]

[project.optional-dependencies]
bm25 = [
    "tantivy>=0.20",                 # BM25 search (Phase 2)
]
```

---

## Implementation Phases

### Phase 1: MVP (1-2 days)

**Goal**: Working semantic search that can replace grep for exploratory queries

- [ ] CLI skeleton with Click
- [ ] Tree-sitter chunking (Python + JS/TS)
- [ ] Sentence-transformers embedding
- [ ] ChromaDB storage
- [ ] Basic `greppy index` and `greppy search`
- [ ] grep-like output format
- [ ] `greppy exact` (ripgrep wrapper)
- [ ] Claude Code hook setup

**Deliverable**: Can run `greppy search "auth logic"` and get useful results

### Phase 2: Hybrid Search (1 day)

**Goal**: Add BM25 for better exact matching within semantic search

- [ ] Tantivy integration
- [ ] RRF merge logic
- [ ] Combined scoring

**Deliverable**: Hybrid search that handles both semantic and keyword queries well

### Phase 3: Polish (1 day)

**Goal**: Production-ready tool

- [ ] Incremental indexing (hash-based)
- [ ] File watching (`--watch`)
- [ ] More languages (Go, Rust)
- [ ] JSON output format
- [ ] Config file support
- [ ] Better error handling
- [ ] Progress indicators

**Deliverable**: Robust tool ready for daily use

### Phase 4: Optimization (Optional)

- [ ] GPU acceleration for embeddings
- [ ] Parallel indexing
- [ ] Caching layer
- [ ] Index compression

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Index time (100k LOC) | <2 min | CPU, single thread |
| Index time (1M LOC) | <15 min | CPU, single thread |
| Search latency | <200ms | Including embedding |
| Storage overhead | <100MB/100k LOC | Vectors + metadata |
| Memory usage | <500MB | During indexing |

---

## Testing Strategy

### Unit Tests
- Chunker produces valid chunks for each language
- Embedder output dimensions are correct
- Vector store CRUD operations work
- Search returns ranked results

### Integration Tests
- Index a sample repo, search, verify results
- Incremental reindex after file change
- Hook blocks grep and suggests greppy

### Benchmark Tests
- Token usage comparison vs grep workflow
- Search quality (precision@k on labeled queries)
- Indexing speed at various scales

---

## Success Criteria

1. **Token Reduction**: 40%+ fewer tokens vs grep workflow
2. **Speed**: End-to-end search <1 second
3. **Quality**: Finds relevant code on first try >80% of time
4. **Reliability**: Claude uses greppy 100% of time (hook enforced)
5. **Cost**: $0 ongoing (fully local)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Tree-sitter parsing failures | Fall back to sliding window chunking |
| Embedding model too slow | Use smaller model, batch processing |
| ChromaDB scaling issues | Can swap to Milvus Lite if needed |
| Claude ignores instructions | Hook enforcement (blocking) |
| Index corruption | Hash verification, rebuild command |

---

## Next Steps

1. Set up project structure
2. Implement chunker with tree-sitter
3. Implement embedder
4. Implement ChromaDB store
5. Build CLI
6. Test with real repo
7. Set up Claude Code hooks
8. Iterate based on usage
