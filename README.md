# WindScope

A UK wind forecast dashboard built for the REint Full Stack SWE internship challenge. It evaluates hypothetical day-ahead purchasing decisions made 1–31 January 2026. The assumed noon Europe/London decision cutoff is configurable and is not a confirmed market rule. A 31 January decision covers 1 February delivery.

**Live deployment:** [WindScope dashboard](https://windscope-web.vercel.app) · [FastAPI backend](https://windscope-api.vercel.app) · [API summary](https://windscope-api.vercel.app/api/summary). The live frontend and summary endpoint returned HTTP 200 on 4 November 2026; the summary reported 744 matched of 1,488 expected intervals and the assumed `12:00` cutoff.

## Stack and layout

- `frontend/`: responsive React + Vite dashboard with Recharts and Lucide icons
- `backend/`: FastAPI service, explicit Elexon refresh, ignored local SQLite workspace, repository-contained read-only snapshot, and analysis endpoints
- `docs/ARCHITECTURE.md`: provenance, cutoff and matching rules, metric definitions, and limitations
- `docs/AI_USE.md`: AI-use disclosure

## Local development

Requirements: Node.js 24 (or a Vite-compatible version), npm, and Python 3.13. The verified historical snapshot in this workspace is served immediately; an Elexon refresh is not required for startup. To change Vite defaults, copy `frontend/.env.example` to `frontend/.env`. Backend settings `CORS_ORIGINS`, `DAY_AHEAD_CUTOFF_LOCAL`, and `ELEXON_CACHE_PATH` can be set in the environment; the root `.env.example` documents them. Environment files are excluded from Git and are not loaded automatically by FastAPI.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000` by default. On systems without PowerShell execution restrictions, `npm` also works.

The production API reads the bundled snapshot, not Elexon or an ephemeral SQLite file. For backend tests, run `cd backend; ..\.venv\Scripts\python.exe -m pytest -q; cd ..` (the repository root has a separate Vercel `app.py` entrypoint). For frontend checks: `cd frontend; npm.cmd run test; npm.cmd run build`. FastAPI response schemas are at `http://localhost:8000/docs`.

## Dashboard

The dashboard loads `/api/summary`, `/api/timeseries`, and `/api/accuracy` through the Vite `/api` proxy or `VITE_API_BASE_URL`. It initially shows the entire January 2026 purchase-decision range. Changing the range filters the already fetched interval series by **decision date**, while `/api/accuracy` recalculates MAE, RMSE, bias, and missing counts on the server for that selected range. The coverage percentage is matched intervals divided by expected intervals in that selection. The UI never averages daily error metrics or inserts synthetic measurements.

The actual-versus-forecast and signed-error charts show only exact-start matched pairs. The coverage panel counts the missing half-hours, and an expandable interval table shows both missing and zero values distinctly. The final January decision includes 1 February delivery. Loading, API error, no-match, and retry states are provided. The methodology panel marks the noon Europe/London cutoff as an assumption, explains publication-time selection, and warns that WINDFOR's hourly targets and FUELHH's half-hour averages limit interpretation. Source links and snapshot refresh time are shown at the bottom.

## Data refresh and API

The intentional deployment assets are [backend/snapshots/manifest.json](backend/snapshots/manifest.json) and its content-addressed gzip file (118,484 bytes). The manifest records both Elexon URLs, SHA-256, source row counts, retrieval time, and decision/delivery periods. The gzip contains real source records, including `publishTime`, `startTime`, `generation`, and daily window metadata. The loader validates the digest, provenance, row counts, required windows, and records before serving. No request or cold start contacts Elexon. Missing or corrupt assets yield HTTP 503 on analysis endpoints; `/api/health` reports process health only.

The snapshot was retrieved on **1 November 2026** using only [FUELHH WIND](https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream) and [WINDFOR](https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream). Elexon's [OpenAPI specification](https://data.elexon.co.uk/swagger/v1/swagger.json) confirms the historical publication and settlement-date filters and JSON response fields. It contains 18,688 forecast and 1,488 actual rows and, at the noon cutoff, 744 matched of 1,488 expected intervals (50% coverage), 744 missing forecasts, zero missing actuals, MAE 1,883.98 MW, RMSE 2,350.33 MW, and bias +1,685.27 MW. These numbers describe this verified snapshot; the UI renders actual API values. An hourly target is never carried forward into the next half-hour.

To refresh intentionally, run from the repository root with internet access:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.refresh
..\.venv\Scripts\python.exe -m app.snapshot_store
..\.venv\Scripts\python.exe -m pytest -q
cd ..
```

The first command fetches WINDFOR publication days 31 December 2025–31 January 2026 and FUELHH delivery days 2 January–1 February 2026 into `backend/data/elexon.sqlite3`, atomically replacing it only after all requests succeed. The ignored SQLite file is a local refresh workspace, not the production datastore. Export validates and writes a deterministic read-only asset and updated manifest. Review source counts, manifest, API summary, and changed asset before committing a refresh; retain the old asset until the new one is verified. A new deployment is needed to serve a committed update. The API prefers the bundle; setting `ELEXON_CACHE_PATH` explicitly opts into SQLite for local inspection. `SNAPSHOT_REQUIRED=1` fails closed when the bundle is absent.

The assumed purchase decision is **12:00 Europe/London** each day in January. Set `DAY_AHEAD_CUTOFF_LOCAL=HH:MM` to analyze a different cutoff and restart the API. Noon is an explicit analysis assumption because the brief does not specify a market decision time. A 31 January decision targets 1 February delivery. For each exact 30-minute UTC interval start, the backend selects the latest WINDFOR record published **at or before** the cutoff, then compares it with FUELHH WIND at the same `startTime`. No later forecast, interpolation, or synthetic value is used. WINDFOR's observed hourly target times leave every other half-hour without an exact forecast. Even matched starts compare an hourly forecast target with a half-hour actual average, so interpret these metrics as hour-start comparisons, not full half-hour forecast performance.

| Endpoint | Response |
| --- | --- |
| `GET /api/health` | Service health; does not imply cache readiness |
| `GET /api/summary` | Decision and delivery scope, source counts, coverage, accuracy, warnings |
| `GET /api/timeseries` | All expected intervals with source values, publication time, cutoff, signed error |
| `GET /api/timeseries?decision_date=2026-01-31` | One January decision's next-day intervals; out-of-scope dates return 400 |
| `GET /api/accuracy` | Matched count, missing counts, MAE, RMSE, signed bias in MW |
| `GET /api/accuracy?decision_date_from=2026-01-10&decision_date_to=2026-01-15` | Server-calculated accuracy for an inclusive January purchase-decision range |

FastAPI serves response schemas and field descriptions at `/docs` and `/openapi.json`. Signed error is forecast minus actual. MAE averages absolute errors; RMSE is the square root of mean squared errors; bias averages signed errors. All three use only non-null exact-start pairs. Missing actual and missing forecast counts are independent. No percentage error is reported because division by near-zero actual generation is unstable, and the forecast and actual feed populations may differ. See [architecture notes](docs/ARCHITECTURE.md) for duplicate, timezone, and coverage rules.

## Docker

With Docker installed, run `docker compose build`, then `docker compose up`, and open `http://localhost:8080`. The backend image includes the read-only source-backed asset and runs as a non-root user. Nginx serves the Vite build and forwards `/api` to FastAPI, so browser CORS is unnecessary. No volume or live refresh is required. **Docker has not been executed in the current environment**; image and Compose behavior still need validation on a Docker host.

## Production deployment

The running application uses two Vercel projects from the same public repository. The **API project** uses the repository root, Python 3.13, `app.py`, `requirements.txt`, and the root `vercel.json`. It serves FastAPI as one function with the versioned Elexon snapshot explicitly bundled from `backend/snapshots/**`. The **web project** uses `frontend/` as its root and serves the Vite `dist` build as static assets. The browser calls the API at the public backend origin. This fixed historical analysis needs no production database and performs no live Elexon refresh during a request or cold start.

| Vercel project | Environment variable | Production value | Status and purpose |
| --- | --- | --- | --- |
| API | `CORS_ORIGINS` | `https://windscope-web.vercel.app` | Required for browser access from the web origin; omit trailing slash and `/api` |
| Web | `VITE_API_BASE_URL` | `https://windscope-api.vercel.app/api` | Required public API base, embedded at Vite build time |
| API | `SNAPSHOT_REQUIRED` | `1` | Recommended explicit guard for the bundled source asset; Vercel already fails closed if it is missing |
| API | `DAY_AHEAD_CUTOFF_LOCAL` | `12:00` | Optional explicit setting; the code defaults to `12:00` Europe/London |

To reproduce the deployment, create or link the two Vercel projects with the roots above, set the required variables and any chosen explicit settings in each project's **Production** environment, and build/deploy the API followed by the web project. Check [`/api/summary`](https://windscope-api.vercel.app/api/summary), then the [dashboard](https://windscope-web.vercel.app), browser network requests, and a filtered accuracy view. Redeploy the affected project after changing an environment variable. Preview web domains require their own explicitly allowed API CORS origin. `VITE_` values are visible in browser code; no token or credential belongs in them. Do not set `ELEXON_CACHE_PATH` in production; the source-backed bundle is loaded directly.

The deployment follows Vercel's [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [Vite](https://vercel.com/docs/frameworks/frontend/vite), and [monorepo](https://vercel.com/docs/monorepos) guidance. A legacy `Procfile` remains for Heroku compatibility, but the verified production deployment uses Vercel.

## Challenge handoff

The public GitHub repository has the requested random-looking repository name. This README provides the live URLs, local run and test commands, data provenance, refresh procedure, API routes, metric definitions, cutoff assumption, resolution limitation, and Docker instructions. [PLAN.md](PLAN.md) tracks acceptance; [architecture notes](docs/ARCHITECTURE.md) document selection and matching rules; [AI-use disclosure](docs/AI_USE.md) describes assistance and review limits. Docker execution remains unverified because Docker is unavailable in the current environment. Provide the public repository and live dashboard/API links through the challenge's submission process.

