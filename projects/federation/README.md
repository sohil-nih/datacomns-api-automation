# CCDI Federation Service (example project)

- **Config:** `config/projects.yaml` → `federation`
- **Env:** `DATACOMNS_FEDERATION_BASE_URL` — host only; default QA is `https://federation-qa.ccdi.cancer.gov` (`/api/v1` from `projects.yaml`)
- **Contracts:** drop `openapi.json` under `contracts/` for schema/AI context (see `contracts/README.md`)

Tests: `tests/smoke/`, `tests/regression/`.
