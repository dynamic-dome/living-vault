"""Synesthesia render CLI: builds a self-contained HTML from db state."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import click
from jinja2 import Environment, FileSystemLoader, select_autoescape

from living_vault.apps.synesthesia.layout import compute_layout
from living_vault.core import db as db_mod
from living_vault.core.privacy import load_allowlist, allowlist_skipped, public_pages

TEMPLATES_DIR = Path(__file__).parent / "templates"


VARIANT_TEMPLATES = {
    "default": "vault-3d.html.j2",
    "galaxy":  "galaxy.html.j2",
    "city":    "city.html.j2",
    "network": "network.html.j2",
}


def render_html(
    db_path: Path,
    output: Path,
    public_only: bool,
    variant: str = "default",
    allowlist: list[str] | None = None,
    **extra_ctx,
) -> None:
    """Render vault HTML.

    extra_ctx: optional template variables passed through as-is (embed_url,
    public_count, vault_total_pages, build_date, build_at, schema_version).
    Ignored by templates that don't reference them (backward-compatible).
    """
    nodes, edges = compute_layout(db_path, public_only=public_only, allowlist=allowlist)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template_name = VARIANT_TEMPLATES.get(variant, VARIANT_TEMPLATES["default"])
    tmpl = env.get_template(template_name)
    ctx = dict(
        title="Vault | public" if public_only else "Vault | full",
        count=len(nodes),
        edge_count=len(edges),
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
    )
    ctx.update(extra_ctx)
    rendered = tmpl.render(**ctx)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def public_build(
    vault_root: Path,
    db_path: Path,
    allowlist_path: Path | None,
    out_dir: Path,
    variant: str = "default",
    embed_url: str = "https://vault.dynamic-dome.com",
) -> dict:
    """Build a deploy-ready public-vault bundle.

    Produces:
      out_dir/index.html       — 3D vault, public subset only
      out_dir/manifest.json    — build metadata (schema_version=1)
      out_dir/pages.json       — list of built pages

    Returns the manifest dict (for CLI logging and tests).
    """
    # Parse allowlist
    allowlist: list[str] = []
    if allowlist_path is not None:
        allowlist = load_allowlist(allowlist_path)

    # Gather stats from DB
    con = db_mod.connect(db_path)
    try:
        vault_total_pages: int = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        public_via_frontmatter: int = con.execute(
            "SELECT COUNT(*) FROM pages WHERE is_public = 1"
        ).fetchone()[0]

        # Pages that are public ONLY via allowlist (not already is_public=1)
        if allowlist:
            placeholders = ",".join("?" * len(allowlist))
            public_via_allowlist: int = con.execute(
                f"SELECT COUNT(*) FROM pages WHERE path IN ({placeholders}) AND is_public = 0",
                allowlist,
            ).fetchone()[0]
        else:
            public_via_allowlist = 0

        all_public = public_pages(con, allowlist if allowlist else None)
        public_total = len(all_public)
        skipped_paths = allowlist_skipped(con, allowlist) if allowlist else []
    finally:
        con.close()

    # Build timestamp
    build_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_date = build_at[:10]

    # Render HTML
    out_dir.mkdir(parents=True, exist_ok=True)
    index_html = out_dir / "index.html"
    render_html(
        db_path=db_path,
        output=index_html,
        public_only=True,
        variant=variant,
        allowlist=allowlist if allowlist else None,
        embed_url=embed_url,
        public_count=public_total,
        vault_total_pages=vault_total_pages,
        build_date=build_date,
        build_at=build_at,
        schema_version=1,
    )

    # Count edges from rendered layout (re-use layout call)
    nodes, edges = compute_layout(db_path, public_only=True, allowlist=allowlist if allowlist else None)
    edges_total = len(edges)

    # Build pages.json
    pages_list = sorted(
        [
            {
                "path": n["path"],
                "title": n["title"],
                "cluster": n["cluster"],
            }
            for n in nodes
        ],
        key=lambda x: x["path"],
    )
    (out_dir / "pages.json").write_text(
        json.dumps({"pages": pages_list}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Build manifest
    manifest = {
        "schema_version": 1,
        "build_at": build_at,
        "vault_root": str(vault_root),
        "vault_total_pages": vault_total_pages,
        "public_via_frontmatter": public_via_frontmatter,
        "public_via_allowlist": public_via_allowlist,
        "public_total": public_total,
        "allowlist_path": str(allowlist_path) if allowlist_path is not None else None,
        "allowlist_skipped": skipped_paths,
        "edges_total": edges_total,
        "variant": variant,
        "embed_url": embed_url,
        "build_tool": "living_vault.apps.synesthesia public-build",
        "engine_version": "0.1.0",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return manifest


@click.command()
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", required=True, type=click.Path())
@click.option("--public-only", is_flag=True, help="render only pages with public:true")
@click.option(
    "--variant",
    type=click.Choice(list(VARIANT_TEMPLATES.keys())),
    default="default",
    help="visual style variant",
)
def cli(db: str, output: str, public_only: bool, variant: str) -> None:
    render_html(Path(db), Path(output), public_only=public_only, variant=variant)
    click.echo(f"wrote {output} (variant={variant})")


@click.command()
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--allowlist", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--out", required=True, type=click.Path())
@click.option(
    "--variant",
    type=click.Choice(list(VARIANT_TEMPLATES.keys())),
    default="default",
)
@click.option("--embed-url", default="https://vault.dynamic-dome.com")
def public_build_cli(
    vault: str,
    db: str,
    allowlist: str | None,
    out: str,
    variant: str,
    embed_url: str,
) -> None:
    manifest = public_build(
        vault_root=Path(vault),
        db_path=Path(db),
        allowlist_path=Path(allowlist) if allowlist is not None else None,
        out_dir=Path(out),
        variant=variant,
        embed_url=embed_url,
    )
    click.echo(
        f"wrote {out}/ ({manifest['public_total']} public, "
        f"{len(manifest['allowlist_skipped'])} skipped, "
        f"edges={manifest['edges_total']})",
        err=True,
    )


if __name__ == "__main__":
    cli()
