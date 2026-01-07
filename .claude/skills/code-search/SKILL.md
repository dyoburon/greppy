---
name: code-search
description: Semantic code search for finding code by meaning. Use when searching for concepts, logic, patterns, or asking "where is X handled" or "find code that does Y".
allowed-tools: Bash(greppy:*), Bash(npx greppy:*), Read, Glob
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
