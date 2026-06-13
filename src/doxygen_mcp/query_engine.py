"""
Doxygen XML Query Engine.

This module parses Doxygen XML output and provides an API for querying
symbols, structures, and documentation.
"""

import ast
import asyncio
import logging
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

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
        self._files: List[Tuple[str, Dict[str, Any]]] = (
            []
        )  # list of (name, info) for kind="file"
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
                "base_classes": [
                    p.text for p in compounddef.findall("basecompoundref")
                ],
                "derived_classes": [
                    p.text for p in compounddef.findall("derivedcompoundref")
                ],
                "members": [],
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
            "references": [
                ref.text for ref in member.findall("references") if ref.text
            ],
            "referencedby": [
                ref.text for ref in member.findall("referencedby") if ref.text
            ],
        }

        if mem_info["references"] or mem_info["referencedby"]:
            connections["members"].append(mem_info)

    def get_file_structure(self, file_path: str) -> List[Dict[str, Any]]:
        """Identify all symbols defined in a specific file"""
        file_name = Path(file_path).name

        # 1. Find the file compound
        refid = None
        candidates = self._file_map.get(file_name)
        if candidates:
            refid = candidates[0]["refid"]
        else:
            for name, info in self._files:
                if name.endswith(file_name):
                    refid = info["refid"]
                    break

        if not refid:
            return []

        # 2. Parse the file XML to find inner classes and namespaces
        xml_file = (self.xml_dir / f"{refid}.xml").resolve()
        if not xml_file.exists():
            return []

        members = []
        try:
            tree = ET.parse(xml_file)
            xml_root = tree.getroot()
            compounddef = xml_root.find("compounddef")
            if compounddef is not None:
                # Get direct members (like namespace-level functions/variables)
                for section in compounddef.findall("sectiondef"):
                    for member in section.findall("memberdef"):
                        m_wrapper = {"members": []}
                        self._process_member_details(member, m_wrapper)
                        if m_wrapper["members"]:
                            m = m_wrapper["members"][0]
                            m["full_name"] = m["name"]
                            m["is_class_member"] = False
                            members.append(m)

                # Get members of inner classes defined in this file
                for innerclass in compounddef.findall("innerclass"):
                    class_refid = innerclass.get("refid")
                    if class_refid:
                        class_details = self._fetch_compound_details(class_refid)
                        if class_details and "members" in class_details:
                            # Add the class itself as a symbol
                            members.append(
                                {
                                    "name": class_details["name"],
                                    "full_name": class_details["name"],
                                    "kind": class_details["kind"],
                                    "type": "",
                                    "args": "",
                                    "location": class_details.get("location") or {},
                                    "brief": class_details.get("brief") or "",
                                    "is_class_member": False,
                                }
                            )
                            # Add class members
                            for m in class_details["members"]:
                                m["full_name"] = f"{class_details['name']}::{m['name']}"
                                m["is_class_member"] = True
                                members.append(m)

                # Get members of inner namespaces defined in this file
                for innernamespace in compounddef.findall("innernamespace"):
                    ns_refid = innernamespace.get("refid")
                    if ns_refid:
                        ns_details = self._fetch_compound_details(ns_refid)
                        if ns_details and "members" in ns_details:
                            for m in ns_details["members"]:
                                loc = m.get("location") or {}
                                m_file = loc.get("file", "")
                                if m_file and Path(m_file).name == file_name:
                                    m["full_name"] = (
                                        f"{ns_details['name']}::{m['name']}"
                                    )
                                    m["is_class_member"] = False
                                    members.append(m)

        except Exception as e:
            logger.error("Error parsing file structure for %s: %s", file_path, e)

        # Deduplicate members by name, kind, file, and line
        seen = set()
        deduped = []
        for m in members:
            loc = m.get("location") or {}
            key = (m["name"], m["kind"], loc.get("file"), loc.get("line"))
            if key not in seen:
                seen.add(key)
                deduped.append(m)

        return deduped

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
                    m_id = member.get("id")
                    if m_id:
                        self._member_parent_map[m_id] = refid

            return details
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"error": f"Error parsing {xml_file}: {e}"}

    def _process_member_details(self, member, details):
        """Helper to process member details."""
        m_name_elem = member.find("name")
        m_name = m_name_elem.text if m_name_elem is not None else ""
        details["members"].append(
            {
                "refid": member.get("id"),
                "name": m_name,
                "kind": member.get("kind"),
                "type": self._get_text_recursive(member.find("type")),
                "args": self._get_text_recursive(member.find("argsstring")),
                "location": self._get_location(member),
                "brief": self._get_text_recursive(member.find("briefdescription")),
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
                "bodystart": loc.get("bodystart"),
                "bodyend": loc.get("bodyend"),
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
            results.append(
                {
                    "name": comp_details["name"],
                    "kind": comp_details["kind"],
                    "refid": comp_details.get("refid") or symbol_name,
                    "location": comp_details.get("location") or {},
                    "is_member": False,
                    "parent_refid": None,
                }
            )

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
                        results.append(
                            {
                                "name": member["name"],
                                "kind": member["kind"],
                                "refid": member.get("refid")
                                or member.get("location", {}).get("file", "")
                                + ":"
                                + str(member.get("location", {}).get("line", "")),
                                "location": member.get("location") or {},
                                "is_member": True,
                                "parent_refid": info["refid"],
                                "parent_name": name,
                            }
                        )

        return results

    def find_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all call sites / occurrences of a symbol in the workspace."""
        results: List[Dict[str, Any]] = []

        definitions = self.find_symbol_definitions(symbol_name)
        if not definitions:
            return []

        for def_info in definitions:
            if def_info.get("is_member"):
                referenced_by_list = self._get_member_referenced_by(def_info)
                for ref in referenced_by_list:
                    results.extend(self._process_reference_call_site(ref, def_info))
            else:
                results.extend(self._get_compound_derived_classes(def_info))

        return results

    def _get_member_referenced_by(
        self, def_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract the referencedby list for a member definition."""
        parent_details = self._fetch_compound_details(def_info.get("parent_refid", ""))
        if not parent_details or "members" not in parent_details:
            return []

        for member in parent_details["members"]:
            if member["name"] == def_info["name"] and member.get("referencedby"):
                return member["referencedby"]

        return []

    def _get_compound_derived_classes(
        self, def_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find derived classes for compound definitions and construct results."""
        results = []
        connections = self.get_symbol_connections(def_info["name"])

        if not connections or not connections.get("derived_classes"):
            return results

        for derived in connections["derived_classes"]:
            derived_details = self.query_symbol(derived)
            if not derived_details or not derived_details.get("location"):
                continue

            loc = derived_details["location"]
            file_path_str = loc.get("file")
            if not file_path_str:
                continue

            abs_path = (self.search_index.repo_root / file_path_str).resolve()
            results.append(
                {
                    "file": str(abs_path),
                    "line": int(loc.get("line") or 1),
                    "content": f"class {derived} inherits from {def_info['name']}",
                    "caller": derived,
                }
            )

        return results

    def _resolve_reference_file_path(self, ref: Dict[str, Any]) -> Optional[Path]:
        """Resolve the absolute file path for a reference."""
        file_path_str = None
        ref_refid = ref.get("refid")

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
            return None

        # Resolve to absolute path in repository
        abs_path = (self.search_index.repo_root / file_path_str).resolve()
        if abs_path.exists():
            return abs_path

        abs_path = (self.xml_dir.parent / file_path_str).resolve()
        if abs_path.exists():
            return abs_path

        found_files = list(self.search_index.repo_root.rglob(Path(file_path_str).name))
        if found_files:
            return found_files[0]

        return None

    def _process_reference_call_site(
        self, ref: Dict[str, Any], def_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse the exact call site from the resolved file path."""
        abs_path = self._resolve_reference_file_path(ref)
        if not abs_path:
            return []

        start_line = int(ref.get("startline") or 1)
        end_line = int(ref.get("endline") or start_line)

        # Scan lines for exact call site
        short_name = def_info["name"].split("::")[-1].split(".")[-1]
        word_pattern = re.compile(r"\b" + re.escape(short_name) + r"\b")

        found_lines = []
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            scan_start = max(0, start_line - 1)
            scan_end = min(len(lines), end_line)

            for idx in range(scan_start, scan_end):
                line_content = lines[idx]
                if word_pattern.search(line_content):
                    found_lines.append(
                        {
                            "file": str(abs_path),
                            "line": idx + 1,
                            "content": line_content.strip(),
                            "caller": ref.get("name"),
                        }
                    )
        except Exception:
            pass

        if found_lines:
            return found_lines

        return [
            {
                "file": str(abs_path),
                "line": start_line,
                "content": f"[Caller block start] {ref.get('name')}",
                "caller": ref.get("name"),
            }
        ]

    def get_file_skeleton(self, file_path: str) -> str:
        """Generate a skeletal version of the source file (signatures only, bodies stripped)."""
        file_name = Path(file_path).name

        abs_path = (self.search_index.repo_root / file_path).resolve()
        if not abs_path.exists():
            abs_path = (self.xml_dir.parent / file_path).resolve()
            if not abs_path.exists():
                found_files = list(self.search_index.repo_root.rglob(file_name))
                if found_files:
                    abs_path = found_files[0]
                else:
                    return f"❌ Error: File '{file_path}' not found in workspace."

        members = self.get_file_structure(file_path)
        if not members:
            try:
                return abs_path.read_text(encoding="utf-8")
            except Exception as e:
                return f"❌ Error reading file: {e}"

        try:
            content = abs_path.read_text(encoding="utf-8")
            lines = content.splitlines()
        except Exception as e:
            return f"❌ Error reading file: {e}"

        ext = abs_path.suffix.lower()
        is_python = ext == ".py"

        ranges = []
        for m in members:
            loc = m.get("location") or {}
            bodystart_str = loc.get("bodystart")
            bodyend_str = loc.get("bodyend")

            if bodystart_str and bodyend_str:
                try:
                    start = int(bodystart_str)
                    end = int(bodyend_str)
                    if start > 0 and end > start:
                        ranges.append((start, end))
                except ValueError:
                    continue

        if not ranges:
            return content

        unique_ranges = []
        seen = set()
        for r in sorted(ranges, key=lambda x: (x[0], -x[1])):
            if r[0] not in seen:
                unique_ranges.append(r)
                seen.add(r[0])

        unique_ranges.sort(key=lambda x: x[0], reverse=True)

        for start, end in unique_ranges:
            idx_start = start - 1
            idx_end = end - 1

            if idx_start >= len(lines) or idx_end >= len(lines):
                continue

            start_line = lines[idx_start]
            indent = start_line[: len(start_line) - len(start_line.lstrip())]

            if is_python:
                lines[idx_start + 1 : idx_end + 1] = [indent + "    pass"]
            else:
                if idx_end - idx_start > 1:
                    lines[idx_start + 1 : idx_end] = [indent + "    /* stub */"]
                else:
                    lines[idx_start + 1 : idx_end + 1] = [indent + "    /* stub */"]

        return "\n".join(lines)

    def get_source_snippet(self, file_path: str, bodystart: int, bodyend: int) -> str:
        abs_path = (self.search_index.repo_root / file_path).resolve()
        if not abs_path.exists():
            abs_path = (self.xml_dir.parent / file_path).resolve()
            if not abs_path.exists():
                return ""
        try:
            content = abs_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            start = max(0, bodystart - 1)
            end = min(len(lines), bodyend)
            return "\n".join(lines[start:end])
        except Exception:
            return ""

    def get_member_by_refid(self, refid: str) -> Optional[Dict[str, Any]]:
        parent_refid = self._member_parent_map.get(refid)
        if parent_refid:
            parent_details = self._fetch_compound_details(parent_refid)
            if parent_details and "members" in parent_details:
                for m in parent_details["members"]:
                    if m.get("refid") == refid:
                        if (
                            parent_details.get("name")
                            and parent_details.get("kind") != "file"
                        ):
                            m["full_name"] = f"{parent_details['name']}::{m['name']}"
                        else:
                            m["full_name"] = m["name"]
                        return m
        return None

    def trace_call_path(self, entry_symbol: str, max_depth: int = 3) -> str:
        defs = self.find_symbol_definitions(entry_symbol)
        if not defs:
            return f"❌ Error: Entry symbol '{entry_symbol}' not found."

        target = None
        for d in defs:
            if d.get("kind") in {"function", "slot", "signal"}:
                target = d
                break
        if not target:
            target = defs[0]

        visited = set()
        steps = []

        def trace(refid: str, depth: int):
            if depth > max_depth or refid in visited:
                return
            visited.add(refid)

            m = self.get_member_by_refid(refid)
            if not m:
                comp_details = self._fetch_compound_details(refid)
                if comp_details and "error" not in comp_details:
                    loc = comp_details.get("location") or {}
                    file_path = loc.get("file")
                    bodystart = int(loc.get("bodystart") or 0)
                    bodyend = int(loc.get("bodyend") or 0)
                    if file_path and bodystart > 0 and bodyend >= bodystart:
                        snippet = self.get_source_snippet(file_path, bodystart, bodyend)
                        if snippet:
                            steps.append(
                                {
                                    "name": comp_details["name"],
                                    "file": file_path,
                                    "start": bodystart,
                                    "end": bodyend,
                                    "code": snippet,
                                }
                            )
                return

            loc = m.get("location") or {}
            file_path = loc.get("file")
            bodystart_str = loc.get("bodystart")
            bodyend_str = loc.get("bodyend")

            if file_path and bodystart_str and bodyend_str:
                try:
                    bodystart = int(bodystart_str)
                    bodyend = int(bodyend_str)
                    if bodystart > 0 and bodyend >= bodystart:
                        snippet = self.get_source_snippet(file_path, bodystart, bodyend)
                        if snippet:
                            full_name = m.get("full_name") or m["name"]
                            steps.append(
                                {
                                    "name": full_name,
                                    "file": file_path,
                                    "start": bodystart,
                                    "end": bodyend,
                                    "code": snippet,
                                }
                            )
                except ValueError:
                    pass

            refs = m.get("references") or []
            for r in refs:
                callee_refid = r.get("refid")
                if callee_refid:
                    trace(callee_refid, depth + 1)

        entry_refid = target.get("refid")
        if entry_refid:
            if ":" in entry_refid:
                for parent_ref, parent_info in self.compounds.items():
                    p_details = self._fetch_compound_details(parent_info["refid"])
                    if p_details and "members" in p_details:
                        for m in p_details["members"]:
                            loc = m.get("location") or {}
                            loc_str = f"{loc.get('file')}:{loc.get('line')}"
                            if loc_str == entry_refid:
                                entry_refid = m.get("refid")
                                break
                        else:
                            continue
                        break

            if entry_refid:
                trace(entry_refid, 1)

        if not steps:
            return "No call path code could be traced."

        output = []
        for i, step in enumerate(steps, 1):
            role = "Caller" if i == 1 else "Callee"
            output.append(f"[STEP {i}] {role}: {step['name']}")
            output.append(f"Source: {step['file']}:{step['start']}-{step['end']}")
            ext = Path(step["file"]).suffix.lower()
            lang = "python" if ext == ".py" else "cpp"
            output.append(f"```{lang}\n{step['code']}\n```\n")

        return "\n".join(output)

    def get_virtual_diff(self, project_path: Optional[str] = None) -> Dict[str, Any]:
        """Track active working-tree edits and provide exact signature differences."""
        repo_root = self.search_index.repo_root
        if project_path:
            repo_root = Path(project_path).resolve()

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception as e:
            logger.error("Error running git status: %s", e)
            return {"error": f"Failed to query git status: {e}"}

        modified_files = []
        for line in res.stdout.splitlines():
            if len(line) > 3:
                file_path_str = line[3:].strip()
                if "->" in file_path_str:
                    file_path_str = file_path_str.split("->")[-1].strip()
                if file_path_str.startswith('"') and file_path_str.endswith('"'):
                    file_path_str = file_path_str[1:-1]

                ext = Path(file_path_str).suffix.lower()
                if ext in {".py", ".cpp", ".h", ".cc", ".c", ".hpp", ".cxx", ".hxx"}:
                    modified_files.append(file_path_str)

        results = []
        for rel_file in modified_files:
            abs_file = repo_root / rel_file
            if not abs_file.exists():
                continue

            disk_sigs = parse_signatures_from_source(abs_file)
            xml_symbols = self.get_file_structure(rel_file)

            added_signatures = []
            removed_signatures = []
            modified_signatures = []

            matched_xml_refids = set()

            for source_name, source_info in disk_sigs.items():
                xml_sym = find_matching_xml_symbol(
                    source_name, source_info["kind"], xml_symbols
                )
                if xml_sym:
                    matched_xml_refids.add(xml_sym.get("refid") or xml_sym["name"])
                    source_params = extract_param_names(source_info["args"])
                    xml_params = extract_param_names(xml_sym.get("args") or "")
                    if source_params != xml_params:
                        old_sig = f"{xml_sym['name']}{xml_sym.get('args') or ''}"
                        modified_signatures.append(
                            {"old": old_sig, "new": source_info["signature"]}
                        )
                else:
                    added_signatures.append(source_info["signature"])

            for xml_sym in xml_symbols:
                ref_key = xml_sym.get("refid") or xml_sym["name"]
                if ref_key not in matched_xml_refids:
                    if xml_sym["kind"] in {
                        "class",
                        "struct",
                        "function",
                        "slot",
                        "signal",
                    }:
                        old_sig = f"{xml_sym['name']}{xml_sym.get('args') or ''}"
                        removed_signatures.append(old_sig)

            if added_signatures or removed_signatures or modified_signatures:
                results.append(
                    {
                        "file": rel_file,
                        "added_signatures": added_signatures,
                        "removed_signatures": removed_signatures,
                        "modified_signatures": modified_signatures,
                    }
                )

        return {"modified_files": results}


# Helper functions for virtual diff and parsing


def normalize_symbol_name(name: str) -> str:
    return name.replace("::", ".").strip().lower()


def extract_param_names(args_str: str) -> List[str]:
    s = args_str.strip()
    if s.startswith("("):
        s = s[1:]
    if s.endswith(")"):
        s = s[:-1]
    if not s:
        return []

    parts = []
    level = 0
    current = []
    for char in s:
        if char in "([":
            level += 1
        elif char in ")]":
            level -= 1
        elif char == "," and level == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())

    param_names = []
    for part in parts:
        if not part:
            continue
        part = part.split("=")[0].strip()
        if ":" in part:
            name = part.split(":")[0].strip()
        else:
            words = part.split()
            if words:
                name = words[-1].strip()
            else:
                name = ""
        if name:
            param_names.append(name.strip("*&"))
    return param_names


def parse_python_signatures_from_source(content: str) -> Dict[str, Dict[str, Any]]:
    try:
        root = ast.parse(content)
    except Exception:
        return {}

    signatures = {}

    class SignatureVisitor(ast.NodeVisitor):
        def __init__(self):
            self.context = []

        def visit_ClassDef(self, node):
            class_name = node.name
            qualified_name = ".".join(self.context + [class_name])

            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    parts = []
                    curr = base
                    while isinstance(curr, ast.Attribute):
                        parts.append(curr.attr)
                        curr = curr.value
                    if isinstance(curr, ast.Name):
                        parts.append(curr.id)
                    bases.append(".".join(reversed(parts)))

            bases_str = f"({', '.join(bases)})" if bases else ""
            signatures[qualified_name] = {
                "name": class_name,
                "kind": "class",
                "signature": f"class {class_name}{bases_str}",
                "args": bases_str,
            }

            self.context.append(class_name)
            self.generic_visit(node)
            self.context.pop()

        def visit_FunctionDef(self, node):
            self._visit_func(node)

        def visit_AsyncFunctionDef(self, node):
            self._visit_func(node)

        def _visit_func(self, node):
            func_name = node.name
            qualified_name = ".".join(self.context + [func_name])

            try:
                args_str = f"({ast.unparse(node.args)})"
            except Exception:
                args_str = "(*args, **kwargs)"

            ret_str = ""
            if node.returns:
                try:
                    ret_str = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass

            is_async = isinstance(node, ast.AsyncFunctionDef)
            prefix = "async def" if is_async else "def"
            signatures[qualified_name] = {
                "name": func_name,
                "kind": "function",
                "signature": f"{prefix} {func_name}{args_str}{ret_str}",
                "args": args_str,
            }

            self.context.append(func_name)
            self.generic_visit(node)
            self.context.pop()

    SignatureVisitor().visit(root)
    return signatures


def parse_cpp_signatures_from_source(content: str) -> Dict[str, Dict[str, Any]]:
    signatures = {}

    content_clean = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content_clean = re.sub(r"//.*", "", content_clean)

    class_pattern = re.compile(r"\b(class|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b")
    for match in class_pattern.finditer(content_clean):
        kind = match.group(1)
        name = match.group(2)
        signatures[name] = {
            "name": name,
            "kind": "class",
            "signature": f"{kind} {name}",
            "args": "",
        }

    func_pattern = re.compile(
        r"\b([a-zA-Z_][a-zA-Z0-9_<>\s::]*)\s+([a-zA-Z_][a-zA-Z0-9_]*::)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(const)?\s*[{;]?"
    )
    for match in func_pattern.finditer(content_clean):
        ret_type = match.group(1).strip()
        scope = match.group(2) or ""
        name = match.group(3)
        args = f"({match.group(4).strip()})"

        if name in {
            "if",
            "for",
            "while",
            "switch",
            "catch",
            "return",
            "using",
            "template",
        }:
            continue

        full_name = f"{scope}{name}"
        signatures[full_name] = {
            "name": name,
            "kind": "function",
            "signature": f"{ret_type} {full_name}{args}",
            "args": args,
        }

    return signatures


def parse_signatures_from_source(file_path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    ext = file_path.suffix.lower()
    if ext == ".py":
        return parse_python_signatures_from_source(content)
    elif ext in {".cpp", ".h", ".cc", ".c", ".hpp", ".cxx", ".hxx"}:
        return parse_cpp_signatures_from_source(content)
    else:
        return {}


def find_matching_xml_symbol(
    source_name: str, source_kind: str, xml_symbols: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    src_parts = source_name.lower().replace("::", ".").split(".")
    is_method = source_kind == "function" and len(src_parts) > 1

    for xml_sym in xml_symbols:
        xml_name = xml_sym.get("full_name") or xml_sym["name"]
        xml_parts = xml_name.lower().replace("::", ".").split(".")

        if source_kind == "class" and xml_sym["kind"] not in {"class", "struct"}:
            continue
        if source_kind == "function" and xml_sym["kind"] not in {
            "function",
            "slot",
            "signal",
        }:
            continue

        is_xml_method = xml_sym.get("is_class_member", False)
        if is_method != is_xml_method:
            continue

        if len(xml_parts) >= len(src_parts):
            if xml_parts[-len(src_parts) :] == src_parts:
                return xml_sym
    return None
