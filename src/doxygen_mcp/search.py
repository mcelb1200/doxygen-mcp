"""
Semantic Search Engine using SQLite FTS5 for Doxygen MCP.
Provides fast conceptual search across code and specifications.
"""
import sqlite3
import logging
import os
import defusedxml.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DoxygenSearchIndex:
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
            logger.warning(f"No index.xml found in {self.xml_dir}")
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

    def _build_index(self):
        """Parse XML and broader context to build the FTS5 index."""
        logger.info(f"Building SQLite FTS5 search index at {self.db_path}")
        
        # Remove old db if it exists
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete old db: {e}")

        conn = self.get_connection()
        cursor = conn.cursor()

        # Create FTS5 virtual table
        # We index name, kind, refid, brief, detailed, and filepath
        cursor.execute("""
            CREATE VIRTUAL TABLE symbols USING fts5(
                name, kind, refid, brief, detailed, filepath
            )
        """)

        # 1. Ingest Doxygen XML Compounds
        try:
            tree = ET.parse(self.index_xml)
            root = tree.getroot()
            
            if root is None:
                logger.error(f"Empty or invalid index.xml in {self.xml_dir}")
                return

            for compound in root.findall("compound"):
                refid = compound.get("refid")
                kind = compound.get("kind")
                name_elem = compound.find("name")
                name = name_elem.text if name_elem is not None else ""
                
                # Parse the detailed XML for this compound to get descriptions
                xml_file = self.xml_dir / f"{refid}.xml"
                brief = ""
                detailed = ""
                filepath = ""
                
                if xml_file.exists():
                    try:
                        ct_tree = ET.parse(xml_file)
                        ct_root = ct_tree.getroot()
                        if ct_root is None:
                            continue

                        compounddef = ct_root.find("compounddef")
                        if compounddef is not None:
                            brief_elem = compounddef.find("briefdescription")
                            if brief_elem is not None:
                                brief = "".join(brief_elem.itertext()).strip()
                            
                            det_elem = compounddef.find("detaileddescription")
                            if det_elem is not None:
                                detailed = "".join(det_elem.itertext()).strip()
                                
                            loc = compounddef.find("location")
                            if loc is not None:
                                filepath = loc.get("file", "")
                    except Exception as e:
                        logger.warning(f"Failed to parse {xml_file.name}: {e}")
                
                cursor.execute(
                    "INSERT INTO symbols (name, kind, refid, brief, detailed, filepath) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, kind, refid, brief, detailed, filepath)
                )
        except Exception as e:
            logger.error(f"Error parsing Doxygen XML for index: {e}")

        # 2. Ingest Broader Context (.md, .yaml)
        self._ingest_broader_context(cursor)

        conn.commit()
        conn.close()
        logger.info("FTS5 index build complete.")

    def _ingest_broader_context(self, cursor):
        """Scan repository for documentation files and ingest them."""
        ignore_dirs = {".git", "build", "node_modules", "html", "latex", ".venv", "__pycache__"}
        
        for root, dirs, files in os.walk(self.repo_root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in {'.md', '.yaml', '.yml', '.txt'}:
                    filepath = Path(root) / file
                    try:
                        # Try relative path
                        rel_path = filepath.relative_to(self.repo_root)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Use filename as name, content as detailed
                        cursor.execute(
                            "INSERT INTO symbols (name, kind, refid, brief, detailed, filepath) VALUES (?, ?, ?, ?, ?, ?)",
                            (file, "documentation", "file_context", "Repository Specification/Documentation", content, str(rel_path))
                        )
                    except Exception as e:
                        # Skip files that can't be read (e.g., binary or encoding issues)
                        pass

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform a semantic search using SQLite FTS5."""
        if not self.db_path.exists():
            return []
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use SQLite FTS5 MATCH syntax
            # By default FTS5 ranks by bm25()
            # We append a wildcard to the last term for prefix matching if requested, but standard MATCH is safer
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
            logger.error(f"SQLite search error: {e}")
            return [{"error": f"Search failed: {e}"}]
