# living-vault

Vault engine + 3 consumers: Synesthesia (3D), Séance (chat), Living-Portfolio (site).

**Erst hier lesen:** [`HOW-TO-USE.md`](HOW-TO-USE.md) — Index/Wegweiser durch die drei Konsumenten, Multi-Vault-Setup, Troubleshooting.

Weiterfuehrend: `docs/plans/2026-05-08-living-vault-master-plan.md` (Master-Plan, 14 Phasen ✅) und `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md` (Architektur-Spec).

## Setup

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[embeddings,dev]"
    pytest -q
