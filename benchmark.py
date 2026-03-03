import time
from pathlib import Path
import os
import sys
import tempfile
import shutil

# Add src to python path so we can import
sys.path.insert(0, str(Path(__file__).parent / "src"))

from doxygen_mcp.utils import find_project_root

with tempfile.TemporaryDirectory() as temp_dir:
    # Create a deeply nested path to force the worst-case scenario
    deep_path = Path(temp_dir) / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "h" / "i" / "j"
    os.makedirs(deep_path, exist_ok=True)

    # Run once to warm up cache if any
    find_project_root(deep_path)

    start = time.perf_counter()
    # Run many times
    for _ in range(10000):
        find_project_root(deep_path)
    end = time.perf_counter()

print(f"Optimized Time taken: {end - start:.4f} seconds")
