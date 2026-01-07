# Greppy Implementation Analysis

## Problem Statement

Claude Code uses grep for code search, which leads to:
- Multiple search iterations to find relevant code
- Reading many files to verify relevance
- High token usage (50-100k tokens for complex queries)
- Slow search workflows (10-30 seconds per query)

**Goal**: Build a semantic search tool that reduces tokens sent to Claude Code by 5-10x while remaining free and self-hosted.

---

## Architecture Overview

### Hybrid Search Approach

```
┌──────────────────────────────────────────────────────────┐
│                      User Query                          │
└─────────────────────────┬────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                                 ▼
┌─────────────────────┐          ┌─────────────────────┐
│    Vector Store     │          │      Tantivy        │
│    (Semantic)       │          │      (BM25)         │
│                     │          │                     │
│  "What MEANS this?" │          │ "What CONTAINS this?│
└──────────┬──────────┘          └──────────┬──────────┘
           │                                │
           └───────────┬────────────────────┘
                       ▼
              ┌─────────────────┐
              │  Merge (RRF)    │
              └─────────────────┘
```

### Why Both Components?

| Search Type | Tool | Good For |
|-------------|------|----------|
| Semantic | ChromaDB/FAISS | "find authentication logic" |
| Keyword (BM25) | Tantivy | "getUserById", exact function names |
| **Hybrid** | Both combined | Best of both worlds |

---

## Scale Assumptions

### Target: 10M Token Repository

| Metric | Value |
|--------|-------|
| Lines of code | ~700k-1M |
| Chunks (500 tokens each) | ~20k |
| Vector storage | ~30MB |
| Tantivy index | ~50-100MB |
| **Total disk** | **~150MB** |

### Token Conversion Reference

| Lines of Code | Estimated Tokens |
|---------------|------------------|
| 100k LOC | ~1-1.5M tokens |
| 500k LOC | ~5-7.5M tokens |
| 1M LOC | ~10-15M tokens |

(Rough estimate: 1 line ≈ 10-15 tokens avg)

---

## Performance Estimates

### Indexing Time (One-Time)

| Method | Time |
|--------|------|
| Embeddings (CPU) | ~7 min |
| Embeddings (GPU) | ~40 sec |
| Tantivy | ~30 sec |
| **Total** | **~8 min (CPU) / ~1 min (GPU)** |

### Query Performance

| Method | Latency |
|--------|---------|
| Vector search | <100ms |
| Tantivy BM25 | <10ms |
| Hybrid (both) | <150ms |

---

## Token Savings Analysis

### Current: Claude Code with Grep

```
Complex query: "find where user sessions are validated"

1. Claude runs: grep -r "session" .         → 200 results, ~500 tokens
2. Claude reads 5 files to check            → ~25,000 tokens
3. Claude runs: grep -r "valid" .           → 150 results, ~400 tokens
4. Claude reads 3 more files                → ~15,000 tokens
5. Claude runs: grep -r "auth" .            → 300 results, ~600 tokens
6. Claude reads 2 more files                → ~10,000 tokens

Total: ~51,500 tokens for ONE complex search
```

### With Semantic/Hybrid Search

```
Same query: "find where user sessions are validated"

1. Search returns top 10 chunks             → ~5,000 tokens
2. Claude reads 1 full file for context     → ~5,000 tokens

Total: ~10,000 tokens
```

### Savings Summary

| Query Type | Grep Workflow | Hybrid Search | Savings |
|------------|---------------|---------------|---------|
| Simple (exact match) | ~10k tokens | ~3k tokens | 3x |
| Medium (concept) | ~30k tokens | ~7k tokens | 4x |
| Complex (intent) | ~50-100k tokens | ~10k tokens | **5-10x** |

### Daily Usage Estimate

| Metric | Grep | Hybrid | Savings |
|--------|------|--------|---------|
| Searches per day | ~20 | ~20 | - |
| Avg tokens per search | ~30k | ~5k | 6x |
| **Daily tokens** | ~600k | ~100k | **500k saved** |
| Monthly tokens | ~18M | ~3M | **15M saved** |

---

## Cost Analysis

### DIY Solution: $0 Ongoing

| Item | Cost |
|------|------|
| Embedding model | $0 (open source, runs locally) |
| Tantivy | $0 (open source) |
| ChromaDB/FAISS | $0 (open source) |
| Storage | Local disk, negligible |
| Queries | Unlimited, free |

### vs mgrep Pricing

| | mgrep Free | mgrep Scale | DIY |
|--|------------|-------------|-----|
| Queries/month | 100 | Unlimited | **Unlimited** |
| Ingestion | 2M tokens/mo | Pay per use | **Unlimited** |
| Monthly cost | $0 (limited) | $20 + usage | **$0** |
| 10M token repo | Unusable | ~$75-150/mo | **$0** |

---

## Implementation Components

### Core Stack

```
greppy/
├── chunker.py        # Tree-sitter code-aware chunking
├── embedder.py       # Local embedding model
├── vector_store.py   # ChromaDB for semantic search
├── bm25_store.py     # Tantivy for keyword search
├── search.py         # Hybrid search + RRF merge
├── cli.py            # Command line interface
└── mcp_server.py     # Claude Code integration
```

### Key Dependencies

| Component | Library | Purpose |
|-----------|---------|---------|
| Chunking | tree-sitter | Code-aware splitting |
| Embeddings | sentence-transformers | Local embedding model |
| Vector Store | ChromaDB | Semantic search |
| BM25 | tantivy-py | Keyword search |
| CLI | typer/click | User interface |
| MCP | mcp-python | Claude Code integration |

---

## Phased Implementation

### Phase 1: Semantic Only (MVP)
- **Effort**: 1-1.5 days
- **Quality**: ~80%
- **Token savings**: 5-8x

Components:
1. Tree-sitter chunking
2. Local embeddings (sentence-transformers)
3. ChromaDB vector store
4. Basic CLI
5. MCP server for Claude Code

### Phase 2: Add Hybrid Search
- **Additional effort**: +1 day
- **Quality**: ~90-95%
- **Token savings**: 8-10x

Components:
1. Tantivy BM25 indexing
2. Reciprocal Rank Fusion (RRF) merge
3. Query routing (exact vs semantic)

---

## Complexity Assessment

| Component | Effort | Impact on Quality |
|-----------|--------|-------------------|
| Basic vector search | 4 hours | Gets you 50% there |
| Code-aware chunking | 4-6 hours | Critical for code |
| Hybrid search (BM25 + semantic) | 4-6 hours | +15-20% relevance |
| Smart context extraction | 2-3 hours | Token efficiency |
| CLI interface | 2 hours | Usability |
| MCP integration | 3-4 hours | Claude Code support |

---

## Decision Summary

| Factor | Analysis |
|--------|----------|
| **Need both?** | No — semantic-only gets 80% of benefit |
| **Token savings** | 5-10x reduction (~500k tokens/day) |
| **Speed** | 10-30x faster per query |
| **Cost** | $0 ongoing |
| **Effort** | 1-1.5 days for semantic-only MVP |

**Recommendation**: Start with semantic-only (Phase 1), add Tantivy if exact match misses become an issue.
