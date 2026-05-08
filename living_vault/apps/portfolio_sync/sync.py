"""Living-Portfolio sync: write public wiki pages into the cv-dynamic-dome project."""
from __future__ import annotations
import json
import time
from pathlib import Path
import click
import frontmatter

from living_vault.core import db as db_mod
from living_vault.core.privacy import public_pages
from living_vault.core.reader import read_page
from living_vault.apps.portfolio_sync.config import resolve_target_dir


def render_freshness(mtime: float, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    delta_days = max(0, int((now - mtime) / 86400))
    if delta_days < 1:
        return "today"
    if delta_days < 14:
        return f"{delta_days} day(s) ago"
    if delta_days < 60:
        weeks = delta_days // 7
        return f"{weeks} week(s) ago"
    months = delta_days // 30
    return f"{months} month(s) ago"


def plan_sync(vault_root: Path, db_path: Path) -> list[dict]:
    con = db_mod.connect(db_path)
    try:
        public = public_pages(con)
        plan = []
        for relpath in public:
            row = con.execute("SELECT mtime FROM pages WHERE path = ?", (relpath,)).fetchone()
            mtime = row["mtime"] if row else 0.0
            plan.append({"relpath": relpath, "mtime": mtime})
        return plan
    finally:
        con.close()


def write_page(vault_root: Path, target_dir: Path, relpath: str, mtime: float) -> Path:
    page = read_page(vault_root / relpath, vault_root)
    badge = render_freshness(mtime)
    fm = dict(page.frontmatter)
    fm.setdefault("type", "wiki-page")
    fm["freshness"] = badge
    body = page.body
    out_path = target_dir / "wiki-pages" / relpath
    out_path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(body, **fm)
    out_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return out_path


@click.group()
def cli() -> None:
    """portfolio-sync subcommands."""


@cli.command("sync")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True)
def sync_cmd(vault: str, db: str, dry_run: bool) -> None:
    plan = plan_sync(Path(vault), Path(db))
    target = resolve_target_dir()
    click.echo(f"target dir: {target}")
    click.echo(f"would write {len(plan)} page(s)")
    if dry_run:
        for p in plan:
            click.echo(f"  - {p['relpath']}")
        return
    written = 0
    for p in plan:
        out = write_page(Path(vault), target, p["relpath"], p["mtime"])
        written += 1
        click.echo(f"wrote {out}")
    click.echo(f"done: {written} page(s) written")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
