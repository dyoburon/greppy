# Greppy

Semantic code search CLI using ChromaDB + Ollama. Integrates with Claude Code via Skills.

**No Docker required.** Everything runs locally.

## Architecture

```
Claude Code → Skill → greppy CLI → ChromaDB + Ollama
                      (Python)     (embedded)  (local)
```

## Quick Start

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Start Ollama (keep running in background)
ollama serve

# Pull embedding model
ollama pull nomic-embed-text
```

### 2. Install Greppy

```bash
cd /Users/dylan/Desktop/projects/greppy
pip install -e .
```

### 3. Verify Installation

```bash
greppy --help
```

### 4. Index Your Codebase

```bash
cd /path/to/your/project
greppy index .
```

### 5. Search!

```bash
greppy search "authentication logic"
greppy search "error handling" -n 20
greppy exact "TODO"  # Exact pattern match
```

## Usage

### Index a Codebase
```bash
greppy index .
greppy index /path/to/project
greppy index . --force  # Reindex
```

### Semantic Search
```bash
greppy search "authentication logic"
greppy search "how errors are handled" -n 20
greppy search "database queries" -p /path/to/project
```

### Exact Pattern Match
```bash
greppy exact "TODO"
greppy exact "def process_payment"
greppy exact "import React" -p ./src
```

### Check Status
```bash
greppy status
greppy status /path/to/project
```

### Clear Index
```bash
greppy clear
```

## Claude Code Integration

### Two-Layer Protection

**Layer 1: Skill (Proactive)**

The `code-search` Skill automatically activates when your query matches:
```
"find authentication logic" → Skill matches → greppy search "authentication"
```

**Layer 2: Hook (Reactive)**

If Claude tries to use grep anyway, the hook blocks it:
```
Claude tries Grep → BLOCKED → Message: "Use greppy instead" → Claude adapts
```

### Setup Claude Code Integration

Copy the `.claude` folder to your project:
```bash
cp -r /Users/dylan/Desktop/projects/greppy/.claude /path/to/your/project/
```

Or install globally:
```bash
cp -r /Users/dylan/Desktop/projects/greppy/.claude ~/.claude
```

Then restart Claude Code to load the Skill.

### How It Works

```
You: "Find where errors are handled"
         │
         ▼
┌─────────────────────────────┐
│ Skill matches description   │  ← Layer 1 (proactive)
│ "find code by meaning"      │
└─────────────┬───────────────┘
              │
              ▼
   Claude runs: greppy search "error handling"
```

If Claude tries grep anyway:

```
Claude tries: Grep("error")
         │
         ▼
┌─────────────────────────────┐
│ Hook blocks Grep            │  ← Layer 2 (reactive)
│ Message: "Use greppy"       │
└─────────────┬───────────────┘
              │
              ▼
   Claude adapts: greppy search "error"
```

### Result

- Claude **always** uses greppy instead of grep
- Semantic search for concepts/intent
- Exact search for specific patterns
- Faster searches, fewer tokens

## Data Storage

Greppy stores indexes in `~/.greppy/chroma/`. Each project gets its own collection.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Ollama not running | `ollama serve` |
| Model not found | `ollama pull nomic-embed-text` |
| greppy not found | `pip install -e .` in greppy directory |
| Index missing | `greppy index .` |
| Skill not activating | Restart Claude Code |

## Cost

| Component | Cost |
|-----------|------|
| ChromaDB | $0 (embedded, local) |
| Ollama | $0 (local) |
| **Total** | **$0** |

## Tech Stack

- **ChromaDB**: Embedded vector database (no server)
- **Ollama**: Local embeddings via nomic-embed-text
- **Python**: Simple, portable CLI
