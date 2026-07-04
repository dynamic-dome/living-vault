"""Read markdown pages from a vault root with frontmatter parsing."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import frontmatter


@dataclass
class Page:
    relpath: str            # forward-slash, relative to vault_root, e.g. "concepts/note-a.md"
    title: str              # filename stem
    body: str               # markdown body (without frontmatter)
    frontmatter: dict[str, Any] = field(default_factory=dict)
    mtime: float = 0.0
    is_public: bool = False
    content_hash_value: str = ""


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_page(file_path: Path, vault_root: Path) -> Page:
    file_path = file_path.resolve()
    vault_root = vault_root.resolve()
    rel = file_path.relative_to(vault_root).as_posix()
    raw = file_path.read_text(encoding="utf-8")
    try:
        fm = frontmatter.loads(raw)
        body = fm.content
        md = dict(fm.metadata)
    except Exception:
        body = raw
        md = {}
    is_public = bool(md.get("public", False))
    return Page(
        relpath=rel,
        title=file_path.stem,
        body=body,
        frontmatter=md,
        mtime=file_path.stat().st_mtime,
        is_public=is_public,
        content_hash_value=content_hash(raw),
    )


from collections.abc import Iterator


def walk_vault(vault_root: Path) -> Iterator[Page]:
    """Yield Page for every .md file under vault_root, skipping dotted dirs/files."""
    vault_root = vault_root.resolve()
    for path in vault_root.rglob("*.md"):
        rel = path.relative_to(vault_root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield read_page(path, vault_root)
