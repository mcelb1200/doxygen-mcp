import asyncio
import time
import os
import shutil
import tempfile
import glob
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

# Mock dependencies for doxygen_mcp.server
mock_defusedxml = MagicMock()
mock_defusedxml.ElementTree = ET
sys.modules["defusedxml"] = mock_defusedxml
sys.modules["defusedxml.ElementTree"] = ET

mock_mcp = MagicMock()
sys.modules["mcp"] = mock_mcp
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from doxygen_mcp.funnel import minify_xml_file
from doxygen_mcp.server import _minify_all_xml

def create_dummy_xml(filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class1" kind="class">
    <compoundname>Class1</compoundname>
    <collaborationgraph>Something</collaborationgraph>
    <briefdescription><para>Brief</para></briefdescription>
    <detaileddescription></detaileddescription>
    <inheritancegraph>Something</inheritancegraph>
    <listofallmembers><member>1</member></listofallmembers>
  </compounddef>
</doxygen>
""")

async def run_sequential(xml_files):
    for f in xml_files:
        await asyncio.to_thread(minify_xml_file, f)

async def benchmark():
    num_files = 100

    # We want to simulate some work to show the benefit of parallelism
    from doxygen_mcp import funnel
    original_minify = funnel.minify_xml_file

    def mock_minify(filepath):
        import time
        time.sleep(0.01)
        return original_minify(filepath)

    funnel.minify_xml_file = mock_minify

    with tempfile.TemporaryDirectory() as temp_dir:
        xml_dir = Path(temp_dir)
        for i in range(num_files):
            create_dummy_xml(xml_dir / f"test_{i}.xml")

        xml_files = glob.glob(os.path.join(xml_dir, "*.xml"))

        # Baseline: Sequential (simulating what it was before)
        start = time.perf_counter()
        await run_sequential(xml_files)
        duration_seq = time.perf_counter() - start
        print(f"Sequential (Baseline): {duration_seq:.4f}s")

        # Reset files
        for i in range(num_files):
            create_dummy_xml(xml_dir / f"test_{i}.xml")

        # Parallel via _minify_all_xml (The new implementation)
        start = time.perf_counter()
        await _minify_all_xml(str(xml_dir))
        duration_parallel = time.perf_counter() - start
        print(f"Parallel (_minify_all_xml): {duration_parallel:.4f}s")

        improvement = (duration_seq - duration_parallel) / duration_seq * 100
        print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    asyncio.run(benchmark())
