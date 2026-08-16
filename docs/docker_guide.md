# Docker Guide

Three services, one shared local DuckDB warehouse file mounted between
them. Everything runs with zero external dependencies or credentials by
default (`WAREHOUSE_BACKEND=duckdb`).

## Services (`docker-compose.yml`)

| Service | Image built from | Purpose | Exposed |
|---|---|---|---|
| `pipeline` | `Dockerfile` | Runs `scripts/run_pipeline.py --mode incremental` | — (writes to `data/`) |
| `dashboard` | `Dockerfile.dashboard` | Streamlit app (`dashboard/app.py`) | `localhost:8501` |
| `quality-reports` | `nginx:alpine` (no custom build) | Serves `data/profiling_reports/` as static HTML | `localhost:8080` |

Both `Dockerfile` and `Dockerfile.dashboard` are `python:3.11-slim` +
`build-essential` (needed for compiling packages like `duckdb`/`lxml`
wheels not available prebuilt for all platforms) + `requirements.txt` +
a full source copy. `Dockerfile`'s entrypoint is
`python scripts/run_pipeline.py --mode incremental`; the compose file
overrides `command` to the same thing explicitly (so it's easy to change
just in `docker-compose.yml` without touching the image). `Dockerfile.
dashboard` runs Streamlit headless on `0.0.0.0:8501` so it's reachable
from outside the container.

### Volumes and shared state

- `./data` is bind-mounted into `pipeline` read-write — this is how the
  DuckDB file at `data/serving/novamart_serving.duckdb`, the quarantine
  SQLite DB, the incremental tracker DB, and JSONL logs all persist
  across container restarts and are visible on the host.
- `./data/serving` is mounted **read-only** into `dashboard` — the
  dashboard only ever queries, never writes, the warehouse.
- `./data/profiling_reports` is mounted read-only into `quality-reports`
  (plain nginx static file serving, no app code needed).
- `./config` is mounted into `pipeline` so `config/pipeline_config.yaml`
  and `config/quality_rules.yaml` can be edited on the host and picked up
  without a rebuild.

### Service dependencies

`dashboard` and `quality-reports` both `depends_on: pipeline` — this only
controls **startup order** (pipeline's container starts first), not
"wait until the pipeline has finished a run." The dashboard has a
`healthcheck` polling Streamlit's `/_stcore/health` endpoint, so
`docker compose up` reports it as healthy once Streamlit itself is
serving — not once real data exists. On a completely fresh volume, the
dashboard will render but show empty tables until the pipeline container
completes its first run; this is expected and matches
`db_connector.py`'s designed fallback behavior (see `docs/architecture.md`).

### Environment variables

Both `pipeline` and `dashboard` read `WAREHOUSE_BACKEND` (default
`duckdb`) from the host environment via `${WAREHOUSE_BACKEND:-duckdb}` —
set it to `bigquery` or `both` (plus `BQ_PROJECT_ID`/`BQ_DATASET`/
`GOOGLE_APPLICATION_CREDENTIALS`, see `.env.example`) to enable the cloud
warehouse without touching any compose file. `pipeline` additionally
passes through `BQ_PROJECT_ID`/`BQ_DATASET`.

## Running it

```bash
# Build and start all three services (foreground, Ctrl-C to stop)
docker compose up --build

# Detached
docker compose up -d --build

# Dashboard only, e.g. against data a local (non-Docker) pipeline run already produced
docker compose up dashboard

# Tear down (keeps the ./data volume — it's a bind mount, not a named volume)
docker compose down
```

## Development overrides (`docker-compose.dev.yml`)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Additionally bind-mounts `./src`, `./scripts`, `./dashboard` into their
respective containers (on top of the base compose file's mounts), so
local code edits are picked up on container restart without a rebuild,
and sets `LOG_LEVEL=DEBUG` on both `pipeline` and `dashboard`. Use this
while iterating on pipeline or dashboard code; use the base
`docker-compose.yml` alone to test what will actually ship (baked-in code,
no live mount).

## Running a specific pipeline mode in Docker

The compose file's default `command` is `--mode incremental`. To run a
different mode (e.g. a one-off backfill) without editing the compose
file:

```bash
docker compose run --rm pipeline python scripts/run_pipeline.py --mode backfill
```

See `docs/runbook.md` for what each `--mode` does.
