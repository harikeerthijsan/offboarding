# Employee Offboarding Management

A full-stack web application for managing the complete employee exit lifecycle — from resignation submission through final exit documentation.

---

## Project Overview

This application automates and tracks the entire offboarding workflow:

```
Resignation Submission → Manager Approval → HR Review → Notice Period →
Knowledge Transfer → Asset Clearance → Department Clearance →
Finance / Final Settlement → Exit Interview → Final HR Approval →
Employee Exit → Exit Documents
```

Roles (EMPLOYEE, MANAGER, HR, IT, FINANCE, ADMIN) control access at every stage. Workflow transitions are enforced by the backend — stages cannot be skipped.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite 5, React Router v6 |
| HTTP Client | Axios (with JWT interceptor + auto-refresh) |
| Styling | Plain CSS (CSS custom properties, no Tailwind) |
| Backend | Python 3.11, Django 4.2, Django REST Framework |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Database | PostgreSQL 18 |
| Env Config | `python-decouple` |

---

## Project Structure

```
employee-offboarding/
├── frontend/                    # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/          # ProtectedRoute, Sidebar, Header
│   │   ├── contexts/            # AuthContext
│   │   ├── hooks/               # useAuth
│   │   ├── layouts/             # MainLayout
│   │   ├── pages/               # Login, Dashboard, Employees, Offboarding, Profile
│   │   ├── services/            # authService, employeeService, api.ts
│   │   ├── styles/              # global.css, layout.css, login.css
│   │   ├── types/               # TypeScript interfaces
│   │   └── utils/               # storage (localStorage helpers)
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                     # Django + DRF
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py          # Shared settings (DB, JWT, CORS, DRF)
│   │   │   ├── development.py   # DEBUG=True, localhost CORS
│   │   │   └── production.py    # DEBUG=False, env-driven hosts
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── accounts/            # Custom User model, JWT auth, role permissions
│   │   ├── employees/           # Employee + Department models
│   │   ├── offboarding/         # Phase 2 placeholder
│   │   ├── notifications/       # Phase 2 placeholder
│   │   └── audit/               # Phase 2 placeholder
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

---

## PostgreSQL Setup

1. Install PostgreSQL 18 from https://www.postgresql.org/download/
2. Start the PostgreSQL service
3. Connect and create the database:

```sql
psql -U postgres
CREATE DATABASE offboarding_db;
\q
```

---

## Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Create your environment file
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

# Edit .env and fill in your DB password and a real SECRET_KEY

# Create and apply migrations
python manage.py makemigrations accounts employees
python manage.py migrate

# (Optional) Create a Django superuser for /admin
python manage.py createsuperuser
```

---

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

---

## Environment Variables

File: `backend/.env`

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (change in production) | — |
| `DEBUG` | Enable debug mode | `True` |
| `DB_NAME` | PostgreSQL database name | `offboarding_db` |
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | — |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins | `http://localhost:5173` |
| `FRONTEND_URL` | Public frontend URL, used for "View in app" links in emails | `http://localhost:5173` |
| `EMAIL_BACKEND` | Django email backend | `…console.EmailBackend` (dev) |
| `EMAIL_HOST` | SMTP server host | — |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Use STARTTLS | `True` |
| `EMAIL_HOST_USER` | SMTP username (sending mailbox) | — |
| `EMAIL_HOST_PASSWORD` | SMTP / app password | — |
| `EMAIL_TIMEOUT` | SMTP connection timeout (seconds) | `10` |
| `DEFAULT_FROM_EMAIL` | From address on outgoing mail | `offboarding@jsanconsulting.com` |
| `NOTIFICATION_EMAILS_ENABLED` | Mirror every in-app notification to email | `True` |

---

## How to Run

### Backend

```bash
cd backend
# Windows
set DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py runserver 8000

# macOS/Linux
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver 8000
```

Backend runs at: http://localhost:8000

### Frontend

```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:5173

The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`, so no CORS issues during development.

---

## API Overview

