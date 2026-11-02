# WindScope

A UK wind forecast dashboard built for the REint Full Stack SWE internship challenge. It evaluates hypothetical day-ahead purchasing decisions made 1–31 January 2026. The assumed noon Europe/London decision cutoff is configurable and is not a confirmed market rule. A 31 January decision covers 1 February delivery.

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

## Deployment entry points

- **Recommended Vercel API project:** set repository root `/`, FastAPI framework, Python 3.13, root `app.py` and `requirements.txt`. Root `vercel.json` includes `backend/snapshots/**` in the function. Set `SNAPSHOT_REQUIRED=1` and `CORS_ORIGINS=https://<web-project>.vercel.app` (exact origin, without a path or trailing slash).
- **Vercel web project:** use the same repository with root `frontend/`, Vite framework and `dist` output. Set `VITE_API_BASE_URL=https://<api-project>.vercel.app/api` at build time. `VITE_` variables are public; do not place credentials there. If the web origin changes, update backend CORS and redeploy. Preview domains need explicit allowed origins.
- **Heroku alternative:** `Procfile` remains for compatibility, but Vercel is preferred for a personal, noncommercial challenge demo. The bundled read-only asset also avoids Heroku's ephemeral SQLite storage.

These are deployment configurations, not deployed services. Vercel Functions have a read-only filesystem, and the bundled snapshot removes the need for persistent database storage for this fixed historical period. Use a personal noncommercial Hobby project only within its limits. Live Vercel deployment and Docker builds have not been verified. Official references: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite), and [monorepo projects](https://vercel.com/docs/monorepos).

After public repository review and publication, the following is the intended **future** PowerShell deployment sequence from the repository root. Choose unused project names, verify Hobby/noncommercial scope, and inspect each deployment before sharing it. Both project names below derive from the same random identifier; the API is deployed first so its URL can be checked before the web build.

```powershell
npm.cmd install --global vercel
vercel login
$id = [guid]::NewGuid().ToString('N').Substring(0, 12)
$apiProject = "proj-$id-api"
$webProject = "proj-$id-web"
vercel project create $apiProject
vercel project create $webProject
vercel project update $apiProject --framework fastapi
vercel project update $webProject --framework vite
vercel link --yes --project $apiProject
vercel env add SNAPSHOT_REQUIRED production --value '1' --type config --yes
vercel env add CORS_ORIGINS production --value "https://${webProject}.vercel.app" --type config --yes
vercel deploy --prod
Invoke-RestMethod "https://${apiProject}.vercel.app/api/summary"
cd frontend
vercel link --yes --project $webProject
vercel env add VITE_API_BASE_URL production --value "https://${apiProject}.vercel.app/api" --type config --yes
vercel deploy --prod
cd ..
```

These commands use the current [Vercel CLI project](https://vercel.com/docs/cli/project), [environment variable](https://vercel.com/docs/cli/env), and [deployment](https://vercel.com/docs/cli/deploy) interfaces. If Vercel assigns a different production domain, use the actual domain in the web API base and backend CORS settings and redeploy both projects. The root and `frontend/` directories must each link to the intended project; `.vercel/` metadata stays ignored. Verify `/api/summary`, the web page, charts, filters, and browser network requests after deployment.

## Public repository handoff (do not run yet)

The assignment asks for a random-looking public repository name without identifying information. After reviewing files, `git status`, and Git author settings, PowerShell can generate one and publish when authorized:

```powershell
$repoName = 'proj-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
git add .
git commit -m "Build WindScope challenge dashboard"
gh repo create $repoName --public --source . --remote origin --push
```

These are **future instructions**; nothing has been pushed or deployed. A random repository name does not anonymize the GitHub account or commit author. Review GitHub privacy settings before publishing. Local caches, environment files, virtual environments and generated builds are excluded from Git. See [PLAN.md](PLAN.md) for status and [docs/AI_USE.md](docs/AI_USE.md) for disclosure.

