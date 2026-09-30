# Deploying to Railway

This monorepo deploys as **three Railway services** in one project:

1. **PostgreSQL** (Railway plugin/database)
2. **Backend** — Django + Gunicorn (root directory `backend/`)
3. **Frontend** — Vite build served statically (root directory `frontend/`)

No Docker required — Railway uses Nixpacks.

---

## 1. Create the project & database

1. Push this repo to GitHub.
2. Railway → **New Project** → **Deploy from GitHub repo** → select the repo.
3. In the project, **New → Database → Add PostgreSQL**. Railway creates a
   `DATABASE_URL` variable on the DB service.

---

## 2. Backend service

Add a service from the same repo and set its **Root Directory** to `backend`.

**Variables** (Service → Variables):

| Variable | Value |
|----------|-------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | a long random string (50+ chars) |
| `DATABASE_URL` | reference the Postgres service's `DATABASE_URL` (`${{Postgres.DATABASE_URL}}`) |
| `FRONTEND_URL` | the frontend service's public URL, e.g. `https://offboarding-frontend.up.railway.app` |
| `SECURE_SSL_REDIRECT` | `True` |
| `DEFAULT_FROM_EMAIL` | e.g. `offboarding@jsanconsulting.com` |
| *(email, optional)* | `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` |

`ALLOWED_HOSTS` and CSRF trusted origins are auto-derived from `RAILWAY_PUBLIC_DOMAIN`
and `FRONTEND_URL` — you don't need to set them, but you can via `ALLOWED_HOSTS`
and `CSRF_TRUSTED_ORIGINS` (comma-separated) if needed.

**Start / build**: defined in `backend/railway.json` + `backend/start.sh`. On each
deploy it runs `collectstatic`, `migrate`, `seed_initial_data`, then Gunicorn.
Health check: `/api/health/`.

**Your existing data loads automatically.** On the **first** deploy (empty DB),
`seed_initial_data` loads `backend/seed/initial_data.json` — all current employees,
users, departments, assets, offboardings, settlements, exit interviews and
notifications (1419 records). On later redeploys it detects existing data and skips,
so it never overwrites changes made in production.

- All the existing logins work as-is (e.g. HR `hr@offboarding.com` / `Hr@12345`,
  Swapna `sganapavarapu@jsanconsulting.com` / `Welcome@123`).
- To create an additional Django superuser for `/admin` (optional):
  `python manage.py createsuperuser`
- To refresh the seed later from an updated dev DB: regenerate the fixture with
  `python manage.py dumpdata accounts employees offboarding notifications documents --indent 2 > seed/initial_data.json`
  (run with `PYTHONUTF8=1` on Windows), and on Railway run
  `python manage.py seed_initial_data --force`.

---

## 3. Frontend service

Add another service from the same repo, **Root Directory** = `frontend`.

**Variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | the backend public URL **with `/api`**, e.g. `https://offboarding-backend.up.railway.app/api` |

**Build / start**: defined in `frontend/railway.json` — `npm run build`, then
`serve -s dist` on `$PORT`. (`VITE_API_URL` is baked in at build time, so redeploy
the frontend if you change it.)

---

## 4. Wire the two together

1. Deploy the **backend** first; copy its public domain.
2. Set the frontend's `VITE_API_URL` to `https://<backend-domain>/api` and deploy.
3. Set the backend's `FRONTEND_URL` to the frontend's public URL and redeploy
   (so CORS + CSRF allow it).

---

## 5. Verify

- `https://<backend>/api/health/` → `{"status": "healthy"}`
- Open the frontend URL, log in (the superuser you created, or a seeded account).

---

## Notes

- **Media / generated PDFs** are written to the container filesystem (`MEDIA_ROOT`),
  which is **ephemeral** on Railway — files are lost on redeploy. For persistent
  documents, attach a Railway **Volume** to the backend at `/app/media`, or switch
  storage to S3-compatible object storage. Documents can always be regenerated.
- **Exit reminders**: the `send_exit_reminders` command should run daily. On Railway
  use a **Cron** schedule on the backend service running
  `python manage.py send_exit_reminders` (the Windows `.bat`/Task Scheduler setup is
  local-only).
- All business dates remain manually entered; only `created_at`/`updated_at`/audit
  timestamps are automatic.
