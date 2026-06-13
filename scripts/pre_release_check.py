#!/usr/bin/env python3
"""
Pre-release quality gates check script.
Executes pylint, mypy, pytest (with coverage), black, and isort.
Enforces:
- pylint score > 9.0
- mypy typing errors = 0
- pytest passes and coverage > 70%
- black formatting is valid
- isort import sorting is valid
"""
import sys
import subprocess
import re
from pathlib import Path

def run_command(args, check=False, text=True, capture_output=True):
    """Run a subprocess command and return completed process."""
    try:
        return subprocess.run(args, check=check, text=text, capture_output=capture_output)
    except FileNotFoundError:
        print(f"Error: Command not found: {args[0]}")
        sys.exit(1)

def main():
    project_root = Path(__file__).resolve().parent.parent
    bin_dir = Path(sys.executable).parent
    
    pylint_bin = str(bin_dir / "pylint")
    mypy_bin = str(bin_dir / "mypy")
    pytest_bin = str(bin_dir / "pytest")
    black_bin = str(bin_dir / "black")
    isort_bin = str(bin_dir / "isort")
    
    src_dir = str(project_root / "src" / "doxygen_mcp")
    tests_dir = str(project_root / "tests")
    
    failed = False
    
    # 1. Black Check
    print("--- Running Black Check ---")
    black_res = run_command([black_bin, "--check", "--fast", src_dir])
    if black_res.returncode != 0:
        print("❌ Black formatting check failed.")
        print(black_res.stderr or black_res.stdout)
        failed = True
    else:
        print("✅ Black formatting check passed.")
        
    # 2. Isort Check
    print("\n--- Running Isort Check ---")
    isort_res = run_command([isort_bin, "--check", src_dir])
    if isort_res.returncode != 0:
        print("❌ Isort import ordering check failed.")
        print(isort_res.stderr or isort_res.stdout)
        failed = True
    else:
        print("✅ Isort import ordering check passed.")
        
    # 3. Mypy Check
    print("\n--- Running Mypy Type Check ---")
    mypy_res = run_command([mypy_bin, src_dir])
    if mypy_res.returncode != 0:
        print("❌ Mypy typing check failed.")
        print(mypy_res.stdout or mypy_res.stderr)
        failed = True
    else:
        print("✅ Mypy typing check passed.")
        
    # 4. Pylint Check
    print("\n--- Running Pylint Check ---")
    pylint_res = run_command([pylint_bin, src_dir])
    # Extract score
    # Score format: "Your code has been rated at 9.54/10"
    score_match = re.search(r"rated at (-?\d+\.\d+)/10", pylint_res.stdout)
    if score_match:
        score = float(score_match.group(1))
        print(f"Pylint Score: {score}/10")
        if score <= 9.0:
            print("❌ Pylint score is <= 9.0.")
            failed = True
        else:
            print("✅ Pylint score is > 9.0.")
    else:
        print("❌ Failed to parse Pylint score.")
        print(pylint_res.stdout)
        failed = True

    # 5. Pytest Check (with Coverage)
    print("\n--- Running Pytest and Coverage Check ---")
    pytest_res = run_command([
        pytest_bin,
        "--cov=" + src_dir,
        "--cov-report=term-missing",
        tests_dir
    ])
    
    if pytest_res.returncode != 0:
        print("❌ Pytest execution failed.")
        print(pytest_res.stdout or pytest_res.stderr)
        failed = True
    else:
        print("✅ Pytest execution passed.")
        # Parse coverage percentage
        # Format usually: "TOTAL                              2424    704    71%"
        total_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", pytest_res.stdout)
        if total_match:
            coverage = int(total_match.group(1))
            print(f"Test Coverage: {coverage}%")
            if coverage <= 70:
                print("❌ Coverage is <= 70%.")
                failed = True
            else:
                print("✅ Coverage is > 70%.")
        else:
            print("❌ Failed to parse test coverage percentage.")
            print(pytest_res.stdout)
            failed = True

    if failed:
        print("\n❌ Pre-release checks FAILED.")
        sys.exit(1)
    else:
        print("\n✅ All pre-release checks PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    main()
