"""
Git Tracker Utility for Doxygen MCP.
Provides Temporal Context (What Was vs What Is) for source files.
"""
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def get_git_root(filepath: Path) -> Optional[Path]:
    """Find the root of the git repository containing the file."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=filepath.parent,
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None

def check_working_tree(repo_root: Path, filepath: Path) -> str:
    """Check if the file has uncommitted changes in the working tree."""
    try:
        rel_path = filepath.relative_to(repo_root)
        result = subprocess.run(
            ["git", "status", "--porcelain", str(rel_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        status = result.stdout.strip()
        if not status:
            return "[CLEAN]"

        status_code = status[:2]
        if "??" in status_code:
            return "[UNTRACKED] -> A new file exists in the working tree but has not been committed. The AI agent must read the file directly as no documentation exists yet."

        return "[UNCOMMITTED CHANGES] -> The documentation represents 'What Was' before current working tree edits. Read the file directly to see 'What Is'."

    except Exception as e:
        logger.error(f"Error checking working tree for {filepath}: {e}")
        return "[UNKNOWN]"

def check_branch_state(repo_root: Path, filepath: Path) -> str:
    """Check if the file has been modified in the current branch relative to main/master."""
    try:
        rel_path = filepath.relative_to(repo_root)

        # Try main first, then master
        for branch in ["main", "master"]:
            try:
                # Get the merge base to compare branch changes
                base_cmd = ["git", "merge-base", "HEAD", branch]
                base_result = subprocess.run(base_cmd, cwd=repo_root, capture_output=True, text=True, check=True)
                merge_base = base_result.stdout.strip()

                diff_cmd = ["git", "diff", f"{merge_base}...HEAD", "--name-status", "--", str(rel_path)]
                diff_result = subprocess.run(diff_cmd, cwd=repo_root, capture_output=True, text=True, check=True)

                status = diff_result.stdout.strip()
                if not status:
                    return "[SYNCED]"

                return "[MODIFIED FROM MAIN] -> This symbol is actively being refactored in this branch."
            except subprocess.CalledProcessError:
                continue # Try master if main fails

        return "[UNKNOWN BASE BRANCH]"
    except Exception as e:
        logger.error(f"Error checking branch state for {filepath}: {e}")
        return "[UNKNOWN]"

def get_file_timeline(filepath_str: str, is_indexed: bool = True) -> str:
    """
    Generate a formatted Symbol Timeline block for an AI agent.
    """
    filepath = Path(filepath_str).resolve()
    repo_root = get_git_root(filepath)

    if not repo_root:
        return f"[STATUS: ERROR] File {filepath} is not in a git repository."

    doc_state = "Reflects HEAD commit ('What Was')." if is_indexed else "[NOT INDEXED]"
    working_tree_state = check_working_tree(repo_root, filepath)
    branch_state = check_branch_state(repo_root, filepath)

    # Try to provide a relative path for cleaner output
    try:
        display_path = str(filepath.relative_to(repo_root))
    except ValueError:
        display_path = filepath.name

    timeline = f"""
[SYMBOL TIMELINE: {display_path}]
- Documentation State: {doc_state}
- Working Tree State: {working_tree_state}
- Branch State: {branch_state}
"""
    return timeline.strip()
