# Reproducible pipeline image — research and implementation plan

- **Status:** proposed, not implemented
- **Date:** 2026-11-23
- **Scope:** make a fresh clone runnable for a teammate without installing Python, uv, PostgreSQL, DuckDB, or Jupyter on the host.
- **Non-goal:** put the 30M-row mirror or the 3 GB export snapshots inside the image.

## 1. Recommendation

Use **one application image plus Docker Compose**:

| Service | Image | Role |
| --- | --- | --- |
| `app` | built from this repo | Python 3.14 + uv lockfile + project dependencies + DuckDB |
| `postgres` | `postgres:17-alpine` pinned by digest | local analysis mirror (`illicit`, `licit`) |
| `jupyter` | same app image, Compose profile | JupyterLab on `127.0.0.1:8888` |

Do **not** build a single image containing PostgreSQL and the data. PostgreSQL is a server with its own lifecycle and data volume; the Python environment is a build artifact. Compose keeps them separately reproducible and lets a teammate replace one without rebuilding the other.

The image is **code and environment**, not data. Data arrives by one of:

1. ingest from the online source with `src/.env` credentials;
2. restore a `pg_dump -Fc` mirror artifact;
3. analyse the Parquet export snapshots directly with DuckDB, without PostgreSQL.

Record which one a result used. Never mix them in one table or conclusion.

## 2. Current evidence

| Fact | Value |
| --- | --- |
| Host Docker / Compose | `29.10.0` / `v5.8.0` |
| Host Python | `3.14.5`; project requires `>=3.14` |
| Host PostgreSQL | `17.12`; the host service was not accepting TCP connections during this review |
| `uv` | `0.11.14` |
| DuckDB | `2.0.1` resolves for Python 3.14; `uvx duckdb-cli` works |
| Project `.venv` | `675 MB` |
| `outputs/` | `3.0 GB`; two Parquet snapshots under `outputs/etl/load/` |
| Tracked files | `109` |

### Repo gap that blocks onboarding

At review time, `.gitignore` ignored `docs/context`, `docs/dev`, `tasks/`, `**/tests/`, and `outputs/etl/export`, so a clean clone lacked the durable decisions, task trackers, ETL tests, and technical notes that `AGENTS.md` and `README.md` point to.

That has since been narrowed: the durable docs, task trackers, and stage-level tests are tracked. Re-check `.gitignore` before building the image. Keep `src/.env`, `datasets/`, and large snapshot artifacts (`outputs/etl/load/`) untracked.

## 3. Target structure

```text
data_analysis/
  Dockerfile
  compose.yaml
  .dockerignore
  Makefile                         # optional command wrappers
  docker/
    postgres/
      init/01-schemas.sql          # CREATE SCHEMA illicit, licit; grants
  docs/
    reproducible-pipeline-image.md # this document
  src/.env.example                 # variable contract only
  outputs/                         # bind-mounted, not baked into image
```

The image installs dependencies into `/opt/venv`, **not** `/app/.venv`. This lets the repo be bind-mounted at `/app` during development without hiding the image’s environment.

## 4. Dockerfile design

Key decisions:

- Base: `python:3.14-slim` (available; `3.14.10-slim` at review time), pinned by digest for release.
- uv: copied from `ghcr.io/astral-sh/uv:0.11.14`, pinned; not `latest`.
- Dependencies: installed from `uv.lock` with `uv sync --frozen`, using a cache mount.
- Two layers: dependencies first, project second, so code edits do not reinstall NumPy/SciPy/pandas.
- `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_PROJECT_ENVIRONMENT=/opt/venv`.
- Non-root runtime user; no credentials in the image.
- `.dockerignore` excludes `.git`, `.venv`, `outputs`, `datasets`, `src/.env`, caches, and notebooks checkpoints.

Draft:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Dependency layer: only lockfile and project metadata.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

FROM python:3.14-slim AS runtime
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER app
CMD ["python", "-m", "src.scripts.etl.verify_ingestion", "--schema", "illicit", "--allow-incomplete"]
```

Notes:

- Build and test the image before trusting the dependency layer; if a package lacks a Python 3.14 wheel, add the specific build dependency to the builder stage rather than switching to the full `python:3.14` image.
- Add `duckdb` to `pyproject.toml` before the image is final. The exporter needs the Python module; `uvx duckdb-cli` is inspection-only.
- Pin the runtime base and uv image by digest for a paper snapshot, not only by tag.
- Expected image size is several hundred MB; measure it. Do not claim a size before `docker image ls`.

## 5. Compose design

Draft shape:

```yaml
name: capstone-aml

