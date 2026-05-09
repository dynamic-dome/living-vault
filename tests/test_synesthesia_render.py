from pathlib import Path
import json
import re
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli, public_build_cli


def test_render_writes_html(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "out.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out)])
    assert res.exit_code == 0, res.output
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-a.md" in text
    assert "<canvas" in text or "renderer.domElement" in text


def test_render_public_only_excludes_private(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0, res.output
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-b.md" in text       # public
    assert "concepts/note-a.md" not in text   # private must NOT appear
    assert "synthesis/syn-1.md" not in text   # also private


# ---------------------------------------------------------------------------
# Task 11.3 — Public-Build CLI tests
# ---------------------------------------------------------------------------

def _setup_db(vault_copy: Path, tmp_path: Path) -> Path:
    """Initialize and index the fixture vault, return db path."""
    db = tmp_path / ".vault-engine.db"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    return db


def test_public_build_writes_three_files(vault_copy: Path, tmp_path: Path):
    """public_build_cli produces index.html, manifest.json, pages.json in out_dir."""
    db = _setup_db(vault_copy, tmp_path)
    out_dir = tmp_path / "out"
    runner = CliRunner()
    res = runner.invoke(
        public_build_cli,
        ["--vault", str(vault_copy), "--db", str(db), "--out", str(out_dir)],
    )
    assert res.exit_code == 0, f"exit_code={res.exit_code}\n{res.output}\n{res.exception}"
    assert (out_dir / "index.html").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "pages.json").exists()


def test_public_build_manifest_has_required_fields(vault_copy: Path, tmp_path: Path):
    """Manifest contains all §6-schema fields with correct values."""
    db = _setup_db(vault_copy, tmp_path)
    out_dir = tmp_path / "out"

    # Allowlist: concepts/note-a.md exists, concepts/typo.md does not
    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("concepts/note-a.md\nconcepts/typo.md\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(
        public_build_cli,
        [
            "--vault", str(vault_copy),
            "--db", str(db),
            "--allowlist", str(allowlist_file),
            "--out", str(out_dir),
        ],
    )
    assert res.exit_code == 0, f"exit_code={res.exit_code}\n{res.output}\n{res.exception}"

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    # schema_version
    assert manifest["schema_version"] == 1

    # build_at: UTC ISO8601 "YYYY-MM-DDTHH:MM:SSZ"
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["build_at"]), \
        f"build_at format unexpected: {manifest['build_at']}"

    # Required keys
    required_keys = [
        "schema_version", "build_at", "vault_root", "vault_total_pages",
        "public_via_frontmatter", "public_via_allowlist", "public_total",
        "allowlist_path", "allowlist_skipped", "edges_total", "variant",
        "embed_url", "build_tool", "engine_version",
    ]
    for key in required_keys:
        assert key in manifest, f"Missing manifest key: {key}"

    # skipped path is the non-existent one
    assert manifest["allowlist_skipped"] == ["concepts/typo.md"], \
        f"allowlist_skipped unexpected: {manifest['allowlist_skipped']}"

    # public_total: note-b (frontmatter) + note-a (allowlist) = 2
    assert manifest["public_total"] == 2, \
        f"Expected public_total=2, got {manifest['public_total']}"

    # sanity: vault_total_pages covers the 3 fixture pages
    assert manifest["vault_total_pages"] == 3


def test_public_build_skips_nonexistent_allowlist_paths(vault_copy: Path, tmp_path: Path):
    """Allowlist with only non-existent paths: no crash, exit=0, skipped in manifest."""
    db = _setup_db(vault_copy, tmp_path)
    out_dir = tmp_path / "out"

    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("does/not/exist.md\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(
        public_build_cli,
        [
            "--vault", str(vault_copy),
            "--db", str(db),
            "--allowlist", str(allowlist_file),
            "--out", str(out_dir),
        ],
    )
    assert res.exit_code == 0, f"exit_code={res.exit_code}\n{res.output}\n{res.exception}"

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "does/not/exist.md" in manifest["allowlist_skipped"]


def test_public_build_is_deterministic_modulo_build_at(vault_copy: Path, tmp_path: Path):
    """Two consecutive builds with same inputs produce byte-identical index.html and pages.json.
    manifest.json may differ only in build_at.
    No private paths must appear in the HTML.
    """
    db = _setup_db(vault_copy, tmp_path)

    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("concepts/note-a.md\n", encoding="utf-8")

    runner = CliRunner()
    args = [
        "--vault", str(vault_copy),
        "--db", str(db),
        "--allowlist", str(allowlist_file),
        "--out", str(tmp_path / "out1"),
    ]
    res1 = runner.invoke(public_build_cli, args)
    assert res1.exit_code == 0, f"Build 1 failed: {res1.output}\n{res1.exception}"

    args2 = args[:]
    args2[args2.index(str(tmp_path / "out1"))] = str(tmp_path / "out2")
    res2 = runner.invoke(public_build_cli, args2)
    assert res2.exit_code == 0, f"Build 2 failed: {res2.output}\n{res2.exception}"

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    html1 = (out1 / "index.html").read_bytes()
    html2 = (out2 / "index.html").read_bytes()
    assert html1 == html2, "index.html is not deterministic across builds"

    pages1 = (out1 / "pages.json").read_bytes()
    pages2 = (out2 / "pages.json").read_bytes()
    assert pages1 == pages2, "pages.json is not deterministic across builds"

    # manifest may differ only in build_at — check all other fields equal
    m1 = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    for key in m1:
        if key == "build_at":
            continue
        assert m1[key] == m2[key], f"manifest field '{key}' differs: {m1[key]} vs {m2[key]}"

    # Privacy check: synthesis/syn-1.md is private and NOT in allowlist
    html_text = html1.decode("utf-8")
    assert "synthesis/syn-1.md" not in html_text, \
        "PRIVACY LEAK: private path synthesis/syn-1.md found in public build HTML"
