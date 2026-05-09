"""Privacy regression: verify no private path appears in public builds.

This is a high-stakes test. If it ever fails, do NOT merge — investigate.
"""
from pathlib import Path
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli as render_cli
from living_vault.core.privacy import public_pages
from living_vault.core import db as db_mod2


def test_no_private_path_in_public_synesthesia_build(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(render_cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0
    text = out.read_text(encoding="utf-8")

    con = db_mod2.connect(db)
    public = set(public_pages(con))
    all_pages = {r[0] for r in con.execute("SELECT path FROM pages")}
    private = all_pages - public
    con.close()

    for priv in private:
        assert priv not in text, f"PRIVACY LEAK: private path {priv} found in public build"


from living_vault.apps.portfolio_sync.sync import cli as portfolio_cli


def test_no_private_in_portfolio_sync(vault_copy: Path, tmp_path: Path, monkeypatch):
    db = tmp_path / ".vault-engine.db"
    target = tmp_path / "site"
    target.mkdir()
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(target))
    runner = CliRunner()
    res = runner.invoke(
        portfolio_cli,
        ["sync", "--vault", str(vault_copy), "--db", str(db)],
    )
    assert res.exit_code == 0, res.output
    # Private pages must NEVER appear under target
    private_paths = ["concepts/note-a.md", "synthesis/syn-1.md"]
    for priv in private_paths:
        candidate = target / "wiki-pages" / priv
        assert not candidate.exists(), f"PRIVACY LEAK: {candidate} written"


from living_vault.apps.synesthesia.layout import compute_layout


def test_no_private_path_in_public_build_with_allowlist(vault_copy: Path, tmp_path: Path):
    """Allowlist is an explicit override: allowlisted private page becomes public,
    but OTHER private pages must NOT leak into the build."""
    db = tmp_path / ".vault-engine.db"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)

    # note-a is private but explicitly allowlisted
    nodes, _ = compute_layout(db, public_only=True, allowlist=["concepts/note-a.md"])
    paths = {n["path"] for n in nodes}

    # note-a must appear (allowlist override)
    assert "concepts/note-a.md" in paths, "Allowlisted private page must appear in public build"
    # note-b must appear (is_public=1)
    assert "concepts/note-b.md" in paths, "Public page must appear in public build"
    # syn-1 must NOT appear (private, not in allowlist)
    assert "synthesis/syn-1.md" not in paths, \
        "PRIVACY LEAK: non-allowlisted private page syn-1 found in public build"


def test_no_private_path_in_public_build_when_allowlist_empty(vault_copy: Path, tmp_path: Path):
    """Empty allowlist [] behaves identically to allowlist=None — only is_public=1 filter."""
    db = tmp_path / ".vault-engine.db"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)

    nodes_empty, edges_empty = compute_layout(db, public_only=True, allowlist=[])
    nodes_none, edges_none = compute_layout(db, public_only=True, allowlist=None)

    paths_empty = {n["path"] for n in nodes_empty}
    paths_none = {n["path"] for n in nodes_none}

    assert paths_empty == paths_none, \
        f"Empty allowlist must equal no allowlist: {paths_empty} != {paths_none}"
    # Only the one public page should appear
    assert paths_empty == {"concepts/note-b.md"}, \
        f"Expected only note-b (public), got: {paths_empty}"


def test_edge_between_public_and_private_page_not_rendered(vault_copy: Path, tmp_path: Path):
    """Edge filter: an edge X->Y only appears in the output when BOTH X and Y are in the
    filtered node set. Verified across two build variants."""
    db = tmp_path / ".vault-engine.db"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)

    # Branch 1: public_only=True, no allowlist -> only note-b in set
    # note-a is private so the edge note-a->note-b must NOT appear
    _, edges_no_allowlist = compute_layout(db, public_only=True, allowlist=None)
    edge_pairs_no_allowlist = {(e["from"], e["to"]) for e in edges_no_allowlist}
    assert ("concepts/note-a.md", "concepts/note-b.md") not in edge_pairs_no_allowlist, \
        "PRIVACY LEAK: edge from private note-a to public note-b appears without allowlist"

    # Branch 2: public_only=True, allowlist=[note-a] -> both note-a and note-b in set
    # now the edge MUST appear
    _, edges_with_allowlist = compute_layout(db, public_only=True, allowlist=["concepts/note-a.md"])
    edge_pairs_with_allowlist = {(e["from"], e["to"]) for e in edges_with_allowlist}
    assert ("concepts/note-a.md", "concepts/note-b.md") in edge_pairs_with_allowlist, \
        "Edge note-a->note-b must appear when both endpoints are in the filtered set (allowlist)"
