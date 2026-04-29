"""
Semantic Search Engine using SQLite FTS5 for Doxygen MCP.
Provides fast conceptual search across code and specifications.
"""
import sqlite3
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)

class DoxygenSearchIndex:
    """FTS5-based search index for Doxygen symbols and repository context."""
    def __init__(self, xml_dir: str):
        self.xml_dir = Path(xml_dir).resolve()
        self.index_xml = self.xml_dir / "index.xml"
        self.db_path = self.xml_dir / "search_index.db"

        # Determine repo root by going up until we find .git
        self.repo_root = self.xml_dir
        for p in [self.xml_dir] + list(self.xml_dir.parents):
            if (p / ".git").exists():
                self.repo_root = p
                break

    def get_connection(self):
        """Get an SQLite connection."""
        return sqlite3.connect(self.db_path)

    def initialize(self) -> bool:
        """Check if index needs rebuilding, and rebuild if necessary."""
        if not self.index_xml.exists():
            logger.warning("No index.xml found in %s", self.xml_dir)
            return False

        needs_rebuild = False
        if not self.db_path.exists():
            needs_rebuild = True
        else:
            db_mtime = self.db_path.stat().st_mtime
            idx_mtime = self.index_xml.stat().st_mtime
            if idx_mtime > db_mtime:
                needs_rebuild = True

        if needs_rebuild:
            self._build_index()

        return True

    def _parse_detailed_xml(self, refid: str):
        """Parse detailed XML for a compound to extract descriptions and filepath."""
        xml_file = self.xml_dir / f"{refid}.xml"
        brief = ""
        detailed = ""
        filepath = ""

        if not xml_file.exists():
            return brief, detailed, filepath

        try:
            ct_tree = ET.parse(xml_file)
            ct_root = ct_tree.getroot()
            if ct_root is not None:
                compounddef = ct_root.find("compounddef")
                if compounddef is not None:
                    brief = self._get_node_text(compounddef, "briefdescription")
                    detailed = self._get_node_text(compounddef, "detaileddescription")
                    loc = compounddef.find("location")
                    if loc is not None:
                        filepath = loc.get("file", "")
        except Exception as e:
            logger.warning("Failed to parse %s: %s", xml_file.name, e)

        return brief, detailed, filepath

    def _get_node_text(self, parent, tag):
        """Helper to extract text from a subnode."""
        node = parent.find(tag)
        if node is not None:
            return "".join(node.itertext()).strip()
        return ""

    def _build_index(self):
        """Parse XML and broader context to build the FTS5 index."""
        logger.info("Building SQLite FTS5 search index at %s", self.db_path)

        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except Exception as e:
                logger.error("Failed to delete old db: %s", e)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE VIRTUAL TABLE symbols USING fts5(
                name, kind, refid, brief, detailed, filepath
            )
        """)

        try:
            tree = ET.parse(self.index_xml)
            root = tree.getroot()

            if root is not None:
                for compound in root.findall("compound"):
                    self._process_compound_element(compound, cursor)
        except Exception as e:
            logger.error("Error parsing Doxygen XML for index: %s", e)

        self._ingest_broader_context(cursor)
        conn.commit()
        conn.close()
        logger.info("FTS5 index build complete.")

    def _process_compound_element(self, compound, cursor):
        """Helper to process a compound element and insert into DB."""
        refid = compound.get("refid", "")
        kind = compound.get("kind", "")
        name_elem = compound.find("name")
        name = name_elem.text if name_elem is not None else ""

        brief, detailed, filepath = self._parse_detailed_xml(refid)

        cursor.execute(
            "INSERT INTO symbols (name, kind, refid, brief, detailed, filepath) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, kind, refid, brief, detailed, filepath)
        )

    def _ingest_broader_context(self, cursor):
        """Scan repository for documentation files and ingest them."""
        ignore_dirs = {".git", "build", "node_modules", "html", "latex", ".venv", "__pycache__"}

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in {'.md', '.yaml', '.yml', '.txt'}:
                    self._ingest_file(cursor, root, file)

    def _ingest_file(self, cursor, root, file):
        """Ingest a single documentation file into the index."""
        filepath = Path(root) / file
        try:
            rel_path = filepath.relative_to(self.repo_root)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            cursor.execute(
                "INSERT INTO symbols (name, kind, refid, brief, detailed, filepath) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (file, "documentation", "file_context", "Repository Specification/Documentation",
                 content, str(rel_path))
            )
        except Exception:
            pass

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform a semantic search using SQLite FTS5."""
        if not self.db_path.exists():
            return []

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name, kind, refid, brief, filepath, bm25(symbols) as rank
                FROM symbols
                WHERE symbols MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "name": row[0],
                    "kind": row[1],
                    "refid": row[2],
                    "brief": row[3],
                    "filepath": row[4],
                    "rank": round(row[5], 2) # bm25 score
                })

            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error("SQLite search error: %s", e)
            return [{"error": f"Search failed: {e}"}]
