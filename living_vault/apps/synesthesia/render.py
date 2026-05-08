"""Synesthesia render CLI: builds a self-contained HTML from db state."""
from __future__ import annotations
import json
from pathlib import Path
import click
from jinja2 import Environment, FileSystemLoader, select_autoescape

from living_vault.apps.synesthesia.layout import compute_layout

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
) -> None:
    nodes, edges = compute_layout(db_path, public_only=public_only)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template_name = VARIANT_TEMPLATES.get(variant, VARIANT_TEMPLATES["default"])
    tmpl = env.get_template(template_name)
    rendered = tmpl.render(
        title="Vault | public" if public_only else "Vault | full",
        count=len(nodes),
        edge_count=len(edges),
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


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


if __name__ == "__main__":
    cli()
