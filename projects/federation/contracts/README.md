# Contracts (optional)

Place **OpenAPI** specs here for:

- Contract / schema tests (`@pytest.mark.contract`)
- AI context (`framework.ai.context.build_project_context_bundle`)

Example:

```bash
cp ~/Desktop/openapi-filtered.json ./openapi.json
```

Update `openapi_relative` in `config/projects.yaml` if you use a different filename.
