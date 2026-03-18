# Memgraph vs REST validation pairs

Each file in `pairs/*.yaml` defines:

1. **Cypher** (inline or `cypher_file` under `cypher/`) against the **same Memgraph** that backs (or mirrors) the Federation API data.
2. **API** call (`method`, `path`, `query` / `body`).
3. **comparison** rule — see below.

## Environment

Set Bolt credentials (never commit):

- `MEMGRAPH_URI=bolt://host:7687` or `MEMGRAPH_HOST` + `MEMGRAPH_PORT`
- `MEMGRAPH_USER`, `MEMGRAPH_PASSWORD`

Skip when Memgraph is unreachable:

- `DATACOMNS_SKIP_MEMGRAPH_TESTS=1`

## Tags

- `smoke` — included in smoke runs (`pytest -m "memgraph_api and smoke"`).
- `regression` — broader scenarios.
- `memgraph_api` — always add for discovery.

## Comparison types

| `type` | Meaning |
|--------|---------|
| `list_length_match` | `len(Memgraph rows)` == `len(API list at api_list_path)`. |
| `api_identifiers_subset_of_graph` | Every subject identifier on the API page exists as a row in graph (org, namespace, subject_id columns). |
| `graph_min_rows_and_api_list_nonempty` | At least `min_graph_rows` graph rows and API list non-empty. |

## Cypher and schema

**You must align** node labels and properties with your Memgraph instance (e.g. Bento/CCDI curation graph). If tests fail with empty graph results, update `cypher/` queries with help from your data team.

## Run

```bash
pytest projects/federation/tests/memgraph -m "memgraph_api and smoke" -v
```
