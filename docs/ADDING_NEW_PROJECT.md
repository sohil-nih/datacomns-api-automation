# Adding a new API project

Do **not** edit framework internals. Repeat this checklist:

## 1. Register in `config/projects.yaml`

```yaml
projects:
  my_new_api:
    display_name: "My Service"
    base_url_env: "DATACOMNS_MY_NEW_API_BASE_URL"
    default_base_url: "https://api.example.com"
    api_prefix: "/v1"
    optional_headers_env: null
    openapi_relative: "projects/my_new_api/contracts/openapi.json"
```

## 2. Copy the project folder

```bash
cp -R projects/federation projects/my_new_api
```

## 3. Update `projects/my_new_api/conftest.py`

Set:

```python
PROJECT_SLUG = "my_new_api"
```

## 4. Add tests

- `projects/my_new_api/tests/smoke/` — `@pytest.mark.smoke`
- `projects/my_new_api/tests/regression/` — `@pytest.mark.regression`
- Optional: copy `memgraph_validation/` + `tests/memgraph/` from `federation` if you use Memgraph pairs.

Use fixtures: `api_client`, `project_config`, `require_live_api`.

## 5. Document env in `.env.example`

Add `DATACOMNS_MY_NEW_API_BASE_URL=...`

## 6. Extend scripts (optional)

Add `projects/my_new_api` to `scripts/run_smoke.sh` or run:

```bash
pytest projects/my_new_api -m smoke
```

Reference layouts: **`projects/federation/`** (Federation API), **`projects/dcc/`** (Data Commons + `MEMGRAPH_DCC_*`).

## 7. Pytest markers (optional)

Add a marker in `pytest.ini` for the new project, e.g. `project_my_new_api`, and tag tests.
