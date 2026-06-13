import pytest
import os
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from doxygen_mcp.search import DoxygenSearchIndex

def test_search_index_batching(tmp_path):
    test_dir = tmp_path / "test_search"
    test_dir.mkdir()
    (test_dir / ".git").mkdir()

    index_xml_path = test_dir / "index.xml"
    root = ET.Element("doxygenindex")
    for i in range(10):
        refid = f"compound_{i}"
        compound = ET.SubElement(root, "compound", refid=refid, kind="class")
        name = ET.SubElement(compound, "name")
        name.text = f"Class{i}"

        detailed_xml_path = test_dir / f"{refid}.xml"
        d_root = ET.Element("doxygen")
        cdef = ET.SubElement(d_root, "compounddef")
        brief = ET.SubElement(cdef, "briefdescription")
        brief.text = f"Brief {i}"
        detailed = ET.SubElement(cdef, "detaileddescription")
        detailed.text = f"Detailed {i}"
        loc = ET.SubElement(cdef, "location", file=f"src/class{i}.cpp")

        tree = ET.ElementTree(d_root)
        tree.write(detailed_xml_path)

    tree = ET.ElementTree(root)
    tree.write(index_xml_path)

    idx = DoxygenSearchIndex(str(test_dir))
    idx._build_index()

    conn = idx.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM symbols WHERE kind='class'")
    count = cursor.fetchone()[0]
    assert count == 10
