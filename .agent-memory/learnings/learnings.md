# Learnings

*Auto-generated from learnings.json — do not edit directly.*

## 2026-05-11

- [L1] (****) Phase-13 `deploy-public-vault.ps1` hatte `-Vault` Default auf `$HOME\wiki`, aber `pages.path` in der DB ist relativ zu `$HOME\wiki\wiki`. Folge: `history.json` im Live-Vault leer. Tests blieben gruen weil Fixture-basiert. Lesson: phase-close-tests fangen Konfigurationsdefault-Bugs nicht.
- [L2] (***) Living-Vault ist bereits ein generischer Vault-Reader. CLI-Schnittstellen akzeptieren beliebige `--vault`/`--db`/`--allowlist`/`--out-dir`. PoC gegen kompetenz-wiki: 193 Pages, 840 Edges, 0 Errors, kein Code-Change. `vault-engine-mcp` parsed auch Frontmatter-Felder `supports`/`depends_on`/`applies_to` als Edges.
