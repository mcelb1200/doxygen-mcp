# Full Architectural Overhaul

## Background & Motivation
The `doxygen-mcp` project has integrated essential security and performance improvements. However, to maximize its robustness as an MCP server, we need a unified approach to tool responses, strictly asynchronous file system operations, dynamic cache invalidation, and comprehensive type safety using Pydantic models.

## Scope & Impact
This overhaul touches the core of `src/doxygen_mcp/server.py` and `src/doxygen_mcp/utils.py`. The impact will be widespread, updating all MCP tool return types to a structured Pydantic model (`MCPResult`) and replacing blocking `os` and `Path` calls with `anyio.Path`. Due to these sweeping changes, the entire test suite will require significant updates.

## Proposed Solution
1. **Centralized Result Wrapper**: Implement a generic `MCPResult[T]` Pydantic model that standardizes the format of all MCP tool outputs. This model will serialize directly via FastMCP.
2. **Async Path Validation**: Migrate from `os` and blocking `pathlib.Path` to `anyio.Path` for fully asynchronous filesystem operations.
3. **Dynamic Cache Invalidation**: Implement a background `watchdog` task that monitors the Doxygen executable and associated configuration files to automatically invalidate the version cache.
4. **Type Safety Hardening**: Update all internal functions and MCP tools to return strict Pydantic models instead of untyped `Dict[str, Any]` or unstructured strings.

## Alternatives Considered
An incremental refactor utilizing lightweight decorators and manual `os.stat()` cache checking was considered. While this would minimize test breakage, it does not provide the rigorous type safety and true asynchronous scaling required for a robust production MCP server.

## Implementation Plan
### Phase 1: Core Type Safety & Utilities
* Define `MCPResult[T]` model in a new `types.py` or `config.py` module.
* Replace blocking standard library calls with `anyio.Path` wrappers in `utils.py`.

### Phase 2: Dynamic Caching
* Integrate `watchdog` to monitor the Doxygen executable and Doxyfile.
* Implement a background task in `server.py` to trigger cache invalidation upon file modifications.

### Phase 3: Tool Migration
* Update each `@mcp.tool()` in `server.py` to return the new `MCPResult` or specific Pydantic models.
* Remove legacy string-based formatting (e.g., `[SUCCESS]`, `[ERROR]`).

### Phase 4: Test Suite Overhaul
* Rewrite assertions in `tests/test_server.py` and related test files to expect JSON objects mapping to the new Pydantic models instead of string inclusion matching.

## Verification
* Run the complete test suite utilizing `pytest`.
* Execute the verification script `scripts/verify_changes.py` after updating it to consume JSON-based `MCPResult` structures.

## Migration & Rollback
* **Migration**: The changes will be developed in a dedicated feature branch (`feat/full-architectural-overhaul`).
* **Rollback**: If widespread test failures or unforeseen asynchronous deadlocks occur, the branch can be discarded and we can default to the stable `main` branch established in the previous previous merge.
