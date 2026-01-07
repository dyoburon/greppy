# Greppy Implementation Plan v3

## Overview

Integrate **claude-context** (Zilliz's semantic search engine) into Claude Code using **Skills** instead of MCP. A thin CLI wrapper allows the Skill to invoke claude-context via Bash.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Claude Code                              │
│                                                               │
│  1. User: "Find authentication logic"                         │
│  2. Claude matches → code-search Skill activates              │
│  3. Skill instructs: use greppy CLI via Bash                  │
│  4. Claude runs: Bash("greppy search 'authentication'")       │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                 Greppy CLI (thin wrapper)                     │
│                                                               │
│  greppy index .              # Index codebase                 │
│  greppy search "query"       # Semantic search                │
│  greppy exact "pattern"      # Exact match (ripgrep)          │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              claude-context (search engine)                   │
│                                                               │
│  - Hybrid search (BM25 + semantic vectors)                    │
│  - AST-based code chunking (Tree-sitter)                      │
│  - Incremental indexing (Merkle trees)                        │
│  - 13+ language support                                       │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
          ┌──────────────┐    ┌──────────────┐
          │   Ollama     │    │   Milvus     │
          │ (embeddings) │    │  (vectors)   │
          │   LOCAL      │    │   LOCAL      │
          └──────────────┘    └──────────────┘
```

---

## Components

### 1. claude-context (Backend)

Zilliz's open-source semantic code search engine. Provides:
- **Hybrid search**: BM25 + dense vectors combined
- **AST chunking**: Tree-sitter based, code-aware
- **Incremental indexing**: Only re-indexes changed files
- **~40% token reduction** vs grep workflows

GitHub: https://github.com/zilliztech/claude-context

### 2. Greppy CLI (Wrapper)

A thin CLI that wraps claude-context's functionality for Bash invocation.

```bash
# Commands
greppy index [path]           # → calls claude-context index_codebase
greppy search "query" -n 10   # → calls claude-context search_code
greppy exact "pattern"        # → falls back to ripgrep
greppy status                 # → calls claude-context get_indexing_status
```

### 3. Code Search Skill

A Skill that teaches Claude to use greppy for code exploration.

### 4. Grep Blocking Hook

Prevents Claude from using grep, forcing it to use the Skill.

---

## Setup

### Step 1: Install Backend Dependencies

**Ollama (local embeddings)**:
```bash
# macOS
brew install ollama
ollama serve
ollama pull nomic-embed-text
```

**Milvus (local vector DB)**:
```bash
docker run -d --name milvus \
  -p 19530:19530 \
  -p 9091:9091 \
  milvusdb/milvus:latest \
  milvus run standalone
```

### Step 2: Install claude-context Core

```bash
npm install -g @zilliz/claude-context
```

### Step 3: Install Greppy CLI (Wrapper)

```bash
pip install greppy
# or
pipx install greppy
```

The greppy CLI wraps claude-context and exposes it as simple bash commands.

### Step 4: Create the Skill

**.claude/skills/code-search/SKILL.md**:

```yaml
---
name: code-search
description: Semantic code search for finding code by meaning. Use when searching for concepts, logic, patterns, or asking "where is X handled" or "find code that does Y".
allowed-tools: Bash(greppy:*), Read, Glob
---

# Code Search Skill

## When to Use This Skill

Use `greppy` for:
- Finding code by concept ("authentication logic", "error handling")
- Exploring unfamiliar codebases
- Searching by intent, not exact text

Use `greppy exact` for:
- Specific strings, function names, imports
- TODOs, FIXMEs, exact patterns

## Commands

### Index (first time only)
```bash
greppy index .
```

### Semantic Search
```bash
greppy search "your query" -n 10
```

### Exact Match
```bash
greppy exact "pattern"
```

### Check Status
```bash
greppy status
```

## Examples

| Task | Command |
|------|---------|
| Find auth logic | `greppy search "authentication"` |
| Find error handling | `greppy search "error handling patterns"` |
| Find specific function | `greppy exact "def processPayment"` |
| Find all TODOs | `greppy exact "TODO"` |

## Workflow

1. Check if index exists: `greppy status`
2. If not indexed: `greppy index .`
3. Search: `greppy search "your query"`
4. Read returned files for more context

## Output Format

Results show file:line with matched content:
```
src/auth/login.ts:45: async function validateUser(token) {
src/auth/login.ts:46:   const decoded = jwt.verify(token);
--
src/middleware/auth.ts:12: export const requireAuth = ...
```
```

### Step 5: Configure Hook to Block Grep

**.claude/settings.json**:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Grep",
        "command": "echo 'BLOCKED: Use the code-search Skill instead. Run: greppy search \"query\" for semantic search, or greppy exact \"pattern\" for exact matches.'",
        "decision": "block"
      }
    ]
  },
  "permissions": {
    "allow": ["Bash(greppy:*)"]
  }
}
```

### Step 6: Add to CLAUDE.md (Belt & Suspenders)

```markdown
## Code Search

This project uses `greppy` for code search. The `code-search` Skill handles this automatically.

**Do not use grep directly** — it is blocked. Use:
- `greppy search "query"` for semantic/concept search
- `greppy exact "pattern"` for exact string matching
```

---

## File Structure

```
project/
├── .claude/
│   ├── settings.json                    # Hook config
│   └── skills/
│       └── code-search/
│           └── SKILL.md                 # Skill definition
├── CLAUDE.md                            # Project instructions
└── ... (your code)
```

---

## How It Works

```
User: "Find where users are authenticated"
            │
            ▼
┌─────────────────────────────────────┐
│  Claude matches "code-search" Skill │
│  based on "find" + "authenticated"  │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Skill loads, instructs Claude to   │
│  use greppy via Bash                │
└─────────────────┬───────────────────┘
                  │
                  ▼
    Bash("greppy search 'authentication'")
                  │
                  ▼
        Results returned to Claude
                  │
                  ▼
      Claude reads files, answers user
```

If Claude tries grep anyway:
```
Claude tries: Grep("auth")
        │
        ▼
    Hook blocks it
        │
        ▼
    Message: "Use greppy instead"
        │
        ▼
    Claude adapts, uses greppy
```

---

## Cost

| Component | Cost |
|-----------|------|
| claude-context | $0 (open source) |
| Greppy CLI wrapper | $0 (open source) |
| Ollama | $0 (local) |
| Milvus | $0 (local Docker) |
| **Total** | **$0** |

---

## Comparison: Skill vs MCP

| Aspect | Skill Approach | MCP Approach |
|--------|----------------|--------------|
| Setup complexity | Simpler | More config |
| Claude invocation | Automatic (description match) | Tool available |
| Requires daemon | No | Yes (MCP server) |
| Dependencies | Just CLI | Node.js + MCP runtime |
| Customization | Edit SKILL.md | Edit MCP config |

---

## Implementation Order

1. **Install backend** (Ollama + Milvus) — 15 minutes
2. **Install claude-context** — 5 minutes
3. **Build greppy CLI wrapper** — 2-4 hours
   - Thin wrapper that calls claude-context via its Node.js API
   - Formats output for grep-like display
4. **Create Skill** — 30 minutes
5. **Configure hook** — 10 minutes
6. **Test & iterate** — 1 hour

**Total: ~4-6 hours**

(Much faster than v2 since claude-context does the heavy lifting)

---

## Testing

After setup:

```
You: "Find where errors are logged"

Expected:
1. Claude activates code-search Skill
2. Runs: greppy search "error logging"
3. Returns relevant code snippets
4. Reads files for more context if needed
```

```
You: "Find all TODO comments"

Expected:
1. Claude activates code-search Skill
2. Runs: greppy exact "TODO"
3. Returns exact matches
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Skill not activating | Check description matches query; restart Claude |
| greppy not found | Ensure it's in PATH; check `which greppy` |
| Index missing | Run `greppy index .` first |
| Hook not blocking | Verify `.claude/settings.json` syntax |
| Results not relevant | Re-index; try different query phrasing |
| Ollama not running | `ollama serve` |
| Milvus not running | `docker start milvus` |
| Embedding errors | Check Ollama has `nomic-embed-text`: `ollama list` |

---

## Why claude-context?

We use claude-context as the backend because it provides:

| Feature | Benefit |
|---------|---------|
| Hybrid search (BM25 + vectors) | Better than semantic-only |
| AST-based chunking | Code-aware, not naive text splits |
| Incremental indexing | Fast re-indexing on file changes |
| 5k+ GitHub stars | Battle-tested, maintained |
| ~40% token reduction | Proven efficiency gains |

Building this from scratch (v2) would take 2-3 days. Using claude-context takes ~4-6 hours.
