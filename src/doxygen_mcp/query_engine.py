"""
Doxygen XML Query Engine.

This module parses Doxygen XML output and provides an API for querying
symbols, structures, and documentation.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, ClassVar, Tuple
from functools import lru_cache
import defusedxml.ElementTree as ET
from .search import DoxygenSearchIndex

logger = logging.getLogger(__name__)


class DoxygenQueryEngine:
    """Engine for querying Doxygen XML documentation."""
    _cache: ClassVar[Dict[str, "DoxygenQueryEngine"]] = {}

    def __init__(self, xml_dir: str):
        """Initialize the query engine with an XML directory."""
        # Resolve path once during initialization to avoid repeated syscalls
        self.xml_dir = Path(xml_dir).resolve()
        self.index_path = self.xml_dir / "index.xml"

        self.search_index = DoxygenSearchIndex(str(self.xml_dir))

        self.compounds: Dict[str, Any] = {}
        # Optimization indices
        self._lower_map: Dict[str, Any] = {}  # lower_case_name -> info
        self._file_map: Dict[str, List[Dict[str, Any]]] = {}  # basename -> list of info
        self._files: List[Tuple[str, Dict[str, Any]]] = []  # list of (name, info) for kind="file"
        self._member_parent_map: Dict[str, str] = {}  # member refid -> compound refid

    @classmethod
    async def create(cls, xml_dir: str) -> "DoxygenQueryEngine":
        """Factory method to create or retrieve a cached engine instance."""
        xml_path = str(Path(xml_dir).absolute())
        if xml_path in cls._cache:
            return cls._cache[xml_path]

        self = cls(xml_dir)
        # pylint: disable=no-member
        await asyncio.to_thread(self._load_index)
        cls._cache[xml_path] = self
        return self

    @classmethod
    def clear_cache(cls, xml_dir: Optional[str] = None):
        """Clear the engine instance cache."""
        if xml_dir:
            xml_path = str(Path(xml_dir).absolute())
            if xml_path in cls._cache:
                del cls._cache[xml_path]
        else:
            cls._cache.clear()

    def _process_compound(self, elem):
        """Helper to process a single compound element from index.xml."""
        name_elem = elem.find("name")
        if name_elem is not None and name_elem.text:
            name = name_elem.text
            kind = elem.get("kind")
            refid = elem.get("refid")
            info = {
                "kind": kind,
                "refid": refid,
            }
            self.compounds[name] = info

            # Build optimization indices
            self._lower_map[name.lower()] = info

            if kind == "file":
                self._files.append((name, info))
                file_name = Path(name).name
                if file_name not in self._file_map:
                    self._file_map[file_name] = []
                self._file_map[file_name].append(info)

            # Map member refids to parent compound refid
            for member_elem in elem.findall("member"):
                member_refid = member_elem.get("refid")
                if member_refid:
                    self._member_parent_map[member_refid] = refid

    def _load_index(self):
        """Load and parse the Doxygen index.xml file."""
        if not self.index_path.exists():
            return

        self.search_index.initialize()

        try:
            # Use iterparse to handle large XML files with minimal memory usage
            context = ET.iterparse(self.index_path, events=("end",))

            for _, elem in context:
                if elem.tag == "compound":
                    self._process_compound(elem)
                    elem.clear()  # Only clear after processing

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error loading index: %s", e)

    def query_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Query a class or namespace by name"""
        # Exact match first
        if symbol_name in self.compounds:
            return self._fetch_compound_details(self.compounds[symbol_name]["refid"])

        # Case-insensitive exact match (O(1) optimization)
        lower_name = symbol_name.lower()
        if lower_name in self._lower_map:
            return self._fetch_compound_details(self._lower_map[lower_name]["refid"])

        # Partial match (fallback to O(N) scan)
        for name_lower, info in self._lower_map.items():
            if lower_name in name_lower:
                return self._fetch_compound_details(info["refid"])

        return None

    def get_symbol_connections(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve the call graph (references/referencedby) for a symbol."""
        refid = None
        if symbol_name in self.compounds:
            refid = self.compounds[symbol_name]["refid"]
        else:
            lower_name = symbol_name.lower()
            if lower_name in self._lower_map:
                refid = self._lower_map[lower_name]["refid"]
            else:
                for name_lower, info in self._lower_map.items():
                    if lower_name in name_lower:
                        refid = info["refid"]
                        break

        if not refid:
            return None

        return self._fetch_compound_connections(refid)

    @lru_cache(maxsize=128)
    def _fetch_compound_connections(self, refid: str) -> Dict[str, Any]:
        """Fetch connection metadata (references, referencedby, inheritance)."""
        try:
            xml_file = (self.xml_dir / f"{refid}.xml").resolve()
            xml_file.relative_to(self.xml_dir)
        except (ValueError, RuntimeError):
            return {"error": f"Security Error: Access denied to path '{refid}'"}

        if not xml_file.exists():
            return {"error": f"Details file {xml_file} not found"}

        try:
            tree = ET.parse(xml_file)
            xml_root = tree.getroot()
            compounddef = xml_root.find("compounddef")

            if compounddef is None:
                return {"error": "No compounddef found"}

            name_elem = compounddef.find("compoundname")
            name_text = name_elem.text if name_elem is not None else ""

            connections = {
                "name": name_text,
                "kind": compounddef.get("kind"),
                "base_classes": [p.text for p in compounddef.findall("basecompoundref")],
                "derived_classes": [p.text for p in compounddef.findall("derivedcompoundref")],
                "members": []
            }

            for section in compounddef.findall("sectiondef"):
                for member in section.findall("memberdef"):
                    self._process_member_connections(member, connections)

            return connections
        except Exception as e:
            return {"error": f"Error parsing {xml_file}: {e}"}

    def _process_member_connections(self, member, connections):
        """Helper to process member connections."""
        mem_name_elem = member.find("name")
        mem_name = mem_name_elem.text if mem_name_elem is not None else ""
        mem_info = {
            "name": mem_name,
            "kind": member.get("kind"),
            "references": [ref.text for ref in member.findall("references") if ref.text],
            "referencedby": [ref.text for ref in member.findall("referencedby") if ref.text]
        }

        if mem_info["references"] or mem_info["referencedby"]:
            connections["members"].append(mem_info)

    def get_file_structure(self, file_path: str) -> List[Dict[str, Any]]:
        """Identify all symbols defined in a specific file"""
        file_name = Path(file_path).name

        candidates = self._file_map.get(file_name)
        if candidates:
            details = self._fetch_compound_details(candidates[0]["refid"])
            return details.get("members", [])

        for name, info in self._files:
            if name.endswith(file_name):
                details = self._fetch_compound_details(info["refid"])
                return details.get("members", [])

        return []

    @lru_cache(maxsize=128)
    def _fetch_compound_details(self, refid: str) -> Dict[str, Any]:
        """Fetch and parse detailed information for a specific compound ID."""
        try:
            xml_file = (self.xml_dir / f"{refid}.xml").resolve()
            xml_file.relative_to(self.xml_dir)
        except (ValueError, RuntimeError):
            return {"error": f"Security Error: Access denied to path '{refid}'"}

        if not xml_file.exists():
            return {"error": f"Details file {xml_file} not found"}

        try:
            tree = ET.parse(xml_file)
            xml_root = tree.getroot()
            compounddef = xml_root.find("compounddef")

            if compounddef is None:
                return {"error": "No compounddef found"}

            name_elem = compounddef.find("compoundname")
            name_text = name_elem.text if name_elem is not None else ""

            details = {
                "name": name_text,
                "kind": compounddef.get("kind"),
                "location": self._get_location(compounddef),
                "brief": self._get_text_recursive(compounddef.find("briefdescription")),
                "detailed": self._get_text_recursive(
                    compounddef.find("detaileddescription")
                ),
                "members": [],
            }

            for section in compounddef.findall("sectiondef"):
                for member in section.findall("memberdef"):
                    self._process_member_details(member, details)

            return details
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"error": f"Error parsing {xml_file}: {e}"}

    def _process_member_details(self, member, details):
        """Helper to process member details."""
        m_name_elem = member.find("name")
        m_name = m_name_elem.text if m_name_elem is not None else ""
        details["members"].append(
            {
                "name": m_name,
                "kind": member.get("kind"),
                "type": self._get_text_recursive(member.find("type")),
                "args": self._get_text_recursive(member.find("argsstring")),
                "location": self._get_location(member),
                "brief": self._get_text_recursive(
                    member.find("briefdescription")
                ),
                "referencedby": [
                    {
                        "name": ref.text or "",
                        "refid": ref.get("refid"),
                        "compoundref": ref.get("compoundref"),
                        "startline": ref.get("startline"),
                        "endline": ref.get("endline"),
                    }
                    for ref in member.findall("referencedby")
                ],
                "references": [
                    {
                        "name": ref.text or "",
                        "refid": ref.get("refid"),
                        "compoundref": ref.get("compoundref"),
                        "startline": ref.get("startline"),
                        "endline": ref.get("endline"),
                    }
                    for ref in member.findall("references")
                ],
            }
        )

    def _get_location(self, element) -> Dict[str, Any]:
        """Extract location information from an XML element."""
        loc = element.find("location")
        if loc is not None:
            return {
                "file": loc.get("file"),
                "line": loc.get("line"),
                "column": loc.get("column"),
            }
        return {}

    def _get_text_recursive(self, element) -> str:
        """Recursively extract text from an XML element and its children."""
        if element is None:
            return ""
        return "".join(element.itertext()).strip()

    def list_all_symbols(self, kind_filter: Optional[str] = None) -> List[str]:
        """List all symbols, optionally filtered by kind (e.g., 'class', 'namespace')."""
        if kind_filter:
            return [
                name
                for name, info in self.compounds.items()
                if info["kind"] == kind_filter
            ]
        return list(self.compounds.keys())

    def semantic_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform a semantic search across the Doxygen FTS5 index."""
        return self.search_index.search(query, limit)

    def find_symbol_definitions(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Locate definitions of a symbol (compound or member)."""
        results = []
        
        # Check if it has class/namespace qualification
        parts = symbol_name.replace(".", "::").split("::")
        qualified = len(parts) > 1
        
        # 1. Check if matches a compound name
        comp_details = self.query_symbol(symbol_name)
        if comp_details and "error" not in comp_details:
            results.append({
                "name": comp_details["name"],
                "kind": comp_details["kind"],
                "refid": comp_details.get("refid") or symbol_name,
                "location": comp_details.get("location") or {},
                "is_member": False,
                "parent_refid": None
            })
            
        # 2. Check if matches a member name
        # Scan all compounds for matching members
        for name, info in self.compounds.items():
            # If qualified, the parent compound name must match the qualifier parts
            if qualified:
                parent_match = True
                for part in parts[:-1]:
                    if part.lower() not in name.lower():
                        parent_match = False
                        break
                if not parent_match:
                    continue
                member_target_name = parts[-1]
            else:
                member_target_name = symbol_name
                
            details = self._fetch_compound_details(info["refid"])
            if details and "members" in details:
                for member in details["members"]:
                    if member["name"].lower() == member_target_name.lower():
                        results.append({
                            "name": member["name"],
                            "kind": member["kind"],
                            "refid": member.get("location", {}).get("file", "") + ":" + str(member.get("location", {}).get("line", "")),
                            "location": member.get("location") or {},
                            "is_member": True,
                            "parent_refid": info["refid"],
                            "parent_name": name
                        })
                        
        return results

    def find_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all call sites / occurrences of a symbol in the workspace."""
        results = []
        
        # Resolve target symbol to member(s) or compound(s)
        definitions = self.find_symbol_definitions(symbol_name)
        if not definitions:
            return []
            
        for def_info in definitions:
            referenced_by_list = []
            
            if def_info["is_member"]:
                # Fetch details of parent compound to get all members
                parent_details = self._fetch_compound_details(def_info["parent_refid"])
                if parent_details and "members" in parent_details:
                    for member in parent_details["members"]:
                        if member["name"] == def_info["name"] and member.get("referencedby"):
                            referenced_by_list = member["referencedby"]
                            break
            else:
                # If it's a compound class, check for derived classes
                connections = self.get_symbol_connections(def_info["name"])
                if connections and connections.get("derived_classes"):
                    for derived in connections["derived_classes"]:
                        derived_details = self.query_symbol(derived)
                        if derived_details and derived_details.get("location"):
                            loc = derived_details["location"]
                            file_path_str = loc.get("file")
                            if file_path_str:
                                abs_path = (self.search_index.repo_root / file_path_str).resolve()
                                results.append({
                                    "file": str(abs_path),
                                    "line": int(loc.get("line") or 1),
                                    "content": f"class {derived} inherits from {def_info['name']}",
                                    "caller": derived
                                })
            
            # Process referenced_by_list
            for ref in referenced_by_list:
                ref_refid = ref.get("refid")
                file_path_str = None
                
                # 1. Look up parent compound of caller
                if ref_refid and ref_refid in self._member_parent_map:
                    caller_parent_refid = self._member_parent_map[ref_refid]
                    caller_parent_details = self._fetch_compound_details(caller_parent_refid)
                    if caller_parent_details and caller_parent_details.get("location"):
                        file_path_str = caller_parent_details["location"].get("file")
                
                # 2. Fall back to compoundref
                if not file_path_str:
                    file_path_str = ref.get("compoundref")
                    
                if not file_path_str:
                    continue
                    
                # Resolve to absolute path in repository
                abs_path = (self.search_index.repo_root / file_path_str).resolve()
                if not abs_path.exists():
                    abs_path = (self.xml_dir.parent / file_path_str).resolve()
                    if not abs_path.exists():
                        found_files = list(self.search_index.repo_root.rglob(Path(file_path_str).name))
                        if found_files:
                            abs_path = found_files[0]
                        else:
                            continue
                
                start_line = int(ref.get("startline") or 1)
                end_line = int(ref.get("endline") or start_line)
                
                # Scan lines for exact call site
                short_name = def_info["name"].split("::")[-1].split(".")[-1]
                word_pattern = re.compile(r'\b' + re.escape(short_name) + r'\b')
                
                found_lines = []
                try:
                    with open(abs_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    scan_start = max(0, start_line - 1)
                    scan_end = min(len(lines), end_line)
                    
                    for idx in range(scan_start, scan_end):
                        line_content = lines[idx]
                        if word_pattern.search(line_content):
                            found_lines.append({
                                "file": str(abs_path),
                                "line": idx + 1,
                                "content": line_content.strip(),
                                "caller": ref.get("name")
                            })
                except Exception:
                    pass
                
                if found_lines:
                    results.extend(found_lines)
                else:
                    results.append({
                        "file": str(abs_path),
                        "line": start_line,
                        "content": f"[Caller block start] {ref.get('name')}",
                        "caller": ref.get("name")
                    })
                    
        return results
