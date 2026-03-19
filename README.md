# datacomns-api-automation

Multi-project **API test framework** with shared HTTP client, config registry, smoke/regression markers, and hooks for **AI-assisted** workflows later.

---

## How it works (short)

1. **`config/projects.yaml`** lists each API **project** (slug, default base URL, env override, `/api/v1`-style prefix).
2. **`framework/`** provides **`ApiClient`**, **`ProjectConfig`**, and **response assertions** — tests never hardcode full URLs.
3. **`projects/<slug>/`** holds **one API product**: `conftest.py` sets `PROJECT_SLUG`, tests live under `tests/smoke/` and `tests/regression/`.
4. **Pytest markers**: `smoke`, `regression`, `project_federation`, `project_dcc` (add more per project).

You add **only** new test files under the right project folder; rarely touch framework code.

---

## Step-by-step: first-time setup

### 1. Create virtualenv and install

```bash
cd datacomns-api-automation
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment (optional overrides)

```bash
cp .env.example .env
# Edit .env — e.g. DATACOMNS_FEDERATION_BASE_URL=https://dcc-qa.ccdi.cancer.gov
```

`.env` is loaded automatically from the repo root before tests run.

### 3. Execute tests

| What you want | Command |
|---------------|---------|
| **Smoke suite** (Federation API) | `bash scripts/run_smoke.sh` |
| **Regression suite** | `bash scripts/run_regression.sh` |
| **All tests** | `bash scripts/run_all.sh` |
| **One test file** | `pytest projects/federation/tests/smoke/test_subject_summary_smoke.py -v` |
| **One test function** | `pytest projects/federation/tests/smoke/test_subject_summary_smoke.py::test_subject_summary_returns_json_200 -v` |

Each full run writes a single HTML file: **`reports/report_<YYYYMMDD_HHMMSS>_utc.html`** (UTC timestamp). It includes **database vs API comparison** (**PASSED** / **FAILED**), full **API** and **database** JSON in the table (up to **`DATACOMNS_REPORT_BODY_MAX_CHARS`**, default 50M per side). No `latest.html` / JSON duplicates. Disable with **`--no-datacomns-report`** or **`DATACOMNS_TEST_REPORT=0`**.

**Offline / no VPN:** config smoke still runs; live tests **fail** if the host is unreachable. To skip live HTTP:

```bash
export DATACOMNS_SKIP_LIVE_TESTS=1
pytest projects/federation -m smoke -v
```

### Memgraph + API cross-validation

Set `MEMGRAPH_URI` (or `MEMGRAPH_HOST` + `MEMGRAPH_PORT`), `MEMGRAPH_USER`, `MEMGRAPH_PASSWORD` in `.env` (see `.env.example`). Pairs live under `projects/federation/memgraph_validation/`.

```bash
pytest projects/federation/tests/memgraph -m \"memgraph_api and smoke\" -v
```

Skip without Memgraph: `export DATACOMNS_SKIP_MEMGRAPH_TESTS=1`

**Credentials / Bolt URL:** copy [`.env.example`](.env.example) to **`.env`** and set **`MEMGRAPH_PASSWORD`** (URL and user are documented in the example). See **[docs/MEMGRAPH_ENV.md](docs/MEMGRAPH_ENV.md)**.

Details: [projects/federation/memgraph_validation/README.md](projects/federation/memgraph_validation/README.md)

### DCC (Data Commons) project

Separate folder **`projects/dcc/`** — REST + Memgraph validation against the DCC QA API and **DCC Memgraph** (`MEMGRAPH_DCC_*` or shared `MEMGRAPH_*`).

| Suite | Command |
|-------|---------|
| DCC TC01 | `pytest projects/dcc/tests/api_smoke/test_DCC_TC01_verify_organizations.py -v` |
| DCC TC02 | `pytest projects/dcc/tests/api_smoke/test_DCC_TC02_verify_tumor_grade_count.py -v` |
| DCC TC03 | `pytest projects/dcc/tests/api_smoke/test_DCC_TC03_verify_file_summary.py -v` |
| DCC TC04 | `pytest projects/dcc/tests/api_smoke/test_DCC_TC04_verify_subjects_count_by_sex.py -v` |
| DCC TC05 | `pytest projects/dcc/tests/api_smoke/test_DCC_TC05_verify_namespace.py -v` |
| **DCC regression (TC01–TC05)** | `bash scripts/run_dcc_regression.sh` or `pytest projects/dcc/tests/api_smoke -m dcc_regression -v` |
| DCC Memgraph + API pairs (batch) | `bash scripts/run_dcc_memgraph_smoke.sh` |

See [projects/dcc/README.md](projects/dcc/README.md).

### 4. Optional HTML report

```bash
pip install pytest-html
pytest projects/federation -m smoke --html=report.html --self-contained-html
```

---

## Repository layout

```
datacomns-api-automation/
├── README.md                 ← this file
├── requirements.txt
├── pytest.ini                # markers, testpaths
├── .env.example
├── conftest.py               # loads .env
├── config/
│   └── projects.yaml         # ★ register every API here
├── framework/
│   ├── config/               # ProjectConfig, YAML loader
│   ├── http/                 # ApiClient (httpx)
│   ├── memgraph/             # Bolt client, pair loader, API comparison
│   ├── assertions/           # assert_successful_json, etc.
│   └── ai/                   # context bundle for LLM/RAG (no SDK)
├── projects/
│   ├── federation/           # Federation API
│   └── dcc/                  # Data Commons (DCC) API
│       ├── memgraph_validation/
│       └── tests/
│           ├── api_smoke/
│           └── memgraph_api/
├── scripts/
│   ├── run_smoke.sh
│   ├── run_regression.sh
│   ├── run_dcc_memgraph_smoke.sh
│   └── run_all.sh
└── docs/
    ├── ONBOARDING.md         # ★ newcomers start here
    ├── ADDING_NEW_PROJECT.md
    └── AI_INTEGRATION.md
