# Environment variables

1. Copy **`.env.example`** → **`.env`**
2. Uncomment the block for the project you run (**DCC** or **Federation**).
3. Set Bolt URL, user, and password.

| Project | REST base | Memgraph |
|---------|-----------|----------|
| **DCC** | `DATACOMNS_DCC_BASE_URL` | `MEMGRAPH_DCC_URI`, `MEMGRAPH_DCC_USER`, `MEMGRAPH_DCC_PASSWORD` |
| **Federation** | `DATACOMNS_FEDERATION_BASE_URL` | `MEMGRAPH_URI`, `MEMGRAPH_USER`, `MEMGRAPH_PASSWORD` |

If DCC Memgraph vars are unset, DCC tests fall back to `MEMGRAPH_*` (Federation Memgraph block).

Defaults for API bases are in **`config/projects.yaml`** when env vars are omitted.
