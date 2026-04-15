from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .db import transaction


@dataclass
class StoredFile:
    rel_path: str
    checksum: str
    size: int


class FileStorageService:
    def __init__(self, uploads_dir: Path, temp_dir: Path):
        self.uploads_dir = uploads_dir
        self.temp_dir = temp_dir

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fp:
            for chunk in iter(lambda: fp.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _stage(self, content: bytes) -> Path:
        staged = self.temp_dir / f"stage-{uuid.uuid4().hex}.tmp"
        with staged.open("wb") as fp:
            fp.write(content)
        return staged

    def save_document(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: int,
        category: str,
        status: str,
        original_name: str,
        content: bytes,
        visibility_scope: str,
        correlation_id: str,
        created_by: int | None,
    ) -> int:
        staged = self._stage(content)
        checksum = self._hash_file(staged)
        ext = Path(original_name).suffix
        final_name = f"{uuid.uuid4().hex}{ext}"
        final_path = self.uploads_dir / final_name
        published = False

        try:
            with transaction(conn):
                staged.replace(final_path)
                published = True
                cursor = conn.execute(
                    """
                    INSERT INTO documents(project_id, category, status, original_name, storage_path, file_sha256, visibility_scope, created_by)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        category,
                        status,
                        original_name,
                        final_name,
                        checksum,
                        visibility_scope,
                        created_by,
                    ),
                )
                doc_id = int(cursor.lastrowid)
                conn.execute(
                    "INSERT INTO document_events(document_id, event_type, correlation_id, details) VALUES(?, 'uploaded', ?, ?)",
                    (doc_id, correlation_id, f"stored_in={final_name}"),
                )
            return doc_id
        except Exception:
            if published and final_path.exists():
                final_path.unlink(missing_ok=True)
            staged.unlink(missing_ok=True)
            raise

    def replace_document(
        self,
        conn: sqlite3.Connection,
        *,
        document_id: int,
        new_original_name: str,
        new_content: bytes,
        correlation_id: str,
    ) -> int:
        old = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if old is None:
            raise ValueError(f"Document {document_id} not found")

        staged = self._stage(new_content)
        checksum = self._hash_file(staged)
        ext = Path(new_original_name).suffix
        final_name = f"{uuid.uuid4().hex}{ext}"
        final_path = self.uploads_dir / final_name
        published = False

        try:
            with transaction(conn):
                staged.replace(final_path)
                published = True
                cursor = conn.execute(
                    """
                    INSERT INTO documents(project_id, category, status, original_name, storage_path, file_sha256, visibility_scope, linked_entity_type, linked_entity_id, created_by)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        old["project_id"],
                        old["category"],
                        old["status"],
                        new_original_name,
                        final_name,
                        checksum,
                        old["visibility_scope"],
                        old["linked_entity_type"],
                        old["linked_entity_id"],
                        old["created_by"],
                    ),
                )
                new_id = int(cursor.lastrowid)
                conn.execute("UPDATE documents SET replaced_by = ? WHERE id = ?", (new_id, document_id))
                conn.execute(
                    "INSERT INTO document_events(document_id, event_type, correlation_id, details) VALUES(?, 'replaced', ?, ?)",
                    (document_id, correlation_id, f"new_document_id={new_id}"),
                )
            old_path = self.uploads_dir / old["storage_path"]
            old_path.unlink(missing_ok=True)
            return new_id
        except Exception:
            if published and final_path.exists():
                final_path.unlink(missing_ok=True)
            staged.unlink(missing_ok=True)
            raise

    def reconcile(self, conn: sqlite3.Connection) -> dict[str, list[str]]:
        db_paths = {
            row[0]
            for row in conn.execute("SELECT storage_path FROM documents WHERE replaced_by IS NULL")
        }
        disk_paths = {p.name for p in self.uploads_dir.iterdir() if p.is_file()}

        missing_on_disk = sorted(db_paths - disk_paths)
        orphaned_files = sorted(disk_paths - db_paths)

        return {
            "missing_on_disk": missing_on_disk,
            "orphaned_files": orphaned_files,
        }

    def clear_orphans(self, orphaned: list[str]) -> int:
        removed = 0
        for name in orphaned:
            path = self.uploads_dir / name
            if path.exists():
                path.unlink()
                removed += 1
        return removed
