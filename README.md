# living-vault

Vault engine + 3 consumers: Synesthesia (3D), Séance (chat), Living-Portfolio (site).

See `docs/plans/2026-05-08-living-vault-master-plan.md` and `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md`.

## Setup

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[embeddings,dev]"
    pytest -q
