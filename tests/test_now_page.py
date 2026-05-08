from pathlib import Path
from living_vault.apps.portfolio_sync.now_page import build_now_page


def test_build_now_page_with_inputs(tmp_path: Path):
    summary = tmp_path / "summary.md"
    summary.write_text("---\n---\n# Last session\nDoing X.\n", encoding="utf-8")
    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    (todos_dir / "2026-05-01-x.md").write_text(
        "---\nstatus: open\npriority: high\n---\n# Fix X\n", encoding="utf-8"
    )
    (todos_dir / "2026-05-02-y.md").write_text(
        "---\nstatus: closed\n---\n# Done thing\n", encoding="utf-8"
    )
    text = build_now_page(session_summary=summary, todos_dir=todos_dir)
    assert "Doing X" in text
    assert "Fix X" in text
    assert "Done thing" not in text  # closed must be filtered


def test_build_now_page_handles_missing_summary(tmp_path: Path):
    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    text = build_now_page(session_summary=tmp_path / "missing.md", todos_dir=todos_dir)
    assert "no session summary" in text.lower()