services:
  postgres:
    image: postgres:17-alpine
    env_file: src/.env
    environment:
      POSTGRES_DB: ${LOCAL_DB_NAME}
      POSTGRES_USER: ${LOCAL_DB_USER}
      POSTGRES_PASSWORD: ${LOCAL_DB_PASS}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 20s

  app:
    build: .
    env_file: src/.env
    environment:
      LOCAL_DB_HOST: postgres
    volumes:
      - .:/app
      - /app/outputs
    depends_on:
      postgres:
        condition: service_healthy
    working_dir: /app
    command: ["sleep", "infinity"]

  jupyter:
    profiles: ["jupyter"]
    build: .
    env_file: src/.env
    environment:
      LOCAL_DB_HOST: postgres
    volumes:
      - .:/app
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8888:8888"
    command: ["jupyter", "lab", "--ip=0.0.0.0", "--no-browser", "--port=8888"]

volumes:
  pgdata:
```

Important details:

- `env_file: src/.env` passes variables into the container, but `${LOCAL_DB_NAME}` interpolation in Compose is read from the Compose invocation environment. Use `docker compose --env-file src/.env ...`, or wrap commands in a `Makefile`. Do not copy the password into `compose.yaml`.
- `LOCAL_DB_HOST=postgres` overrides the host-side `localhost` value. The same `src/.env` works inside and outside containers.
- `$$` escapes the healthcheck variables so Compose does not interpolate them.
- Publish PostgreSQL only on `127.0.0.1`, and only if a host GUI/psql client is needed. Do not expose it on `0.0.0.0`.
- `depends_on` with `condition: service_healthy` is required; plain `depends_on` only waits for the container to start, not for PostgreSQL to accept connections.
- `docker compose down` keeps the named volume; `docker compose down -v` destroys the mirror. Put that warning in the README and the Makefile help.
- The bind mount `.:/app` is for development. For a frozen run, drop it and run the code baked into the image so a teammate cannot accidentally run uncommitted edits.

### Initialisation

`docker/postgres/init/01-schemas.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS illicit AUTHORIZATION current_user;
CREATE SCHEMA IF NOT EXISTS licit AUTHORIZATION current_user;
```

The official Postgres image runs this only when the data directory is empty. If `pgdata` already exists, the script does not rerun. Document that changing `LOCAL_DB_PASS` after the first start does not change the database password; use `ALTER USER` or recreate the volume.

## 6. Data strategy

### A. Ingest from the online source

```bash
docker compose --env-file src/.env run --rm app \
  python -m src.scripts.etl.extract.main --source online_db --pos-db-type illicit --schema illicit

docker compose --env-file src/.env run --rm app \
  python -m src.scripts.etl.extract.main --source online_db --pos-db-type licit --schema licit
```

Requires `ILLICIT_ONLINE_DATABASE_LINK` / `LICIT_ONLINE_DATABASE_LINK` in `src/.env`. This is the cleanest provenance, but it takes hours and depends on the source connection.

### B. Restore a mirrored dump

```bash
# On the machine that owns the mirror:
pg_dump -h localhost -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -Fc -f mirror.dump

# On the teammate machine:
docker compose --env-file src/.env exec -T postgres \
  pg_restore -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" \
  --no-owner --no-privileges < mirror.dump
```

Ship the dump outside Git, with a SHA-256 and the snapshot/run ids from `_etl_runs`. Verify with:

```bash
docker compose --env-file src/.env run --rm app \
  python -m src.scripts.etl.verify_ingestion --schema illicit
