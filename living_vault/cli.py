"""Top-level CLI for living-vault."""
from __future__ import annotations
import json
import sqlite3
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


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}


def _status_payload(db_p: Path) -> dict[str, object]:
    if not db_p.exists():
        return {
            "status": "missing-db",
            "pages_total": 0,
            "links_total": 0,
            "embeddings_total": 0,
            "current": 0,
            "stale": 0,
            "unknown": 0,
            "missing": 0,
            "orphan": 0,
            "models": [],
        }

    con = db_mod.connect(db_p)
    try:
        required_tables = {"pages", "links", "embeddings_blob"}
        missing_tables = [t for t in sorted(required_tables) if not _table_exists(con, t)]
        embedding_columns = _columns(con, "embeddings_blob") if not missing_tables else set()
        legacy_schema = bool(missing_tables) or "content_hash" not in embedding_columns
        if legacy_schema:
            return {
                "status": "legacy-schema",
                "pages_total": 0,
                "links_total": 0,
                "embeddings_total": 0,
                "current": 0,
                "stale": 0,
                "unknown": 0,
                "missing": 0,
                "orphan": 0,
                "models": [],
                "missing_tables": missing_tables,
            }

        pages_total = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        links_total = con.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        embeddings_total = con.execute("SELECT COUNT(*) FROM embeddings_blob").fetchone()[0]
        current = con.execute(
            """
            SELECT COUNT(*)
            FROM embeddings_blob e
            JOIN pages p ON p.path = e.path
            WHERE e.content_hash = p.content_hash
            """
        ).fetchone()[0]
        unknown = con.execute(
            """
            SELECT COUNT(*)
            FROM embeddings_blob e
            JOIN pages p ON p.path = e.path
            WHERE e.content_hash IS NULL
            """
        ).fetchone()[0]
        stale = con.execute(
            """
            SELECT COUNT(*)
            FROM embeddings_blob e
            JOIN pages p ON p.path = e.path
            WHERE e.content_hash IS NOT NULL AND e.content_hash != p.content_hash
            """
        ).fetchone()[0]
        missing = con.execute(
            """
            SELECT COUNT(*)
            FROM pages p
            LEFT JOIN embeddings_blob e ON e.path = p.path
            WHERE e.path IS NULL
            """
        ).fetchone()[0]
        orphan = con.execute(
            """
            SELECT COUNT(*)
            FROM embeddings_blob e
            LEFT JOIN pages p ON p.path = e.path
            WHERE p.path IS NULL
            """
        ).fetchone()[0]
        models = [
            row["model"]
            for row in con.execute(
                "SELECT DISTINCT model FROM embeddings_blob ORDER BY model"
            )
        ]
        status = "ok"
        if stale or unknown or missing or orphan:
            status = "needs-reembed"
        return {
            "status": status,
            "pages_total": pages_total,
            "links_total": links_total,
            "embeddings_total": embeddings_total,
            "current": current,
            "stale": stale,
            "unknown": unknown,
            "missing": missing,
            "orphan": orphan,
            "models": models,
        }
    finally:
        con.close()


@cli.command("status")
@click.option("--db", required=True, type=click.Path())
@click.option("--json", "json_output", is_flag=True, help="print machine-readable JSON")
def status_cmd(db: str, json_output: bool) -> None:
    """Report DB and embedding freshness without loading an embedding model."""
    payload = _status_payload(Path(db))
    if json_output:
        click.echo(json.dumps(payload, sort_keys=True))
    else:
        models = ",".join(payload["models"]) if payload["models"] else "-"
        fields = [
            f"status={payload['status']}",
            f"pages_total={payload['pages_total']}",
            f"links_total={payload['links_total']}",
            f"embeddings_total={payload['embeddings_total']}",
            f"current={payload['current']}",
            f"stale={payload['stale']}",
            f"unknown={payload['unknown']}",
            f"missing={payload['missing']}",
            f"orphan={payload['orphan']}",
            f"models={models}",
        ]
        click.echo(" ".join(fields))
    if payload["status"] in {"missing-db", "legacy-schema"}:
        raise click.exceptions.Exit(1)


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


@cli.command("export-seance-bundle")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", "db_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--allowlist", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--persona", "personas", multiple=True, required=True,
              help="Relpath einer Persona-Page; 1-3x angeben. Muss auf der Allowlist stehen.")
@click.option("--demo", type=click.Path(exists=True, dir_okay=False), default=None,
              help="JSON-Datei mit vorgenerierten Demo-Konversationen.")
@click.option("--out", required=True, type=click.Path())
def export_seance_bundle_cmd(vault, db_path, allowlist, personas, demo, out):
    """Exportiert das public-safe Séance-Bundle für die Website."""
    import json as _json
    from pathlib import Path as _P

    from living_vault.apps.seance_ui.bundle import (
        SeanceExportError, build_seance_bundle, validate_bundle_text,
    )
    from living_vault.core.privacy import load_allowlist as _load_allowlist

    try:
        bundle = build_seance_bundle(
            vault_root=_P(vault), db_path=_P(db_path),
            allowlist_path=_P(allowlist), persona_paths=list(personas),
            demo_path=_P(demo) if demo else None,
        )
        text = _json.dumps(bundle, ensure_ascii=False, indent=2)
        findings = validate_bundle_text(text, allowed=set(_load_allowlist(_P(allowlist))))
        if findings:
            raise SeanceExportError(
                "validator findings (export aborted):\n" + "\n".join(findings)
            )
    except SeanceExportError as exc:
        raise click.ClickException(str(exc))
    _P(out).write_text(text, encoding="utf-8")
    click.echo(
        f"wrote {out} ({len(bundle['personas'])} personas, "
        f"{len(bundle['demo_conversations'])} demo conversations)"
    )


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
