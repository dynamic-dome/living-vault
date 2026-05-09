"""Top-level CLI for living-vault."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import click

from living_vault.core import db as db_mod
from living_vault.core import history as history_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.core.llm import get_llm
from living_vault.core.reader import read_page
from living_vault.core.voice.distill import distill_voice_via_llm


@click.group()
def cli() -> None:
    """living-vault command-line interface."""


@cli.command("index")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path())
@click.option("--no-embed", is_flag=True, help="skip embedding stage")
def index_cmd(vault: str, db: str, no_embed: bool) -> None:
    vault_p = Path(vault)
    db_p = Path(db)
    db_mod.initialize(db_p)
    stats = index_vault(vault_p, db_p)
    click.echo(f"index pages_seen={stats['pages_seen']} pages_updated={stats['pages_updated']}")
    if not no_embed:
        n = index_embeddings(vault_p, db_p)
        click.echo(f"embeddings updated={n}")


# ~ Phase-9 ~

# Anthropic Haiku 4.5 — published price (as of 2026-05): $0.80 / $4 per million
# input/output tokens. We assume ~7K total tokens per call (most input, ~150 out).
# That's ~$0.0056 input + ~$0.0006 output = ~$0.0062 per page → ~$5.91 / 953.
# We display the rounded estimate; actual will vary with body length.
_ESTIMATED_USD_PER_PAGE = 0.006


def _select_pages_to_distill(con, force: bool, limit: int | None) -> list[str]:
    if force:
        sql = "SELECT path FROM pages ORDER BY path"
    else:
        sql = "SELECT path FROM pages WHERE voice_distilled IS NULL ORDER BY path"
    rows = con.execute(sql).fetchall()
    paths = [r[0] for r in rows]
    if limit is not None:
        paths = paths[:limit]
    return paths


@cli.command("extract-voice")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None, help="cap pages processed (probe runs)")
@click.option("--force", is_flag=True, help="re-distill pages that already have voice_distilled")
@click.option("--yes", is_flag=True, help="skip cost-confirmation prompt (non-interactive)")
def extract_voice_cmd(vault: str, db: str, limit: int | None, force: bool, yes: bool) -> None:
    """Distill voice descriptions for pages via the configured LLM (default: Anthropic Haiku 4.5).

    With LIVING_VAULT_FAKE_LLM=1 set, uses FakeLLM (no API calls). Cached
    results are skipped unless --force is passed.
    """
    vault_p = Path(vault)
    db_p = Path(db)
    con = db_mod.connect(db_p)

    paths = _select_pages_to_distill(con, force=force, limit=limit)
    fresh_n = len(paths)
    cached_n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    total_n = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    click.echo(f"Pages to distill: {fresh_n} (already cached: {cached_n}, total: {total_n})")
    est_cost = _ESTIMATED_USD_PER_PAGE * fresh_n
    est_seconds = fresh_n * 0.75  # ~750ms per Haiku call typical
    click.echo(f"Estimated cost: ~${est_cost:.2f} (Anthropic Haiku 4.5)")
    click.echo(f"Estimated time: ~{est_seconds / 60:.1f} minutes")

    if fresh_n == 0:
        click.echo("Nothing to do.")
        con.close()
        return

    if not yes:
        click.confirm("Continue?", abort=True, default=False)

    llm = get_llm()
    ok = 0
    failed = 0
    for path in paths:
        try:
            row = con.execute(
                "SELECT title, frontmatter FROM pages WHERE path = ?", (path,)
            ).fetchone()
            fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
            page = read_page(vault_p / path, vault_p)
            distill_input = {
                "title": page.title,
                "created": str(fm.get("created", "")),
                "tags": list(fm.get("tags", []) or []),
                "body": page.body or "",
            }
            text = distill_voice_via_llm(distill_input, llm)
            con.execute(
                "UPDATE pages SET voice_distilled = ? WHERE path = ?",
                (text, path),
            )
            con.commit()
            ok += 1
        except Exception as exc:
            sys.stderr.write(f"[extract-voice] {path}: {exc}\n")
            failed += 1
            continue
    con.close()
    click.echo(f"done: {ok} OK, {failed} failed.")
    if failed:
        click.echo("Re-run extract-voice to retry failed pages.", err=True)


@cli.command("history")
@click.argument("path")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--limit", default=10, type=int, help="number of commits (default 10, max 100)")
def history_cmd(path: str, vault: str, limit: int) -> None:
    """Show git history of a vault page (Phase 13)."""
    rows = history_mod.page_history(Path(vault), path, limit=limit)
    if not rows:
        click.echo("(no history found)")
        return
    click.echo(f"{'sha':<10} {'date':<25} {'author':<20} subject")
    click.echo("-" * 80)
    for r in rows:
        date = (r["date"] or "")[:25]
        author = (r["author"] or "")[:20]
        click.echo(f"{r['sha']:<10} {date:<25} {author:<20} {r['subject']}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
