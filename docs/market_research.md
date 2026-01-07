# Market Research: Semantic Code Search Tools

## Executive Summary

Several open-source semantic code search tools already exist. **CodeGrok MCP** and **smart-coding-mcp** are the most promising candidates that closely match our requirements: fully local, MCP-compatible, and designed for Claude Code integration. Building from scratch may not be necessary.

---

## Tool Comparison Matrix

| Tool | Local/Offline | Open Source | Claude Code Integration | Maintained | Cost |
|------|---------------|-------------|------------------------|------------|------|
| **CodeGrok MCP** | Yes | MIT | Yes (native) | Active | Free |
| **smart-coding-mcp** | Yes | Yes | Yes (MCP) | Active | Free |
| **Bloop** | Yes | Apache 2.0 | No | **Archived** | Free |
| **sturdy-dev/semantic-code-search** | Yes | AGPL-3.0 | No | Stale (2022) | Free |
| mgrep | No (cloud) | Apache 2.0 | Yes | Active | Freemium |
| Greptile | No (API) | No | Via MCP | Active | $30/dev/mo |
| Sourcegraph Cody | Partial | Partial | No | Active | Enterprise |

---

## Detailed Analysis

### Tier 1: Strong Candidates (Match Our Requirements)

#### CodeGrok MCP
**GitHub**: [github.com/rdondeti/CodeGrok_mcp](https://github.com/rdondeti/CodeGrok_mcp)

**Pros**:
- 100% local, no API keys needed
- Native Claude Code integration (`claude mcp add codegrok-mcp`)
- Tree-sitter AST parsing (code-aware chunking)
- Claims "10-100x fewer tokens"
- 9 language support
- Incremental indexing
- GPU acceleration when available

**Cons**:
- New project (low stars)
- Single maintainer
- No hybrid BM25 search

**Tech Stack**: Python, Tree-sitter, CodeRankEmbed model (768d vectors)

**Verdict**: Very close to what we'd build. Worth trying first.

---

#### smart-coding-mcp
**GitHub**: [github.com/omar-haris/smart-coding-mcp](https://github.com/omar-haris/smart-coding-mcp)

**Pros**:
- Fully local (nomic-embed-text model)
- MCP server for Claude Desktop/Cursor/etc
- Matryoshka embeddings (flexible dimensions 64-768d)
- SQLite caching (5-10x faster than JSON)
- Package version lookup (20+ ecosystems)
- Progressive indexing
- 158 stars, active development

**Cons**:
- Claude Code CLI integration unclear (designed for Claude Desktop)
- No explicit Tree-sitter AST parsing
- Regex-based chunking may be less accurate

**Tech Stack**: Python, nomic-embed-text-v1.5, SQLite

**Verdict**: More mature than CodeGrok. Good alternative.

---

### Tier 2: Partial Matches

#### Bloop
**GitHub**: [github.com/BloopAI/bloop](https://github.com/BloopAI/bloop)

**Pros**:
- Full-featured: semantic + regex + code navigation
- Uses both Tantivy (BM25) AND Qdrant (vectors) — true hybrid
- On-device MiniLM embeddings
- Beautiful desktop app
- Apache 2.0 license

**Cons**:
- **ARCHIVED January 2025** — no longer maintained
- No Claude Code integration
- Requires OpenAI API key for chat features
- Complex Rust codebase to fork/maintain

**Tech Stack**: Rust, Tantivy, Qdrant, Tauri, React

**Verdict**: Best architecture, but dead project. Could fork for components.

---

#### sturdy-dev/semantic-code-search
**GitHub**: [github.com/sturdy-dev/semantic-code-search](https://github.com/sturdy-dev/semantic-code-search)

**Pros**:
- Simple CLI (`pip install semantic-code-search`)
- 100% local
- 10 language support
- Clustering feature (find duplicates)

**Cons**:
- Last commit 2022 — likely abandoned
- No MCP/Claude integration
- AGPL license (restrictive)
- No incremental indexing

**Tech Stack**: Python, sentence-t5 model

**Verdict**: Dated. Not recommended.

---

### Tier 3: Cloud/Paid Solutions (Not Our Target)

#### mgrep (mixedbread-ai)
- Cloud-dependent despite CLI
- Free tier: only 100 queries/month
- Good quality but vendor lock-in

#### Greptile
- API-only, $30/dev/month
- SOC2 compliant, enterprise-focused
- Self-host option but still needs their infra

#### Sourcegraph Cody
- Enterprise pricing
- Requires Sourcegraph instance
- Sends code to external LLM services

---

## Key Technical Insights

### From Greptile's Research
> "Semantic search on codebases works better if you first translate the code to natural language before generating embedding vectors."

> "Searching over a natural language summary of the codebase yields better results than searching over the code directly."

This suggests embedding docstrings/comments/summaries rather than raw code improves retrieval quality.

### From Bloop's Architecture
Bloop's combination of:
- **Tantivy** for BM25 keyword search
- **Qdrant** for semantic vector search
- **Tree-sitter** for code parsing

...validates our proposed hybrid architecture.

---

## Recommendation

### Option A: Try CodeGrok MCP First (Lowest Effort)
```bash
git clone https://github.com/rdondeti/CodeGrok_mcp.git
cd CodeGrok_mcp
./setup.sh
claude mcp add codegrok-mcp -- codegrok-mcp
```

Test it on a real project. If it meets 80% of needs, we're done.

### Option B: Try smart-coding-mcp (More Mature)
Better documentation and larger community. Test if MCP works with Claude Code CLI.

### Option C: Build Our Own (Only If A & B Fail)
If existing tools don't meet requirements:
1. Fork CodeGrok MCP as starting point
2. Add Tantivy for hybrid search
3. Improve chunking with better Tree-sitter integration

### Option D: Fork Bloop Components (Advanced)
Extract Tantivy + Qdrant integration from Bloop's Rust codebase for a hybrid solution. High effort but best architecture.

---

## Gap Analysis: What Existing Tools Miss

| Feature | CodeGrok | smart-coding-mcp | Our Ideal |
|---------|----------|------------------|-----------|
| Semantic search | Yes | Yes | Yes |
| BM25 hybrid | No | No | **Yes** |
| Tree-sitter AST | Yes | Partial | Yes |
| Claude Code native | Yes | Partial | Yes |
| Incremental index | Yes | Yes | Yes |
| 10M+ token repos | Untested | Untested | Yes |

The main gap is **hybrid search** (BM25 + semantic). Existing tools are semantic-only.

---

## Next Steps

1. **Install and test CodeGrok MCP** on a real project (~30 min)
2. **Benchmark token savings** vs grep workflow
3. **Test at scale** with a larger repo (500k+ LOC)
4. **Decide**: use as-is, contribute improvements, or build custom

---

## Sources

- [CodeGrok MCP - HackerNoon](https://hackernoon.com/codegrok-mcp-semantic-code-search-that-saves-ai-agents-10x-in-context-usage)
- [smart-coding-mcp - GitHub](https://github.com/omar-haris/smart-coding-mcp)
- [Bloop - GitHub](https://github.com/BloopAI/bloop)
- [sturdy-dev/semantic-code-search - GitHub](https://github.com/sturdy-dev/semantic-code-search)
- [mgrep - GitHub](https://github.com/mixedbread-ai/mgrep)
- [Greptile Pricing](https://www.greptile.com/pricing)
- [Greptile Blog: Semantic Codebase Search](https://www.greptile.com/blog/semantic-codebase-search)
- [Code Context - Milvus Blog](https://milvus.io/blog/build-open-source-alternative-to-cursor-with-code-context.md)
- [Sourcegraph Cody FAQ](https://docs.sourcegraph.com/cody/faq)
