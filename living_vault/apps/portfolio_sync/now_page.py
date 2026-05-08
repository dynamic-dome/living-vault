"""Build a /now page combining latest session summary and open wiki TODOs."""
from __future__ import annotations
from pathlib import Path
import frontmatter


def _parse_todo(path: Path) -> dict | None:
    try:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    fm = dict(post.metadata)
    if str(fm.get("status", "open")).lower() != "open":
        return None
    title = post.content.strip().splitlines()[0].lstrip("# ").strip() if post.content.strip() else path.stem
    return {
        "title": title,
        "priority": fm.get("priority", ""),
        "tags": fm.get("tags", []),
        "path": path.name,
    }


def build_now_page(session_summary: Path, todos_dir: Path) -> str:
    parts: list[str] = ["---", "type: now-page", "---", "", "# Was ich gerade tue", ""]

    if session_summary.exists():
        try:
            post = frontmatter.loads(session_summary.read_text(encoding="utf-8"))
            parts.append("## Letzte Session")
            parts.append("")
            parts.append(post.content.strip())
            parts.append("")
        except Exception:
            parts.append("(session summary unreadable)")
    else:
        parts.append("(no session summary available)")
        parts.append("")

    if todos_dir.exists():
        open_todos: list[dict] = []
        for f in sorted(todos_dir.glob("*.md")):
            t = _parse_todo(f)
            if t is not None:
                open_todos.append(t)
        if open_todos:
            parts.append("## Offene TODOs")
            parts.append("")
            for t in open_todos:
                prio = f" [P{t['priority']}]" if t["priority"] else ""
                parts.append(f"- {t['title']}{prio}")
            parts.append("")
    return "\n".join(parts)
