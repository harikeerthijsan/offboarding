import dj_database_url
from decouple import config

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, CORS_ALLOWED_ORIGINS

DEBUG = False

# ─── Hosts ───────────────────────────────────────────────────────────────────
# Comma-separated hosts from env, plus Railway's auto-provided public domain.
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()],
)
_railway_host = config('RAILWAY_PUBLIC_DOMAIN', default='')
if _railway_host:
    ALLOWED_HOSTS.append(_railway_host)
# Railway's healthcheck requests use this Host header.
if 'healthcheck.railway.app' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('healthcheck.railway.app')

# ─── Database ────────────────────────────────────────────────────────────────
# Railway's Postgres plugin provides DATABASE_URL. Fall back to the individual
# DB_* vars (from base settings) for local/other environments.
_database_url = config('DATABASE_URL', default='')
if _database_url:
    DATABASES = {
        'default': dj_database_url.parse(_database_url, conn_max_age=600, ssl_require=False),
    }

# ─── Static files (WhiteNoise) ───────────────────────────────────────────────
# Insert WhiteNoise right after SecurityMiddleware so it can serve collected
# static files directly from the app (no separate static host needed).
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    _idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1
    MIDDLEWARE.insert(_idx, 'whitenoise.middleware.WhiteNoiseMiddleware')

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# ─── CORS / CSRF ─────────────────────────────────────────────────────────────
# The frontend origin(s) allowed to call the API.
_frontend = config('FRONTEND_URL', default='')
if _frontend:
    CORS_ALLOWED_ORIGINS = list(CORS_ALLOWED_ORIGINS) + [_frontend]

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()],
)
if _railway_host:
    CSRF_TRUSTED_ORIGINS.append(f'https://{_railway_host}')
if _frontend and _frontend not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(_frontend)

# ─── Security headers ────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# Redirect to HTTPS; Railway's edge terminates TLS and forwards X-Forwarded-Proto.
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
