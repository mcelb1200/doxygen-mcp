import asyncio
import os
import defusedxml.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any, ClassVar
from functools import lru_cache

class DoxygenQueryEngine:
    _cache: ClassVar[Dict[str, "DoxygenQueryEngine"]] = {}

    def __init__(self, xml_dir: str):
        self.xml_dir = Path(xml_dir)
        self.index_path = self.xml_dir / "index.xml"
        self.compounds = {}
        self.file_index = {} # Map files to symbols

    @classmethod
    async def create(cls, xml_dir: str) -> "DoxygenQueryEngine":
        xml_path = str(Path(xml_dir).absolute())
        if xml_path in cls._cache:
            return cls._cache[xml_path]

        self = cls(xml_dir)
        await asyncio.to_thread(self._load_index)
        cls._cache[xml_path] = self
        return self

    @classmethod
    def clear_cache(cls, xml_dir: Optional[str] = None):
        if xml_dir:
            xml_path = str(Path(xml_dir).absolute())
            if xml_path in cls._cache:
                del cls._cache[xml_path]
        else:
            cls._cache.clear()

    def _load_index(self):
        if not self.index_path.exists():
            return

        try:
            tree = ET.parse(self.index_path)
            root = tree.getroot()
            for compound in root.findall("compound"):
                name = compound.find("name").text
                kind = compound.get("kind")
                refid = compound.get("refid")
                self.compounds[name] = {
                    "kind": kind,
                    "refid": refid,
                }
        except Exception as e:
            print(f"Error loading index: {e}")

    def query_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Query a class or namespace by name"""
        # Exact match first
        if symbol_name in self.compounds:
            return self._fetch_compound_details(self.compounds[symbol_name]["refid"])

        # Partial match
        for name, info in self.compounds.items():
            if symbol_name.lower() in name.lower():
                return self._fetch_compound_details(info["refid"])

        return None

    def get_file_structure(self, file_path: str) -> List[Dict[str, Any]]:
        """Identify all symbols defined in a specific file"""
        # In Doxygen XML, files are also compounds
        file_name = Path(file_path).name
        for name, info in self.compounds.items():
            if info["kind"] == "file" and (name == file_name or name.endswith(file_name)):
                details = self._fetch_compound_details(info["refid"])
                return details.get("members", [])
        return []

    @lru_cache(maxsize=128)
    def _fetch_compound_details(self, refid: str) -> Dict[str, Any]:
        xml_file = self.xml_dir / f"{refid}.xml"
        if not xml_file.exists():
            return {"error": f"Details file {xml_file} not found"}

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            compounddef = root.find("compounddef")

            details = {
                "name": compounddef.find("compoundname").text,
                "kind": compounddef.get("kind"),
                "location": self._get_location(compounddef),
                "brief": self._get_text_recursive(compounddef.find("briefdescription")),
                "detailed": self._get_text_recursive(compounddef.find("detaileddescription")),
                "members": []
            }

            for section in compounddef.findall("sectiondef"):
                for member in section.findall("memberdef"):
                    details["members"].append({
                        "name": member.find("name").text,
                        "kind": member.get("kind"),
                        "type": self._get_text_recursive(member.find("type")),
                        "args": self._get_text_recursive(member.find("argsstring")),
                        "location": self._get_location(member),
                        "brief": self._get_text_recursive(member.find("briefdescription")),
                    })

            return details
        except Exception as e:
            return {"error": f"Error parsing {xml_file}: {e}"}

    def _get_location(self, element) -> Dict[str, Any]:
        loc = element.find("location")
        if loc is not None:
            return {
                "file": loc.get("file"),
                "line": loc.get("line"),
                "column": loc.get("column")
            }
        return {}

    def _get_text_recursive(self, element) -> str:
        if element is None:
            return ""
        parts = [element.text or ""]
        for child in element:
            parts.append(self._get_text_recursive(child))
            parts.append(child.tail or "")
        return "".join(parts).strip()

    def list_all_symbols(self, kind_filter: Optional[str] = None) -> List[str]:
        if kind_filter:
            return [name for name, info in self.compounds.items() if info["kind"] == kind_filter]
        return list(self.compounds.keys())
