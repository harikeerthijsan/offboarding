# Qoder Memory — Change Log

Record of all code changes made by the AI assistant in this project. Newest entries first.

---

## 2026-09-29 — Notice period form: removed explanatory notes + "(manual)" label

**Request:** Remove the "Dates are pre-filled as suggestions…" banner and the "This resignation has been approved…" card from the HR notice period form; also drop the "(manual)" suffix from the Notice Period Days field label.

**Frontend**
- `frontend/src/pages/NoticePeriodPage.tsx` — deleted both note blocks from the render; label "Notice Period Days (manual)" → "Notice Period Days". The small field hints (policy months under Expected Last Working Day, "Fill in only if…" under Early Relieving Date) were kept.

**Verification:** `npm run build` → OK.

---

## 2026-09-29 — HR notice period form: prefilled dates + optional early relieving date

**Request:** When HR accepts the resignation and starts the notice period, the form should default the start date to the employee's resignation day and the end date per the notice policy (1 month if tenure < 6 months, else 2 months), plus an optional "Early Relieving Date" field for early release.

**Approach:** The prefills are editable UI suggestions — nothing is saved until HR presses Save. The backend still never auto-fills or auto-saves business dates. The optional early relieving date reuses the existing `early_release_*` fields (no migration).

**Backend**
- `backend/apps/offboarding/models.py` — `add_months()` and `notice_months()` moved here from `views.py` (public helpers, single source of the notice policy); schema unchanged.
- `backend/apps/offboarding/views.py` — imports the helpers from `models`; new `_apply_early_relief()` records/clears an approved early release and resolves a pending early-release request; notice-period POST/PATCH pop the write-only `early_relief_date` from `validated_data`, apply it, and notify the employee; audit log includes `early_relief_date`.
- `backend/apps/offboarding/serializers.py` — read-only `notice_policy_months` on the resignation detail (server-computed from the same policy function); write-only `early_relief_date` on the notice-period create/update serializers with cross-validation (≥ start date, ≤ expected last working day; PATCH validates against the instance's stored dates).
- `backend/apps/offboarding/tests.py` — new `NoticePeriodEarlyReliefDateTest` (15 tests): create with / without / explicit-null early date; PATCH set / explicit-null clear / no-op / unrelated-key; validation 400s on create and update; PATCH resolving a pending request → ACTIVE; employee forbidden; `notice_policy_months` = 2 (long tenure) and = 1 (< 6 months, new short-tenure fixture).

**Frontend**
- `frontend/src/types/index.ts` — `ResignationRequest.notice_policy_months: number`.
- `frontend/src/services/noticePeriodService.ts` — `early_relief_date?: string | null` added to the payload type.
- `frontend/src/pages/NoticePeriodPage.tsx` — `addMonthsStr()` helper (clamps month length, mirrors backend `add_months`); `syncForm()` prefills start = resignation date, expected LWD = policy-derived end date, days = months × 30, early date = recorded value; new optional "Early Relieving Date" field; reworded info banner; "Complete Notice Period" modal falls back to the early date.

**Verification**
- `python manage.py test apps.offboarding.tests.NoticePeriodEarlyReliefDateTest` → 15/15 OK.
- Full backend suite re-run → 408 tests, all pass (includes the 15 new ones).
- `npm run build` → OK.
- Browser check (read-only) as HR on the only APPROVED resignation in the dev DB: Start 2026-09-29, Days 60, Expected 2026-11-29, Early Relieving empty, new banner shown. Edit-mode prefill path not browser-verified (no active notice periods in the dev DB; avoided mutating dev data) — covered by the new backend tests.

**Note:** `README.md` still says business dates are never prefilled/defaulted. Backend behavior is unchanged (prefills are unsaved UI suggestions); README left as-is.

---

## 2026-09-30 — Seed existing data into Railway on first deploy

**Request:** The current dev data should reflect when hosted on Railway (fresh DB).

**Approach:** Committed a Django fixture of the real data + a guarded loader that runs on deploy. Railway's Postgres starts empty, so first deploy loads it; later redeploys skip (never clobber prod).

- `backend/seed/initial_data.json` — `dumpdata accounts employees offboarding notifications documents` (1419 records: 204 users, 202 employees, 13 depts, 120 designations, 147 assets, 66 each of resignation/notice/KT/settlement/exit-interview, 327 dept clearances, 57 notifications). Generated with `PYTHONUTF8=1` (Windows dumpdata `-o` writes cp1252 → UnicodeDecodeError; redirect stdout with PYTHONIOENCODING/PYTHONUTF8 instead).
- `apps/employees/management/commands/seed_initial_data.py` — loads the fixture only if `Employee` table is empty (idempotent); `--force` to override.
- `backend/start.sh` — added `python manage.py seed_initial_data` between migrate and gunicorn.
- `DEPLOY_RAILWAY.md` — documents automatic seeding + how to refresh (`dumpdata` → `seed_initial_data --force`).

**Verification:** loaded fixture into a fresh test DB → 202 employees, 204 users, 147 assets, 66 resignations; 2nd run skipped (guard); Swapna HR login present. Fixture is not gitignored (will commit).

---

## 2026-09-30 — Railway deployment readiness

**Request:** Make the project deployable on Railway (no Docker), GitHub repo to be attached.

**Backend**
- `requirements.txt` — added `gunicorn`, `whitenoise`, `dj-database-url`, `openpyxl`.
- `config/settings/production.py` — rewritten: reads `DATABASE_URL` (dj-database-url) with DB_* fallback; auto ALLOWED_HOSTS from `RAILWAY_PUBLIC_DOMAIN` (+ env, `['*']` fallback); WhiteNoise middleware inserted after SecurityMiddleware + `CompressedManifestStaticFilesStorage` via STORAGES; CSRF_TRUSTED_ORIGINS from railway host + FRONTEND_URL; CORS += FRONTEND_URL; kept HSTS/secure-cookie/SSL-redirect headers.
- New `backend/start.sh` (collectstatic → migrate → gunicorn on $PORT), `Procfile`, `runtime.txt` (3.11.9), `railway.json` (healthcheck `/api/health/`).

**Frontend**
- `src/services/api.ts` — `baseURL = import.meta.env.VITE_API_URL || '/api'`; exported `apiBaseUrl` for raw fetch() calls.
- `documentService.downloadUrl` and `EmployeesPage` export fetch now use `apiBaseUrl`.
- New `src/vite-env.d.ts` (typed `VITE_API_URL`, fixes `import.meta.env` TS error).
- `package.json` — added `serve` dep + `start` script; new `railway.json` (build `npm run build`, serve `dist`) and `frontend/.env.example` (`VITE_API_URL`).

**Repo hygiene**
- `.gitignore` — ignore `*.log`, `import_review.csv`, `import_overrides.csv`, `.railway/`.
- New `.gitattributes` — `start.sh` forced LF (Nixpacks runs it on Linux).
- New `DEPLOY_RAILWAY.md` — 3-service guide (Postgres + backend + frontend), env vars, createsuperuser, media-volume + cron caveats.

**Verification:** `check --deploy` (production env) clean; `collectstatic` OK (161 files, manifest); frontend `npm run build` OK; dev `/api/health/` 200. Full backend suite re-run pending.

---

## 2026-09-29 — File initialized
- No code changes yet — prior project exploration was read-only.
- Convention established: every future change gets an entry here (date, files touched, what changed and why).
