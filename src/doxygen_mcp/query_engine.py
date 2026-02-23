"""
Query engine for Doxygen XML output.
"""

# pylint: disable=import-error,broad-exception-caught,unused-import,too-many-nested-blocks,unused-variable

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, ClassVar
from functools import lru_cache

import defusedxml.ElementTree as ET

class DoxygenQueryEngine:
    """Engine to query Doxygen XML output for symbol documentation."""
    _cache: ClassVar[Dict[str, "DoxygenQueryEngine"]] = {}

    def __init__(self, xml_dir: str):
        """Initialize the engine with the XML directory."""
        # Resolve path once during initialization to avoid repeated syscalls
        self.xml_dir = Path(xml_dir).resolve()
        self.index_path = self.xml_dir / "index.xml"
        self.compounds = {}
        self._lower_map = {}
        self._file_map = {}
        self._files = []

    @classmethod
    async def create(cls, xml_dir: str) -> "DoxygenQueryEngine":
        """Factory method to create and load an engine instance."""
        if xml_dir in cls._cache:
            return cls._cache[xml_dir]

        engine = cls(xml_dir)
        # Offload XML parsing to a thread pool
        await asyncio.to_thread(engine._load_index)
        cls._cache[xml_dir] = engine
        return engine

    @classmethod
    def clear_cache(cls, xml_dir: Optional[str] = None):
        """Clear the engine cache."""
        if xml_dir:
            if xml_dir in cls._cache:
                del cls._cache[xml_dir]
        else:
            cls._cache.clear()

    def _load_index(self):
        """Load the Doxygen index.xml file."""
        if not self.index_path.exists():
            return

        try:
            # Using iterparse to stream XML and minimize memory footprint
            for _, elem in ET.iterparse(str(self.index_path), events=('end',)):
                if elem.tag == 'compound':
                    kind = elem.get('kind')
                    refid = elem.get('refid')
                    name_elem = elem.find('name')

                    if name_elem is not None and name_elem.text:
                        name = name_elem.text
                        data = {
                            "name": name,
                            "kind": kind,
                            "refid": refid,
                            "members": {}
                        }

                        # Index by original name for exact match
                        self.compounds[name] = data
                        # Index by lowercase for case-insensitive match
                        self._lower_map[name.lower()] = name

                        # Specialized indexing for files (use basename for fast lookup)
                        if kind == 'file':
                            self._file_map[Path(name).name] = name
                            self._files.append(data)

                        # Process members (functions, variables, etc.)
                        for member in elem.findall('member'):
                            m_name_elem = member.find('name')
                            if m_name_elem is not None and m_name_elem.text:
                                m_name = m_name_elem.text
                                m_refid = member.get('refid')
                                m_kind = member.get('kind')
                                m_data = {
                                    "name": m_name,
                                    "kind": m_kind,
                                    "refid": m_refid,
                                    "parent_refid": refid
                                }
                                data["members"][m_name] = m_data
                                # Members are also searchable globally
                                if m_name not in self.compounds:
                                    self.compounds[m_name] = m_data
                                    self._lower_map[m_name.lower()] = m_name

                    elem.clear()  # Free memory
        except Exception:
            pass

    def query_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Query documentation for a specific symbol."""
        # 1. Exact match (case-sensitive)
        if symbol_name in self.compounds:
            return self._fetch_details(self.compounds[symbol_name])

        # 2. Exact match (case-insensitive)
        lower_name = symbol_name.lower()
        if lower_name in self._lower_map:
            return self._fetch_details(self.compounds[self._lower_map[lower_name]])

        # 3. Partial match (starts with or ends with)
        for name_lower, original_name in self._lower_map.items():
            if lower_name in name_lower:
                return self._fetch_details(self.compounds[original_name])

        return None

    def list_all_symbols(self, kind_filter: Optional[str] = None) -> List[Dict[str, str]]:
        """List all symbols, optionally filtered by kind."""
        results = []
        for name, data in self.compounds.items():
            if not kind_filter or data['kind'] == kind_filter:
                results.append({
                    "name": name,
                    "kind": data['kind']
                })
        return sorted(results, key=lambda x: x['name'])

    def get_file_structure(self, file_path: str) -> List[Dict[str, Any]]:
        """Retrieve the structure (symbols) of a specific file."""
        basename = Path(file_path).name

        # 1. Try exact basename match (O(1) lookup)
        # This covers the common case where the user provides the correct filename
        # (e.g. "test_file.h")
        if basename in self._file_map:
            file_name = self._file_map[basename]
            return self._fetch_details(self.compounds[file_name]).get("members", [])

        # 2. Fallback to suffix match (O(N) scan over files only, not all symbols)
        # Handle cases like "src/utils/file.h" matching "utils/file.h" in Doxygen
        for file_data in self._files:
            if file_data['name'].endswith(basename):
                return self._fetch_details(file_data).get("members", [])

        return []

    def _fetch_details(self, compound_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch detailed documentation from a compound's XML file."""
        refid = compound_data.get("refid")
        if not refid:
            return compound_data

        details = self._fetch_compound_details(refid)
        # Merge details into compound data
        result = compound_data.copy()
        result.update(details)
        return result

    @lru_cache(maxsize=128)
    def _fetch_compound_details(self, refid: str) -> Dict[str, Any]:
        """Load and parse a detailed compound XML file."""
        # Sanitize refid for security (prevent directory traversal)
        safe_refid = Path(refid).name
        detail_path = self.xml_dir / f"{safe_refid}.xml"

        if not detail_path.exists():
            return {}

        try:
            tree = ET.parse(str(detail_path))
            root = tree.getroot()
            compound = root.find('compounddef')

            if compound is None:
                return {}

            brief = compound.find('briefdescription')
            detailed = compound.find('detaileddescription')

            # Extract members if this is a container (class, file, namespace)
            members = []
            for section in compound.findall('sectiondef'):
                for member in section.findall('memberdef'):
                    m_data = {
                        "name": self._get_text(member.find('name')),
                        "kind": member.get('kind'),
                        "definition": self._get_text(member.find('definition')),
                        "argsstring": self._get_text(member.find('argsstring')),
                        "brief": self._get_text_recursive(member.find('briefdescription')),
                        "detailed": self._get_text_recursive(member.find('detaileddescription')),
                        "location": self._get_location(member.find('location'))
                    }
                    members.append(m_data)

            return {
                "brief": self._get_text_recursive(brief),
                "detailed": self._get_text_recursive(detailed),
                "members": members,
                "location": self._get_location(compound.find('location'))
            }
        except Exception:
            return {}

    def _get_text(self, element) -> str:
        """Extract text from an element."""
        if element is None: return ""
        return "".join(element.itertext()).strip()

    def _get_text_recursive(self, element) -> str:
        """Recursively extract text from an element, preserving some structure."""
        if element is None:
            return ""

        parts = []
        for text in element.itertext():
            parts.append(text)

        return "".join(parts).strip()

    def _get_location(self, element) -> Dict[str, str]:
        """Extract location information from an element."""
        if element is None:
            return {}
        return {
            "file": element.get("file"),
            "line": element.get("line"),
            "column": element.get("column")
        }
