# DCC (Data Commons) API project

QA API base: `https://dcc-qa.ccdi.cancer.gov` (`/api/v1/...`).

- **DCC TC01:** `tests/api_smoke/test_DCC_TC01_verify_organizations.py`.
- **DCC TC02:** `tests/api_smoke/test_DCC_TC02_verify_tumor_grade_count.py` (`/sample/by/tumor_grade/count`).
- **DCC TC03:** `tests/api_smoke/test_DCC_TC03_verify_file_summary.py` (`/file/summary`).
- **DCC TC04:** `tests/api_smoke/test_DCC_TC04_verify_subjects_count_by_sex.py` (`/subject/by/sex/count`).
- **DCC TC05:** `tests/api_smoke/test_DCC_TC05_verify_namespace.py` (`/namespace` vs graph study ids).
- **Other REST / regression:** add under `tests/api_smoke/` or `tests/api_regression/`.
- **Memgraph vs API:** `memgraph_validation/pairs/` + `cypher/queries.yaml` — **DCC Memgraph** (`MEMGRAPH_DCC_*` or shared `MEMGRAPH_*`).
- **Regression suite (TC01–TC05):** all DCC Memgraph+API cross-checks in one run — `bash scripts/run_dcc_regression.sh` or `pytest projects/dcc/tests/api_smoke -m dcc_regression -v`. New TC tests should include `pytest.mark.dcc_regression`.

```bash
# Batch memgraph pairs (if any are not named-only)
pytest projects/dcc/tests/memgraph_api -m "memgraph_api and smoke" -v
```
