# Specification: MCP Python SDK v1 → v2 Migration

**Feature Branch**: `001-mcp-v2-migration`

**Created**: 2026-09-01

**Status**: Draft

**Reference**: [MCP Python SDK v1→v2 Migration Guide](https://py.sdk.modelcontextprotocol.io/migration/)

---

## Overview

Migrate `doxygen-mcp` from `mcp>=1.0.0,<2.0.0` to `mcp>=2.0.0,<3.0.0`. The
mcp v2 SDK removes `mcp.server.fastmcp` entirely — it exists only as an error
stub that raises `ModuleNotFoundError` with a pointer to the migration guide.
`FastMCP` is renamed `MCPServer` and moved to `mcp.server.mcpserver`.

This is a mechanical migration. `MCPServer` preserves the full `@mcp.tool()`,
`@mcp.resource()`, and `mcp.run()` decorator API — all tool definitions,
schemas, and runtime behavior remain identical. No user-visible changes.

---

## Scope

### In scope

- `pyproject.toml` — bump `mcp` dependency ceiling from `<2.0.0` to `<3.0.0`
- `src/doxygen_mcp/server.py` — update import and class instantiation
- `uv.lock` — regenerated automatically

### Out of scope

- Tool definitions, schemas, or descriptions (unchanged)
- `DoxygenConfig` model (unchanged)
- Tests (no direct mcp imports; no changes required)
- Any new tools or capabilities

---

## Breaking Changes Being Addressed

### BC-1: `mcp.server.fastmcp` removed; `FastMCP` → `MCPServer`

`mcp.server.fastmcp` is removed in mcp 2.x. Importing it raises
`ModuleNotFoundError`. The replacement is `MCPServer` from
`mcp.server.mcpserver`.

**Before (v1):**
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Doxygen")
```

**After (v2):**
```python
from mcp.server.mcpserver import MCPServer
mcp = MCPServer("Doxygen")
```

The `@mcp.tool()` decorator API and `mcp.run()` call site are unchanged.

---

## User Scenarios & Testing

### User Story 1 — Server starts and tools are available (Priority: P1)

An AI assistant (Claude Desktop or Claude Code via MCP) connects to the
doxygen-mcp server. All 7 tools are available in the tool list and can be
invoked without errors.

**Why this priority**: Core correctness — a server that cannot start or expose
tools is non-functional.

**Independent Test**: Start `uv run doxygen-mcp` and connect; verify tool list
returns 7 tools and at least one tool invocation (`check_doxygen_install`)
succeeds.

**Acceptance Scenarios**:

1. **Given** mcp 2.x is installed, **When** `uv run doxygen-mcp` is executed,
   **Then** the server starts without `ModuleNotFoundError` or import errors.
2. **Given** a running server, **When** a client requests the tool list,
   **Then** all 7 tools are returned with correct names and descriptions.
3. **Given** a running server, **When** `check_doxygen_install` is called,
   **Then** a valid response is returned (either success or "not installed").

---

### User Story 2 — Test suite passes clean (Priority: P2)

All non-integration tests pass under mcp 2.x with no new skips or failures.

**Why this priority**: Regression guard — ensures the migration did not silently
break any tested behavior.

**Independent Test**: `uv run pytest -m "not integration"` exits 0.

**Acceptance Scenarios**:

1. **Given** mcp 2.x installed, **When** `uv run pytest` runs,
   **Then** all tests pass and no new failures are introduced.
2. **Given** the migrated code, **When** `uv run ruff check src/ tests/` runs,
   **Then** 0 lint errors are reported.

---

### Edge Cases

- What if a future mcp 2.x minor release changes `MCPServer` API? The
  `<3.0.0` ceiling protects against major-version breaks while allowing
  minor/patch updates.
- `mcp.run()` is called with no arguments (stdio transport, default). No
  transport parameter changes are needed for doxygen-mcp's use case.

---

## Requirements

### Functional Requirements

- **FR-001**: `pyproject.toml` MUST specify `mcp>=2.0.0,<3.0.0`.
- **FR-002**: `server.py` MUST import `MCPServer` from `mcp.server.mcpserver`.
- **FR-003**: `server.py` MUST instantiate `MCPServer("Doxygen")` in place of
  `FastMCP("Doxygen")`.
- **FR-004**: `uv lock` MUST resolve cleanly to a mcp 2.x release.
- **FR-005**: All 7 tool definitions MUST remain identical (names, descriptions,
  schemas, return behavior).

---

## Acceptance Criteria

### AC-1: Dependency

- `pyproject.toml` specifies `mcp>=2.0.0,<3.0.0`
- `uv lock` resolves cleanly
- `uv sync` installs without conflict

### AC-2: Import health

```bash
uv run python -c "from doxygen_mcp.server import mcp; print(type(mcp).__name__)"
```
Prints `MCPServer`. Exits 0.

### AC-3: Test suite

```bash
uv run pytest
```
All tests pass. No new skips introduced.

### AC-4: Lint

```bash
uv run ruff check src/ tests/
```
Clean (0 errors).

### AC-5: CI gate

`hooks/ci-check.sh` passes green.

---

## What Does Not Change

- All 7 tool names, descriptions, and parameter schemas
- `DoxygenConfig` Pydantic model and `to_doxyfile()` method
- `mcp.run()` call in `main()`
- `__main__.py` and `__init__.py`
- Test suite (no direct mcp imports)
