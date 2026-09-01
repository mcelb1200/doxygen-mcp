# CLAUDE.md — doxygen-mcp

MCP server for generating and querying Doxygen documentation. Hard fork under `hoyt-harness` GitHub account. Python, managed with **uv**.

## Development Environment

```bash
uv venv && uv sync
uv run pytest
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Repo Structure

GNU Coding Standards file layout (AUTHORS.md, BUGS.md, CONTRIBUTING.md, COPYING.md, README.md, USING.md). Source under `src/`, tests under `tests/`, examples under `examples/`.

## CI / Hooks

`hooks/ci-check.sh` (rolled out 2026-06-21) is the single CI source of truth — called by both the pre-push hook and `.github/workflows/ci.yml`.

## Standards

Follow the [Positronikal Coding Standards](https://github.com/Positronikal/PositronikalCodingStandards/tree/main/standards/) and GNU Coding Standards for structure and formatting.