```

---

## First test cases included

| Test | Marker | Needs network |
|------|--------|---------------|
| `test_federation_project_is_registered_and_has_base_url` | smoke | No |
| `test_subject_summary_returns_json_200` | smoke | Yes (`GET …/api/v1/subject/summary`) |
| `test_sample_summary_returns_json_200` | regression | Yes (`GET …/api/v1/sample/summary`) |

---

## Adding a new API project

See **[docs/ADDING_NEW_PROJECT.md](docs/ADDING_NEW_PROJECT.md)**.

Summary: new block in **`config/projects.yaml`**, copy **`projects/federation`** (or **`projects/dcc`**), set **`PROJECT_SLUG`** in **`conftest.py`**, add tests under the project’s test folders.

---

## Newcomer onboarding

Read **[docs/ONBOARDING.md](docs/ONBOARDING.md)**.

---

## AI integration (later)

Read **[docs/AI_INTEGRATION.md](docs/AI_INTEGRATION.md)**. Use `build_project_context_bundle("federation")` after placing OpenAPI under `projects/federation/contracts/openapi.json`.

---

## Environment variables

Grouped by project in **[`.env.example`](.env.example)** (Federation block, DCC block, then global toggles). Copy to **`.env`** and set passwords there.

| Area | Key vars |
|------|----------|
| Federation | `DATACOMNS_FEDERATION_BASE_URL`, `MEMGRAPH_URI`, `MEMGRAPH_USER`, `MEMGRAPH_PASSWORD` |
| DCC | `DATACOMNS_DCC_BASE_URL`, `MEMGRAPH_DCC_URI`, `MEMGRAPH_DCC_USER`, `MEMGRAPH_DCC_PASSWORD` |
| Global | `DATACOMNS_SKIP_LIVE_TESTS`, `DATACOMNS_SKIP_MEMGRAPH_*`, `DATACOMNS_HTTP_TIMEOUT` |
| Debug print | **On by default.** Set `DATACOMNS_PRINT_RESPONSES=0` or `off` to disable. Logs **API** bodies and **Memgraph** rows. **`pytest.ini` includes `-s`** so stdout is visible; use **`pytest --capture=sys`** if you need captured output. |
| Test reports | **On by default.** One **`reports/report_*_utc.html`** per run. Set **`DATACOMNS_TEST_REPORT=0`** or **`pytest --no-datacomns-report`** to disable. |

Details: **[docs/MEMGRAPH_ENV.md](docs/MEMGRAPH_ENV.md)** · AI: `DATACOMNS_AI_OPENAPI_MAX_CHARS`

---

## License

Use per your organization’s policy.
