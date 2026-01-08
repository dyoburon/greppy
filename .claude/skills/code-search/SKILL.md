---
name: code-search
description: Semantic code search for finding code by meaning. Use when searching for concepts, logic, patterns, or asking "where is X handled" or "find code that does Y".
allowed-tools: Bash(greppy:*)
---

# Code Search Skill

## When to Use This Skill

Use `greppy search` for:
- Finding code by concept ("authentication logic", "error handling")
- Exploring unfamiliar codebases
- Searching by intent, not exact text

Use `greppy exact` for:
- Specific strings, function names, imports
- TODOs, FIXMEs, exact patterns

Use `greppy read` for:
- Reading file contents after finding a match
- Viewing context around a specific line

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

### Read File
```bash
greppy read file.py:45       # ~50 lines centered on line 45
greppy read file.py:30-80    # Lines 30-80
greppy read file.py -c 100   # 100 lines of context
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
| Read around line 45 | `greppy read src/auth.py:45` |

## Workflow

1. Check if index exists: `greppy status`
2. If not indexed: `greppy index .`
3. Search: `greppy search "your query"`
4. Read context: `greppy read file.py:45`

## Output Format

Results show file:line with matched content:
```
src/auth/login.ts:45: async function validateUser(token) {
src/auth/login.ts:46:   const decoded = jwt.verify(token);
--
src/middleware/auth.ts:12: export const requireAuth = ...
```
