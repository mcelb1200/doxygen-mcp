# Doxygen MCP Extension

This extension provides deep structural understanding and management of Doxygen-based documentation projects.

## Capabilities

- **Project Discovery**: Automatically identifies Doxygen projects and languages.
- **Symbol Resolution**: Finds symbols at specific file/line locations (IDE integration).
- **Structural Analysis**: Navigates class hierarchies, namespaces, and file structures.
- **Documentation Management**: Generates and refreshes Doxygen documentation.

## Usage Guidelines

- Treat documentation as a live structural map of the codebase.
- Use `doxy_at_loc` when helping with code to understand the context of the current file/line.
- Use `doxy_query` to get detailed documentation for specific symbols.
- If documentation is missing or outdated, suggest running `doxy_config` or `doxy_generate`.