```

`pg_dump`/`pg_restore` major versions must match the server major (17).

### C. Parquet-only analysis

For H1/H3/H5 exploration and the public paper artifact, DuckDB can read `outputs/etl/load/<snapshot>/*.parquet` with no PostgreSQL. This is the cheapest teammate path, but it is read-only and cannot run the ETL or cohort writers.

## 7. Reproducibility controls

| Control | Implementation |
| --- | --- |
| Python dependencies | `uv.lock` + `uv sync --frozen`; commit the lockfile |
| Python version | `python:3.14-slim` pinned by digest |
| uv version | `ghcr.io/astral-sh/uv:0.11.14` |
| PostgreSQL | `postgres:17-alpine` pinned by digest |
| Image identity | tag `phase1-<git-sha>`; record the image digest |
| Compose config | `docker compose config` in CI or before a run |
| Build provenance | optional BuildKit SBOM/provenance; record in the paper artifact |
| Data identity | snapshot id + per-table row counts + manifest hashes; independent of image tag |

Do not use `:latest` in `compose.yaml` or the Dockerfile for a paper run. `latest` is acceptable only as a convenience alias for manual experiments, never as the recorded artifact.

## 8. Teammate onboarding target

The final README should reduce setup to:

```bash
git clone <repo>
cd data_analysis
cp src/.env.example src/.env      # fill credentials or mark "no source access"
docker compose --env-file src/.env up -d --build postgres
docker compose --env-file src/.env run --rm app \
  python -m src.scripts.etl.verify_ingestion --schema illicit --allow-incomplete
```

Then either ingest, restore a dump, or open a Parquet snapshot. Jupyter:

```bash
docker compose --env-file src/.env --profile jupyter up jupyter
```

Add a `Makefile` with short targets so nobody has to remember `--env-file`:

```make
COMPOSE := docker compose --env-file src/.env
up:      ; $(COMPOSE) up -d --build
down:    ; $(COMPOSE) down
verify:  ; $(COMPOSE) run --rm app python -m src.scripts.etl.verify_ingestion --schema illicit
shell:   ; $(COMPOSE) run --rm app bash
jupyter: ; $(COMPOSE) --profile jupyter up jupyter
```

## 9. Implementation plan

| Step | Change | Verification |
| --- | --- | --- |
| 1 | Decide tracking policy for `docs/context`, `docs/dev`, `tasks`, `**/tests` | `git ls-files` shows the contract and tests after a clean clone |
| 2 | Add `duckdb` to `pyproject.toml`; run `uv lock` | `uv sync` succeeds; `python -c "import duckdb"` |
| 3 | Add `Dockerfile`, `.dockerignore` | `docker build -t capstone-aml:dev .` succeeds |
| 4 | Add `compose.yaml`, `docker/postgres/init/01-schemas.sql` | `docker compose config` resolves; `pg_isready` passes |
| 5 | Add `Makefile` | `make up`, `make verify`, `make shell` work |
| 6 | Add `docs/dev/docker-notes.md` or link this file from `README.md` | Teammate follows only README |
| 7 | Add a smoke test: start Postgres, create a tiny fixture table, export it, open the Parquet | `test_load_export` or a compose integration check passes |
| 8 | Publish to GHCR or export a `docker save` archive | Teammate pulls by digest; `docker image inspect` matches |
| 9 | Record image digest and data snapshot in the export manifest/paper notes | The paper artifact points to both |

Do not start with step 3 before step 1. A perfectly built image from a clean clone still lacks the decision docs and tests.

## 10. Decisions needed from you

1. **Data path:** will teammates ingest online, restore a dump, or use Parquet only? This determines whether the default Compose profile starts Postgres or just the app.
2. **Image distribution:** private GHCR, public GHCR, or a `docker save` tarball? Private GHCR needs a token for teammates.
3. **Jupyter in the image:** include it in the default profile, or keep it optional? It adds image size and a second network surface.
4. **Repo tracking:** commit `docs/context`, `docs/dev`, `tasks`, and tests, or ship a separate handoff archive?
5. **Host OS support:** Linux only, or macOS/Windows too? UID/GID and bind-mount permissions differ; the `user:` mapping needs a documented default.

## 11. What this plan deliberately does not do

- No 30M-row database or 3 GB Parquet snapshot inside the image.
- No source database credentials in the image, Compose file, Git, or manifest.
- No production web serving. The web app needs a wallet-level serving table and a read-only API role, which is a separate `tasks/etl/04_web_serving.md` deliverable.
- No Kubernetes or cloud deployment. Compose on a laptop is the target.
- No automatic `docker compose down -v`. Data loss stays an explicit command.

## 12. Sources

- uv Docker guide: https://docs.astral.sh/uv/guides/integration/docker/
- uv Docker example: https://github.com/astral-sh/uv-docker-example
- Python official image tags: https://hub.docker.com/_/python
- Docker Compose startup order and healthchecks: https://docs.docker.com/compose/how-tos/startup-order/
- Docker PostgreSQL guide: https://docs.docker.com/guides/postgresql
- Docker rootless UID/GID mapping: https://docs.docker.com/engine/security/rootless/uid-gid-mapping/
