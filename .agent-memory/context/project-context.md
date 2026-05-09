# Project Context

*Last refreshed: 2026-05-09 (patch-init via /agentic-os:init)*

## Project
- **Name:** living-vault
- **Version:** 0.1.0
- **Description:** Vault engine + 3 consumers (synesthesia 3D, séance chat, living-portfolio site)
- **Language:** Python (>=3.11)
- **Build system:** setuptools >=68
- **Package manager:** pip (editable install: `pip install -e ".[embeddings,dev]"`)
- **Test runner:** pytest (asyncio_mode=auto, testpaths=["tests"])

## Stack
- **Core:** python-frontmatter, click, jinja2, numpy, anthropic
- **Server:** fastmcp, fastapi, uvicorn, watchdog
- **Embeddings (optional):** sentence-transformers (`all-MiniLM-L6-v2`), sqlite-vec
- **Dev:** pytest, pytest-asyncio, httpx

## Entry points (`pyproject.toml [project.scripts]`)
- `living-vault` → `living_vault.cli:main`
- `living-vault-mcp` → `living_vault.mcp_servers.vault_engine.server:main`
- `synesthesia` → `living_vault.apps.synesthesia.render:cli`
- `portfolio-sync` → `living_vault.apps.portfolio_sync.sync:cli`
- `seance-ui` → `living_vault.apps.seance_ui.app:main`

## Architecture (one engine, three lenses)
- **Engine:** `living_vault/core/` — reader, graph, decay, privacy, db, embeddings (3 layers: mechanical, semantic, persona-in-Phase-2)
- **Engine MCP:** `living_vault/mcp_servers/vault_engine/server.py` — single MCP layer over the engine
- **Consumer 1 (synesthesia):** local 3D vault rendering via Three.js template
- **Consumer 2 (séance UI):** FastAPI chat with persona-lite + session-export
- **Consumer 3 (portfolio-sync):** auto-sync with `/now` page + freshness badges, default-private, opt-in `public: true`

## State storage
- SQLite single-file at `~/wiki/.vault-engine.db`
- Default-private privacy model (opt-in via frontmatter `public: true`)

## Key references
- **Master-Plan:** `docs/plans/2026-05-08-living-vault-master-plan.md` (binding for multi-session work)
- **Design doc:** `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md`
- **Genese:** `~/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md`
- **Phase-1 checklist:** `docs/PHASE-1-CHECKLIST.md`

## Current status (per master-plan, 2026-05-09)
- ✅ Phase 0-7 complete (skeleton + spike, both core layers, MCP, all 3 consumers, polish)
- 🟡 **Phase 8 — Phase-1-Abschluss-Gate** in progress (awaiting user review of all three lenses)
- ⏳ Phase 9-13 (Phase 2 features + retro) pending the gate decision

## Constraints
- **Privacy gate:** privacy regression test must pass before any portfolio-sync (`Phase-1: privacy regression test for portfolio-sync` — commit 57238ba)
- **Windows quirks:** sentence-transformers verified on Windows in Phase 0 spike
- **No /dev/null in shell:** PowerShell environment — use `$null`, `$env:VAR`, backtick line continuation
- **Phase-Gate discipline:** Phase-2 features stay locked until Phase 1 is signed off

## Dependencies on the wider workspace
- Reads from `~/wiki/` (953 markdown pages, 13 top-level clusters) — this is the data the engine indexes
- Writes session-summary into `Desktop/.agent-memory/session-summary.md` (per global SESSION-WORKFLOW)
- Local memory under `Claude-Projekte/living-vault/.agent-memory/` is project-scoped state

## Commit-message convention
`living-vault | Phase-{N}: {short-status}` — `git log --grep="living-vault"` is the cross-session handoff index.