All authenticated endpoints require the header: `Authorization: Bearer <access_token>`

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login/` | None | Login — returns access + refresh tokens + user |
| POST | `/api/auth/logout/` | Required | Logout (blacklists refresh token) |
| GET | `/api/auth/me/` | Required | Current user info |
| POST | `/api/auth/register/` | ADMIN | Create a new user with role |
| POST | `/api/auth/token/refresh/` | None | Refresh access token |

### Employees

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/employees/` | MANAGER, HR, ADMIN | List employees (supports `?search=` and `?status=`) |
| POST | `/api/employees/` | HR, ADMIN | Create employee |
| GET | `/api/employees/{id}/` | MANAGER, HR, ADMIN | Get employee detail |
| PATCH | `/api/employees/{id}/` | HR, ADMIN | Update employee |
| DELETE | `/api/employees/{id}/` | ADMIN | Delete employee |
| GET | `/api/employees/departments/` | Authenticated | List departments |
| POST | `/api/employees/departments/` | HR, ADMIN | Create department |

---

## Test Accounts

These accounts are created by the seed script and are ready to use:

| Email | Password | Role |
|-------|----------|------|
| admin@offboarding.com | Admin@123 | ADMIN |
| hr@offboarding.com | Hr@12345 | HR |
| manager@offboarding.com | Mgr@12345 | MANAGER |
| employee@offboarding.com | Emp@12345 | EMPLOYEE |

---

## Running Tests

```bash
cd backend
python manage.py test apps.accounts apps.employees --verbosity=2
```

**18 tests** covering:
- User creation and role assignment
- Login with valid/invalid credentials
- Protected endpoint access (authenticated vs unauthenticated)
- Admin-only user registration
- Role-based access control (employee cannot create employees, etc.)
- Department and Employee CRUD
- Pagination and filtering

---

## Implementation Status (Phases 1–10 complete)

| Phase | Area | Status |
|-------|------|--------|
| 1 | Foundation: auth, RBAC, employees, departments | ✅ |
| 2 | Employee/org management, audit foundation | ✅ |
| 3 | Resignation workflow (DRAFT→APPROVED) | ✅ |
| 4 | Notice period (early release, extension, completion) | ✅ |
| 5 | Knowledge transfer (projects, KT tasks, receiver/manager review) | ✅ |
| 6 | Asset & department clearance (checklists) | ✅ |
| 7 | Final settlement & exit interview | ✅ |
| 8 | HR dashboard & final offboarding approval | ✅ |
| 9 | Exit documents (PDF) & notification center | ✅ |
| 10 | Testing, security & production readiness | ✅ |

All workflow transitions are enforced by the backend; stages cannot be skipped. **All business dates are manually entered** — the system never auto-generates, defaults, or calculates a business date (only `created_at`/`updated_at`/audit timestamps are automatic).

**Test suite: 390+ automated backend tests passing.** Run the full suite with:

```bash
cd backend
python manage.py test --noinput
```

---

## Health Check

```
GET /api/health/        # public; returns {"status": "healthy"} and verifies DB connectivity
```

---

## Production Deployment (no Docker)

### Database

```sql
psql -U postgres
CREATE DATABASE offboarding_db;
CREATE USER offboarding_app WITH PASSWORD 'strong-password';
GRANT ALL PRIVILEGES ON DATABASE offboarding_db TO offboarding_app;
\q
```

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate     # (Windows: venv\Scripts\activate)
pip install -r requirements.txt
pip install gunicorn                                 # WSGI server for production

cp .env.example .env         # fill in a long random SECRET_KEY, DB creds, ALLOWED_HOSTS,
                             # CORS_ALLOWED_ORIGINS, and set DEBUG=False

export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Serve behind Nginx/Apache terminating TLS and forwarding `X-Forwarded-Proto: https`
(production settings enable HSTS, secure cookies, and SSL redirect). Serve
`STATIC_ROOT` and protect `MEDIA_ROOT` (exit documents) — media is only ever
delivered through the authenticated `/api/documents/{id}/download/` endpoint, never
as a public URL.

### Frontend

