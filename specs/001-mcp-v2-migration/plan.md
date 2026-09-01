# Implementation Plan: MCP Python SDK v1 → v2 Migration

**Branch**: `001-mcp-v2-migration` | **Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

---

## Summary

Migrate `doxygen-mcp` from `mcp>=1.0.0,<2.0.0` to `mcp>=2.0.0,<3.0.0`. The
`mcp.server.fastmcp` module was removed in mcp v2; `FastMCP` is renamed
`MCPServer` in `mcp.server.mcpserver`. Three targeted changes cover the full
migration: one dependency bump, one import line, one class reference. All tool
definitions, schemas, and runtime behavior are unchanged.

---

## Technical Context

**Language/Version**: Python >=3.11,<4.0

**Primary Dependencies**: `mcp>=2.0.0,<3.0.0`, `pydantic>=2.0.0`, `lxml>=6.1.0`

**Storage**: N/A

**Testing**: pytest, ruff, mypy (via ci-check.sh)

**Target Platform**: Cross-platform MCP server (stdio transport)

**Project Type**: MCP server / library

**Performance Goals**: N/A (migration only; no behavior change)

**Constraints**: No user-visible changes. No tool renames, schema changes, or
behavior differences.

**Scale/Scope**: 3 file changes, ~3 lines modified.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-mcp-v2-migration/
├── spec.md        # Feature specification
└── plan.md        # This file
```

### Source Code (affected files only)

```text
pyproject.toml                        # mcp ceiling bump
src/doxygen_mcp/server.py             # import + class instantiation
uv.lock                               # auto-regenerated
```

---

## Implementation Steps

### Step 1 — Bump mcp dependency in `pyproject.toml`

**File**: `pyproject.toml`

Change:
```toml
"mcp>=1.0.0,<2.0.0",  # mcp 2.0 removes mcp.server.fastmcp; migration deferred
```
To:
```toml
"mcp>=2.0.0,<3.0.0",
```

Remove the inline comment — the hold is lifted.

**Verify**: `uv lock` resolves without error. `uv sync` installs mcp 2.x.

---

### Step 2 — Update import in `server.py`

**File**: `src/doxygen_mcp/server.py`, line 32

Change:
```python
from mcp.server.fastmcp import FastMCP
```
To:
```python
from mcp.server.mcpserver import MCPServer
```

---

### Step 3 — Update class instantiation in `server.py`

**File**: `src/doxygen_mcp/server.py`, line 39

Change:
```python
mcp = FastMCP("Doxygen")
```
To:
```python
mcp = MCPServer("Doxygen")
```

---

### Step 4 — Regenerate lock file

```bash
uv lock
```

Verify it resolves to a mcp 2.x release with no conflicts.

---

### Step 5 — Verify and run CI gate

```bash
uv sync
uv run python -c "from doxygen_mcp.server import mcp; print(type(mcp).__name__)"
# Expected: MCPServer

hooks/ci-check.sh
# Expected: all checks pass (ruff, pytest)
```

---

## Acceptance Criteria Checklist

- [ ] AC-1: `pyproject.toml` specifies `mcp>=2.0.0,<3.0.0`; `uv lock` resolves cleanly
- [ ] AC-2: `type(mcp).__name__` prints `MCPServer`
- [ ] AC-3: `uv run pytest` — all tests pass
- [ ] AC-4: `uv run ruff check src/ tests/` — 0 errors
- [ ] AC-5: `hooks/ci-check.sh` — green

---

## Version Bump

This is a **MAJOR** version bump. mcp v1→v2 is a breaking protocol dependency
change. Users pinned to `mcp<2.0.0` cannot use this release alongside other
mcp 2.x tools without isolating environments. The changelog must make the
significance of the mcp version upgrade explicit.

Tag after CI passes: `v4.0.0` (next major from current `v3.x` line).
