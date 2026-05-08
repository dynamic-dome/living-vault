"""Top-level CLI for living-vault."""
from __future__ import annotations
from pathlib import Path
import click

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings


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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