```bash
cd frontend
npm install
npm run build            # outputs dist/
# Serve dist/ via Nginx or any static host; proxy /api/* to the backend.
```

### Email / SMTP setup (notifications)

Every in-app notification (resignation, notice period, knowledge transfer, clearance,
asset declaration, settlement, exit interview, final review, documents) is **also
emailed** to the recipient. In development the console backend prints emails to the
server log; for production you must configure a real SMTP server so mail is delivered.

Set these environment variables (in `backend/.env` or your host's variables, e.g.
Railway → backend service → **Variables**):

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yourprovider.com          # see provider hosts below
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=offboarding@jsanconsulting.com   # a real, sendable mailbox
EMAIL_HOST_PASSWORD=your-smtp-or-app-password
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=offboarding@jsanconsulting.com
FRONTEND_URL=https://your-frontend-domain         # for "View in app" links
NOTIFICATION_EMAILS_ENABLED=True
```

**Provider SMTP hosts:**

| Provider | `EMAIL_HOST` | Port | Notes |
|----------|--------------|------|-------|
| Google Workspace | `smtp.gmail.com` | 587 | Requires an **App Password** (2-Step Verification on) |
| Microsoft 365 | `smtp.office365.com` | 587 | SMTP AUTH must be enabled for the mailbox |
| Company mail server | `mail.yourdomain.com` | 587 (or 465 w/ SSL) | Ask your IT team for the exact host |

Notes:
- The sending mailbox (`EMAIL_HOST_USER`) must exist and be allowed to authenticate via SMTP.
- `DEFAULT_FROM_EMAIL` should match (or be an alias of) the authenticated mailbox to avoid spam filtering.
- Delivery against a real SMTP server runs in a background thread (non-blocking) and is
  bounded by `EMAIL_TIMEOUT`; failures are logged and never break the request.
- To turn off email mirroring entirely, set `NOTIFICATION_EMAILS_ENABLED=False`
  (in-app notifications still work).
- Verify from a shell: `python manage.py shell -c "from django.core.mail import send_mail; send_mail('Test','hello','offboarding@jsanconsulting.com',['you@yourdomain.com'])"`

---

## Backup & Recovery

**Database backup (PostgreSQL):**

```bash
pg_dump -U postgres -Fc offboarding_db > offboarding_$(date +%F).dump
```

**Database restore:**

```bash
pg_restore -U postgres -d offboarding_db --clean offboarding_YYYY-MM-DD.dump
```

**Media/documents backup:** archive the `backend/media/` directory (generated exit
document PDFs) alongside each database dump so document references stay consistent.

**Recovery considerations:** take the DB dump and the media archive together (they
reference each other); schedule regular off-host backups; test restores periodically;
never run destructive DB operations without a verified recent backup.

---

## Production Checklist

- [x] Authentication (JWT) with hashed passwords, token refresh, logout
- [x] RBAC enforced on the backend for all 6 roles
- [x] Object-level authorization (IDOR-safe) on offboarding, documents, notifications
- [x] Workflow transitions backend-enforced; status not settable via payload
- [x] All business dates manual; no auto/current-date defaults
- [x] Input validation server-side (types, enums, dates, FKs, money, URLs)
- [x] Documents: secure download, release/revoke gating, no public file URLs
- [x] Audit logging for all critical actions (no secrets logged); read-only to users
- [x] Notifications delivered to correct recipients; mark-read supported
- [x] Concurrency-safe (`select_for_update` + transactions) on state transitions
- [x] Production security headers (HSTS, secure cookies, SSL redirect, XFO=DENY)
- [x] `.env.example` provided; secrets never committed; `.env` gitignored
- [x] `DEBUG=False` and env-driven `ALLOWED_HOSTS`/CORS in production
- [x] Structured logging configured
- [x] Health endpoint (`/api/health/`)
- [x] Pagination + server-side search/filter on large lists
- [x] Dashboard uses aggregate queries (no per-employee fan-out)
- [x] 390+ backend tests passing; `manage.py check --deploy` clean
- **Dashboard analytics** — average offboarding duration, bottleneck reporting
