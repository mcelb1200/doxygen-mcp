## 2025-02-18 - Symlink Attack in File Operations
**Vulnerability:** `update_ignore_file` and `create_doxygen_project` were vulnerable to symlink attacks. If a malicious user created a symlink named `.gitignore` or `Doxyfile` pointing to a sensitive file, the server would follow the symlink and overwrite or append to the target file.
**Learning:** `pathlib.Path.exists()` and `open()` follow symlinks by default. Validating the parent directory is safe is not enough if the file itself is a symlink pointing outside. `exists()` returning `False` (for broken symlinks) can still lead to writing to an arbitrary location if `open()` follows the symlink.
**Prevention:** Always check `path.is_symlink()` explicitly before writing to files in user-controlled directories.
