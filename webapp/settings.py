"""Django settings. Business data stays in the existing SQLite file; Django keeps its own."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-change-before-hosting"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "webapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

WSGI_APPLICATION = "webapp.wsgi.application"

# Django's own tables (sessions, admin, auth later). Not the business data.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "django_internal.sqlite3",
    }
}

# The business database used by the Streamlit app and the services.
BUSINESS_DB_PATH = BASE_DIR / "cosmetics_3sim_erp.db"

LANGUAGE_CODE = "he"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = False
USE_TZ = False

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
