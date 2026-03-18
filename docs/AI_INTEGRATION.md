# AI integration

The framework stays **AI-agnostic**: no LLM SDKs in core dependencies. Use these hooks:

## 1. Context bundle for prompts / RAG

```python
from framework.ai.context import build_project_context_bundle

bundle = build_project_context_bundle("federation")
# bundle["openapi_text"] — truncated OpenAPI if projects/.../contracts/openapi.json exists
# bundle["base_url"], bundle["api_prefix"]
```

Set `DATACOMNS_AI_OPENAPI_MAX_CHARS` to control truncation (default `120000`).

## 2. Suggested workflows

| Workflow | Where to plug in |
|----------|------------------|
| NL → pytest code | External script or CI job reads OpenAPI + writes `projects/<slug>/tests/generated/` |
| Semantic assertion | Mark tests `@pytest.mark.ai_assisted`; run only in optional job |
| Failure triage | Parse pytest JSON report; send to LLM with `build_project_context_bundle` |

## 3. Markers

- `ai_assisted` — opt-in suite; exclude from default `run_smoke.sh` if desired.

## 4. Avoid duplication

Generated tests should still use `api_client`, `assert_successful_json`, and `project_config` fixtures — never duplicate base URLs in generated code.
