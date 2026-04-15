from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    uploads_dir: Path
    logs_dir: Path
    backups_dir: Path
    quarantine_dir: Path
    temp_dir: Path


def _resolve_data_dir() -> Path:
    env_data_dir = os.getenv("BONIFACIY_DATA_DIR")
    if env_data_dir:
        return Path(env_data_dir).expanduser().resolve()

    if os.name == "nt":
        appdata = os.getenv("PROGRAMDATA") or os.getenv("LOCALAPPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Local"
        return (base / "Bonifaciy").resolve()

    xdg = os.getenv("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg) / "bonifaciy").resolve()
    return (Path.home() / ".local" / "share" / "bonifaciy").resolve()


def build_settings() -> Settings:
    data_dir = _resolve_data_dir()
    db_path = data_dir / "db" / "bonifaciy.sqlite3"
    uploads_dir = data_dir / "uploads"
    logs_dir = data_dir / "logs"
    backups_dir = data_dir / "backups"
    quarantine_dir = data_dir / "quarantine"
    temp_dir = data_dir / "tmp"

    for path in [db_path.parent, uploads_dir, logs_dir, backups_dir, quarantine_dir, temp_dir]:
        path.mkdir(parents=True, exist_ok=True)

    return Settings(
        data_dir=data_dir,
        db_path=db_path,
        uploads_dir=uploads_dir,
        logs_dir=logs_dir,
        backups_dir=backups_dir,
        quarantine_dir=quarantine_dir,
        temp_dir=temp_dir,
    )
