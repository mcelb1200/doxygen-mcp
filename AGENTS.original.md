# Instructions for AI Agents (Codebase Investigation)

This document provides guidelines for AI agents (like Jules, Gemini, Claude) on how to effectively use the `doxygen-mcp` server to investigate and understand a codebase. The goal is to maximize context while minimizing token consumption.

## 🎯 Objective
To gain a deep, structured understanding of the project architecture, dependencies, and symbols without reading every source file raw.

## 🛠️ Core Tools & Workflow

### 1. Initial Reconnaissance (Low Token Cost)
Instead of listing all files or reading READMEs immediately, use these tools to get a structural map:

*   **`get_context_info`**:
    *   **Purpose**: Identify the project root, detected language, and if Doxygen is configured.
    *   **Use when**: Starting a session to orient yourself.

*   **`scan_project`**:
    *   **Purpose**: Get a breakdown of file types and counts.
    *   **Use when**: You need to know the scale and primary languages of the project.

### 2. Structural Mapping (Medium Token Cost)
Once oriented, map the architecture:

*   **`get_project_structure`**:
    *   **Purpose**: Returns a hierarchical tree of namespaces, classes, and files.
    *   **Use when**: You need to understand the high-level architecture or find where specific logic resides.
    *   **Tip**: This is much more efficient than `list_files` for understanding code organization.

### 3. Deep Dive into Symbols (Targeted)
When you need to understand *how* a specific component works:

*   **`query_project_reference`**:
    *   **Purpose**: Retrieve detailed documentation (signatures, descriptions, relationships) for a specific class, function, or symbol.
    *   **Argument**: `symbol_name` (e.g., `MyClass`, `processData`).
    *   **Use when**: You encounter an unknown class or function and need to know its contract.
    *   **Advantage**: Provides parsed, relevant info (including inheritance) without the noise of implementation details.

*   **`get_file_structure`**:
    *   **Purpose**: List all symbols (functions, classes, macros) defined in a specific file.
    *   **Argument**: `file_path`.
    *   **Use when**: You are about to edit a file and need to know what's in it, or to verify a file's contents without reading the raw text.

### 4. Contextual Assistance (IDE Integration)
If the user is working in an IDE (VS Code, Cursor):

*   **`query_active_symbol`**:
    *   **Purpose**: Automatically document the symbol at the user's cursor.
    *   **Use when**: The user asks "What does this function do?" or "Explain this code".

## 💡 Best Practices for Token Efficiency

1.  **Prefer `query_project_reference` over `read_file`**:
    *   Reading a raw source file consumes tokens for imports, comments, and implementation details you might not need.
    *   Querying the symbol gives you the interface and documentation, which is often enough to use the component.

2.  **Use `get_project_structure` to navigate**:
    *   Don't guess file paths. Use the structure map to find the exact file defining a class.

3.  **Check `doxygen_status` first**:
    *   If `get_context_info` shows `has_doxyfile: false`, run `auto_configure` first. The tools rely on Doxygen's index.

## 🔄 Example Workflow

**User Request**: "How does the authentication system work?"

**Inefficient Approach**:
1.  `list_files` (token heavy)
2.  `read_file auth.py` (token heavy)
3.  `read_file user.py` (token heavy)

**Efficient Approach (Codebase Investigator)**:
1.  `get_project_structure` -> Find `AuthManager` class and `auth/` directory.
2.  `query_project_reference(symbol_name="AuthManager")` -> Get methods (`login`, `logout`, `verify`).
3.  `get_file_structure(file_path="src/auth/utils.py")` -> See helper functions.
4.  *Only then*, if implementation details are needed: `read_file(...)`.
