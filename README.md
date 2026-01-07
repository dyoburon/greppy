# Greppy

Semantic code search CLI using ChromaDB + Ollama. Integrates with Claude Code via Skills.

**No Docker required.** Everything runs locally.

![Greppy Demo](experiment.gif)

*Video sped up 3x. With Greppy: 37s | Without Greppy: 1m 20s*

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

**Option A: Via Homebrew (recommended)**
```bash
brew tap dyoburon/greppy
brew install greppy
```

**Option B: Via pip**
```bash
pip install -e /path/to/greppy
```

**Option C: Via pipx**
```bash
pipx install /path/to/greppy
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

### Setup

Create a `.claude` folder in your project with these files:

#### 1. `.claude/settings.json`

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Grep",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'BLOCKED: Use greppy instead. Run: greppy search \"query\" for semantic search, or greppy exact \"pattern\" for exact matches.' && exit 1"
          }
        ]
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

#### 2. `.claude/skills/code-search/SKILL.md`

```markdown
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

### Semantic Search
\`\`\`bash
greppy search "your query" -n 10
\`\`\`

### Exact Match
\`\`\`bash
greppy exact "pattern"
\`\`\`
```

#### 3. Add to `CLAUDE.md` (recommended)

Add this to your project's `CLAUDE.md` file:

```markdown
## Code Search - IMPORTANT

**Always use `greppy` for searching code in this codebase.** Do NOT use Glob, Grep, find, or the Explore agent.

\`\`\`bash
# Semantic search (find by meaning/concept)
greppy search "authentication logic"

# Exact pattern match
greppy exact "def process_payment"
\`\`\`

The index is already built. Just run the search commands directly.
```

### Quick Setup (Copy Files)

Or simply copy the `.claude` folder from greppy:

```bash
cp -r /path/to/greppy/.claude /path/to/your/project/
```

Then restart Claude Code to load the settings.

### How It Works

**Layer 1: Skill (Proactive)** - The skill teaches Claude when to use greppy:
```
"find authentication logic" → Skill matches → greppy search "authentication"
```

**Layer 2: Hook (Reactive)** - If Claude tries Grep anyway, it gets blocked:
```
Claude tries Grep → BLOCKED → Message: "Use greppy instead" → Claude adapts
```

**Layer 3: CLAUDE.md (Instruction)** - Explicit instruction to use greppy for all code search

## Data Storage

Greppy stores indexes in `~/.greppy/chroma/`. Each project gets its own collection.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Ollama not running | `ollama serve` |
| Model not found | `ollama pull nomic-embed-text` |
| greppy not found | `brew tap dyoburon/greppy && brew install greppy` |
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
