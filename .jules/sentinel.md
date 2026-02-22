## 2025-02-18 - Symlink Attack in File Operations
**Vulnerability:** `update_ignore_file` and `create_doxygen_project` were vulnerable to symlink attacks. If a malicious user created a symlink named `.gitignore` or `Doxyfile` pointing to a sensitive file, the server would follow the symlink and overwrite or append to the target file.
**Learning:** `pathlib.Path.exists()` and `open()` follow symlinks by default. Validating the parent directory is safe is not enough if the file itself is a symlink pointing outside. `exists()` returning `False` (for broken symlinks) can still lead to writing to an arbitrary location if `open()` follows the symlink.
**Prevention:** Always check `path.is_symlink()` explicitly before writing to files in user-controlled directories.
## 2024-05-23 - Symlink Traversal via Doxygen Configuration
**Vulnerability:** Doxygen follows symbolic links by default when `RECURSIVE = YES` is set. If a project contains a symlink pointing to a sensitive directory outside the project root (e.g., `/etc` or `~/.ssh`), Doxygen will index those files, potentially exposing their contents or structure via the MCP server.
**Learning:** Tools that scan file systems often default to following symlinks for convenience, prioritizing usability over security. Explicit configuration is required to enforce boundaries.
**Prevention:** Configure `EXCLUDE_SYMLINKS = YES` by default in generated Doxyfiles. Allow users to opt-out via environment variables if needed, but ensure the safe default is applied automatically.

## 2024-05-23 - Robust Configuration Loading with Mocked Dependencies
**Vulnerability:** The configuration loader relied exclusively on Pydantic's internal metadata (`model_fields` or `__fields__`). In restricted environments where dependencies like Pydantic are mocked (lacking these attributes), the security configuration loading failed silently or crashed, potentially leaving the application in an unconfigured or insecure state during tests.
**Learning:** Security-critical code (like configuration loading) must be robust against environment variations. Relying solely on library internals can make the system fragile.
**Prevention:** Implement fallbacks to standard Python introspection (e.g., `cls.__annotations__`) when framework-specific metadata is unavailable. This ensures that security settings are processed correctly even in mocked or minimal environments.
