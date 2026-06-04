# Doxygen MCP Extension

This extension provides deep structural understanding and management of Doxygen-based documentation projects.

## Capabilities

- **Project Discovery**: Automatically identifies Doxygen projects and languages.
- **Symbol Resolution**: Finds symbols at specific file/line locations (IDE integration).
- **Structural Analysis**: Navigates class hierarchies, namespaces, and file structures.
- **Refactoring & Surgical Analysis**: Predicts renaming impact using `doxy_rename_impact` and finds exact line-level call sites using `doxy_references`.
- **Token-Efficient Refactoring**: Strip implementation bodies via `doxy_skeleton`, track active working-tree signature deltas via `doxy_virtual_diff`, and trace execution call paths sequentially via `doxy_trace_path`.
- **Documentation & Parity Management**: Generates/refreshes index, performs parity audits (`doxy_parity_check`) for comment/signature parameter mismatches.
- **Incremental Sync**: Updates local index on a single file or directory instantly via `doxy_refresh_delta`.

## Usage Guidelines

- Treat documentation as a live structural map of the codebase.
- Use `doxy_at_loc` when helping with code to understand the context of the current file/line.
- Use `doxy_query` to get detailed documentation for specific symbols.
- Use `doxy_references` and `doxy_rename_impact` during refactoring/renaming tasks to safely locate call sites and identify breaking changes.
- Use `doxy_skeleton` to retrieve structural signatures of a file without implementation noise.
- Use `doxy_virtual_diff` to monitor working tree signature changes and detect contract breakages.
- Use `doxy_trace_path` to build chronological call-path timeline blocks for targeted debugging.
- Use `doxy_parity_check` to verify `@param` documentation correctness.
- If editing files and index gets stale, run `doxy_refresh_delta` on the changed file/directory. If documentation is completely missing or outdated, suggest running `doxy_config` or `doxy_generate`.
