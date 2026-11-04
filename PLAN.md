# WindScope implementation plan — REint challenge

Target: a focused, auditable UK wind forecast dashboard for day-ahead purchasing decisions made in January 2026. Time budget: at most 16 hours. The public repository and Vercel frontend/API are live; Docker execution and external challenge submission remain.

## Increments

1. **Scaffold (about 2 hours)** — React/Vite shell, FastAPI health endpoint, local configuration, Docker and deployment entry points, docs, smoke checks.
2. **Elexon data and decision rules (about 5 hours)** — Fetch FUELHH actual generation and WINDFOR forecasts, preserve source timestamps and provenance, define a documented day-ahead decision time, and select only a forecast published at or before each decision. Limit decisions to 1–31 January 2026. Do not substitute a later forecast when an earlier one is missing.
3. **Analysis API and UI (about 5 hours)** — Join selected forecast and actual generation by the same 30-minute settlement interval (with explicit UK timezone and DST handling), expose coverage and MAE/RMSE/bias, and show a useful decision timeline and error view. Missing observations remain missing; no fabricated points.
4. **Verification and handoff (about 4 hours)** — Add fixture-based tests for cutoff selection, boundary times, missing data, interval matching, and metrics. Inspect Docker, verify local and live workflows, finish architecture and AI-use documentation, and document deployment configuration.

## Acceptance checklist

- [x] React + Vite frontend and Python FastAPI backend scaffolded.
- [x] Backend health endpoint and frontend app shell present.
- [x] Local setup, example environment, Docker definitions, and deployment entry points documented.
- [x] Real Elexon FUELHH and WINDFOR data retrieved with source and publication timestamps retained.
- [x] All purchase decisions are in January 2026; forecast selection uses only information published at or before the assumed day-ahead decision cutoff.
- [x] Forecasts and actuals align on identical 30-minute intervals; timezone and missing data rules are explicit.
- [x] MAE, RMSE, and signed bias are computed from matched pairs only, with sample count and units exposed by the API.
- [x] Dashboard presents decision-relevant charts and coverage without invented data.
- [x] Tests cover cutoff leakage, interval matching, missing values, metrics, and API behavior.
- [x] A compact, checksum-verified Elexon source bundle is versioned with the application; production startup does not rely on an ephemeral SQLite file or live refresh.
- [x] README, architecture notes, AI-use disclosure, Docker configuration, and Vercel instructions are updated.
- [x] The random-looking public repository and Vercel frontend/API are available; the live API reports the January snapshot and 12:00 cutoff.
- [ ] Execute Docker build and Compose smoke test on a machine with Docker.
- [ ] Submit the public repository and live deployment links through the REint challenge process.

## Key design decisions

- Assumed 12:00 Europe/London purchase decision clock; configurable with `DAY_AHEAD_CUTOFF_LOCAL`. This is an analysis assumption, not a confirmed market rule.
- Official Elexon OpenAPI and live samples confirm WINDFOR `publishTime`/`startTime` and FUELHH `settlementDate`/`settlementPeriod`/`fuelType` fields.
- Daily publication/settlement windows are cached in an ignored SQLite file during explicit refresh, then exported into a versioned read-only bundle for production.

