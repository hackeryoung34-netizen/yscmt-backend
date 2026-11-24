from pathlib import Path
from datetime import timedelta
import os
import dj_database_url
# ==========================================================
# Base Directory
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# Security
# ==========================================================

DEBUG = os.environ.get("DEBUG", "False").strip().lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "local-development-only-change-before-deploy"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("SECRET_KEY must be configured in the deployment environment.")

# Frontend URL used for public certificate verification links
FRONTEND_URL = os.environ.get(
    "FRONTEND_URL",
    "http://localhost:5175",
).rstrip("/")

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "yscmt-backend.onrender.com",
    "yscmtcommunty-production.up.railway.app",
    "yscmtenterprise.ng",
    "www.yscmtenterprise.ng",
    ".vercel.app",
]
ALLOWED_HOSTS += [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

# ==========================================================
# Installed Apps
# ==========================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third Party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    # Local Apps
    "accounts",
    "student_portal.apps.StudentPortalConfig",
    "courses",
    "lessons",
    "enrollments",
    "certificates",
    "payments",
    "quizzes",
    "notifications",
    "quiz_questions",
    "quiz_attempts.apps.QuizAttemptsConfig",
    "dashboard",
    "progress",
]

# ==========================================================
# Middleware
# ==========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "yscmt.urls"

# ==========================================================
# Templates
# ==========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "yscmt.wsgi.application"

# ==========================================================
# Database
# ==========================================================

# The temporary SQLite fallback is retained only for local/legacy initialization.
# A migration preview must explicitly require a persistent PostgreSQL DATABASE_URL.
PORTAL_REQUIRE_POSTGRES = os.environ.get("PORTAL_REQUIRE_POSTGRES", "false").strip().lower() == "true"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if PORTAL_REQUIRE_POSTGRES and not DATABASE_URL:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("DATABASE_URL must point to PostgreSQL when PORTAL_REQUIRE_POSTGRES=true.")
if PORTAL_REQUIRE_POSTGRES and DATABASE_URL.lower().startswith("sqlite"):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("SQLite is disabled for Student Portal preview records; configure Neon PostgreSQL.")
DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:////tmp/yscmt-vercel-ephemeral.sqlite3"
    )
}
# ==========================================================
# Password Validation
# ==========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ==========================================================
# Internationalization
# ==========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# ==========================================================
# Static Files
# ==========================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# ==========================================================
# Media Files
# ==========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"

# ==========================================================
# Default Primary Key
# ==========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==========================================================
# Django REST Framework
# ==========================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
}

# ==========================================================
# JSON Web Tokens
# ==========================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": os.environ.get("PORTAL_JWT_SIGNING_KEY", SECRET_KEY),
}

# ==========================================================
# CORS
# ==========================================================

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    # Local development
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5177",
    "http://127.0.0.1:5177",

    # Production
    "https://yscmt-react.vercel.app",
    "https://yscmt-community.vercel.app",
]

# Allow Vercel preview deployments
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]
# ==========================================================
# CSRF
# ==========================================================

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://yscmt-react.vercel.app",
    "https://yscmt-community.vercel.app",
]

# ==========================================================
# Proxy (Production)
# ==========================================================

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==========================================================
# Upload Limits
# ==========================================================

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 100
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 100

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"
