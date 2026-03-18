# DCC Memgraph vs REST validation

Memgraph connection for these pairs:

- **Preferred:** `MEMGRAPH_DCC_URI`, `MEMGRAPH_DCC_USER`, `MEMGRAPH_DCC_PASSWORD`
- **Or:** `MEMGRAPH_DCC_HOST`, `MEMGRAPH_DCC_PORT`, plus credentials above or `MEMGRAPH_USER` / `MEMGRAPH_PASSWORD`
- **Fallback:** global `MEMGRAPH_URI` / `MEMGRAPH_HOST` if DCC-specific host is unset

Skip: `DATACOMNS_SKIP_MEMGRAPH_DCC_TESTS=1` or `DATACOMNS_SKIP_MEMGRAPH_TESTS=1`

## Cypher queries (`cypher/queries.yaml`)

DCC Memgraph queries live in **[`cypher/queries.yaml`](cypher/queries.yaml)**. Use **`cypher_query_key`** like **`DCC_TC01_verify_organizations`** (pytest function name without the **`test_`** prefix). Optional **`cypher_queries_yaml: other.yaml`** if you split bundles (default is `queries.yaml`).

Federation and other projects can keep using **`cypher_file: *.cypher`** or inline **`cypher:`** in pair YAML — those remain supported.

## Comparator: `graph_institutions_subset_of_dcc_organization_api`

Memgraph rows (e.g. column `institution`) must each appear in the **union** of:

- each organization’s `name`, `identifier`
- each `metadata.institution[].value` from `GET /api/v1/organization`

Matching is **case-insensitive**.

## Comparator: `dcc_value_count_buckets_match`

Used for **GET /api/v1/sample/by/tumor_grade/count** (TC02) and **GET /api/v1/subject/by/sex/count** (TC04). API shape:

- `missing`: count of samples with no tumor grade
- `values`: `[{ "value": "<grade>", "count": N }, ...]`

Memgraph returns one row per distinct `tumor_grade` with `COUNT(DISTINCT sample_id:study_id)`; **null/empty** `value` is compared to API **`missing`**. All bucket counts must match exactly.

## Comparator: `dcc_scalar_match`

One Memgraph row with a numeric column (e.g. `total_files`) must equal an integer read from the API JSON via dotted paths (e.g. **`counts.total`** for **GET /api/v1/file/summary** — TC03).

## Comparator: `graph_study_ids_in_dcc_namespace_api` (TC05)

**GET /api/v1/namespace** returns a JSON **array** of namespace objects. Each Memgraph row supplies a study / accession string (e.g. **`namespace_name`**); that string must appear as **`id.name`** on at least one API entry. Extra namespaces in the API-only list are allowed.
