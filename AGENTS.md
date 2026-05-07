# AI Agent Guide (Code Investigation)

Guide for AI agents (Jules, Gemini, Claude). Use `doxygen-mcp` investigate codebase. Max context, min tokens.

## 🎯 Objective
Deep understanding architecture, dependencies, symbols. No raw file read.

## 🛠️ Core Tools & Workflow

### 1. Recon (Low Tokens)
No `list_files`. Use tools for map:

*   **`doxy_context`**:
    *   **Purpose**: Identify root, language, Doxygen config.
    *   **Use**: Orient session.

*   **`doxy_scan`**:
    *   **Purpose**: File types and counts.
    *   **Use**: Know scale, languages.

### 2. Map Architecture (Mid Tokens)
Map structure:

*   **`doxy_structure`**:
    *   **Purpose**: Tree of namespaces, classes, files.
    *   **Use**: High-level architecture, find logic.
    *   **Tip**: Better than `list_files`.

### 3. Deep Symbol Dive (Targeted)
Understand component:

*   **`doxy_query`**:
    *   **Purpose**: Symbol docs (signatures, descriptions, relations).
    *   **Arg**: `symbol_name` (e.g., `MyClass`, `processData`).
    *   **Use**: Unknown class/function contract.
    *   **Win**: Relevant info + inheritance. No implementation noise.

*   **`doxy_file_struct`**:
    *   **Purpose**: List symbols in file.
    *   **Arg**: `file_path`.
    *   **Use**: Before edit, verify contents without raw read.

### 4. IDE Assist
IDE (VS Code, Cursor):

*   **`doxy_active`**:
    *   **Purpose**: Document symbol at cursor.
    *   **Use**: "What this do?" or "Explain code".

## 💡 Best Practices (Token Save)

1.  **`doxy_query` > `read_file`**:
    *   Raw file = too many tokens.
    *   Query symbol = interface + docs. Enough.

2.  **`doxy_structure` to navigate**:
    *   No path guess. Use map find file.

3.  **Check `doxygen_status`**:
    *   If `doxy_context` shows `has_doxyfile: false`, run `doxy_config`. Need index.

## 🔄 Example Workflow

**User**: "How auth work?"

**Bad Approach**:
1.  `list_files` (heavy)
2.  `read_file auth.py` (heavy)
3.  `read_file user.py` (heavy)

**Good Approach (Investigator)**:
1.  `doxy_structure` -> Find `AuthManager` + `auth/`.
2.  `doxy_query(symbol_name="AuthManager")` -> Methods (`login`, `logout`, `verify`).
3.  `doxy_file_struct(file_path="src/auth/utils.py")` -> Helpers.
4.  Need details? `read_file(...)`.

## 📡 Reporting Standards (Inter-Agent)
Use **Hybrid Narrative Compression (Caveman)** for all reports sent to other agents:
- **Technical Terms EXACT**: Keep symbol names, types, and JSON keys raw.
- **Narrative Stripping**: Remove articles/filler from descriptions.
- **Goal**: Maximize SNR, minimize token cost.
