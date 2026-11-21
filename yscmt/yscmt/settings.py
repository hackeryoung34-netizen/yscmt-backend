from pathlib import Path
from datetime import timedelta
import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
# ==========================================================
# Base Directory
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# Security
# ==========================================================

DEBUG = os.environ.get("DEBUG", "False").strip().lower() == "true"

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-development-only-key"
    else:
        raise ImproperlyConfigured("SECRET_KEY must be configured in production.")

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
    "yscmt-backend-v2.onrender.com",
    "yscmtcommunty-production.up.railway.app",
]
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

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

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL and not DEBUG:
    raise ImproperlyConfigured("DATABASE_URL must be configured in production.")

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}" if DEBUG else None,
        conn_max_age=600,
        ssl_require=not DEBUG,
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
    "https://yscmtenterprise.ng",
    "https://www.yscmtenterprise.ng",
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
    "https://yscmtenterprise.ng",
    "https://www.yscmtenterprise.ng",
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
