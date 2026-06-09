from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import get_settings


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_project_id() -> str:
    return uuid.uuid4().hex[:12]


def project_dir(project_id: str) -> Path:
    return get_settings().runs_dir / project_id


def artifact_path(project_id: str, name: str) -> Path:
    return project_dir(project_id) / "artifacts" / name


def project_json_path(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def save_project(project: dict[str, Any]) -> None:
    path = project_json_path(project["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(project_id: str) -> dict[str, Any]:
    path = project_json_path(project_id)
    if not path.exists():
        raise FileNotFoundError(project_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_projects() -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    paths = sorted(
        get_settings().runs_dir.glob("*/project.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        try:
            projects.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return projects


def ensure_project_dirs(project_id: str) -> None:
    base = project_dir(project_id)
    for name in ("uploads", "artifacts", "logs"):
        (base / name).mkdir(parents=True, exist_ok=True)


def save_upload(project_id: str, filename: str, content: bytes) -> Path:
    safe_name = Path(filename).name or "upload.bin"
    target = project_dir(project_id) / "uploads" / safe_name
    target.write_bytes(content)
    return target


def export_zip(project_id: str) -> Path:
    base = project_dir(project_id)
    archive_base = base / "artifacts" / f"{project_id}-deliverables"
    zip_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=base, base_dir="artifacts"))
    return zip_path
