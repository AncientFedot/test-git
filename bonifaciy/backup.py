from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BackupResult:
    archive_path: Path
    manifest_path: Path
    checksum: str


class BackupService:
    def __init__(self, data_dir: Path, db_path: Path, uploads_dir: Path, backups_dir: Path):
        self.data_dir = data_dir
        self.db_path = db_path
        self.uploads_dir = uploads_dir
        self.backups_dir = backups_dir

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fp:
            for chunk in iter(lambda: fp.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _uploads_manifest(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for file in sorted(self.uploads_dir.rglob("*")):
            if file.is_file():
                rel = file.relative_to(self.uploads_dir).as_posix()
                items.append({"path": rel, "sha256": self._sha256(file), "size": file.stat().st_size})
        return items

    def create_backup(self, conn: sqlite3.Connection) -> BackupResult:
        uploads_manifest = self._uploads_manifest()
        manifest: dict[str, Any] = {
            "db": self.db_path.name,
            "uploads_dir": self.uploads_dir.name,
            "db_checksum": self._sha256(self.db_path),
            "uploads_count": len(uploads_manifest),
            "uploads_files": uploads_manifest,
        }

        stamp = manifest["db_checksum"][:12]
        archive = self.backups_dir / f"bonifaciy-backup-{stamp}.tar.gz"
        manifest_path = self.backups_dir / f"bonifaciy-backup-{stamp}.manifest.json"

        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(self.db_path, arcname=f"db/{self.db_path.name}")
            tar.add(self.uploads_dir, arcname="uploads")
            tar.add(manifest_path, arcname=manifest_path.name)

        checksum = self._sha256(archive)
        conn.execute(
            "INSERT INTO backups(archive_path, manifest_path, checksum) VALUES(?, ?, ?)",
            (str(archive), str(manifest_path), checksum),
        )
        conn.commit()
        return BackupResult(archive_path=archive, manifest_path=manifest_path, checksum=checksum)

    def restore(self, archive_path: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="bonifaciy-restore-") as tmp:
            staging = Path(tmp)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=staging)

            manifest_file = next(staging.glob("*.manifest.json"), None)
            if not manifest_file:
                raise ValueError("Backup manifest not found")

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            staged_db = staging / "db" / manifest["db"]
            staged_uploads = staging / "uploads"
            if not staged_db.exists() or not staged_uploads.exists():
                raise ValueError("Invalid backup layout")

            if self._sha256(staged_db) != manifest["db_checksum"]:
                raise ValueError("DB checksum mismatch in staging")

            for item in manifest.get("uploads_files", []):
                candidate = staged_uploads / item["path"]
                if not candidate.exists():
                    raise ValueError(f"Missing upload in backup: {item['path']}")
                if self._sha256(candidate) != item["sha256"]:
                    raise ValueError(f"Checksum mismatch for upload: {item['path']}")

            current_db = self.db_path
            current_uploads = self.uploads_dir

            db_tmp_old = current_db.with_suffix(".restore_old")
            uploads_tmp_old = current_uploads.with_name(current_uploads.name + "_restore_old")

            if db_tmp_old.exists():
                db_tmp_old.unlink()
            if uploads_tmp_old.exists():
                shutil.rmtree(uploads_tmp_old)

            shutil.copy2(current_db, db_tmp_old)
            shutil.copytree(current_uploads, uploads_tmp_old)

            try:
                shutil.copy2(staged_db, current_db)
                if current_uploads.exists():
                    shutil.rmtree(current_uploads)
                shutil.copytree(staged_uploads, current_uploads)
            except Exception:
                if db_tmp_old.exists():
                    shutil.copy2(db_tmp_old, current_db)
                if current_uploads.exists():
                    shutil.rmtree(current_uploads)
                if uploads_tmp_old.exists():
                    shutil.copytree(uploads_tmp_old, current_uploads)
                raise
            finally:
                db_tmp_old.unlink(missing_ok=True)
                if uploads_tmp_old.exists():
                    shutil.rmtree(uploads_tmp_old)
