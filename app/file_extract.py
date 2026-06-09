from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
MEDIA_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".gif", ".png", ".jpg", ".jpeg", ".webp"}


def _xml_text(xml_bytes: bytes, tag: str) -> list[str]:
    root = ET.fromstring(xml_bytes)
    return [node.text or "" for node in root.iter() if node.tag.endswith(tag)]


def extract_docx(path: Path) -> str:
    with ZipFile(path) as zf:
        xml_bytes = zf.read("word/document.xml")
    texts = _xml_text(xml_bytes, "}t")
    return "\n".join(line.strip() for line in texts if line.strip())


def extract_pptx(path: Path) -> str:
    chunks: list[str] = []
    with ZipFile(path) as zf:
        slides = sorted(
            [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda name: int(re.search(r"(\d+)", name).group(1)),
        )
        for index, slide in enumerate(slides, start=1):
            texts = _xml_text(zf.read(slide), "}t")
            joined = " ".join(text.strip() for text in texts if text.strip())
            if joined:
                chunks.append(f"第{index}页：{joined}")
    return "\n".join(chunks)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pptx":
        return extract_pptx(path)
    return ""


def describe_upload(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower()
    kind = "media" if suffix in MEDIA_EXTENSIONS else "document"
    if suffix in {".docx", ".txt", ".md", ".markdown", ".pptx"}:
        kind = "reference"
    return {
        "filename": path.name,
        "size": path.stat().st_size,
        "suffix": suffix,
        "kind": kind,
        "text_preview": extract_text(path)[:1200],
    }
