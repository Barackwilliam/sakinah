import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "storages", "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context.site",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# --- Supabase Postgres ---
DATABASES = {"default": dj_database_url.config(
    default=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR/'db.sqlite3'}"),
    conn_max_age=60, ssl_require=bool(os.getenv("DATABASE_URL")))}

# --- Supabase Storage bucket (S3-compatible) ---
REF = os.getenv("SUPABASE_PROJECT_REF", "")
BUCKET = os.getenv("SUPABASE_BUCKET", "nusrah-media")
if REF and os.getenv("SUPABASE_S3_KEY"):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
    AWS_ACCESS_KEY_ID = os.getenv("SUPABASE_S3_KEY")
    AWS_SECRET_ACCESS_KEY = os.getenv("SUPABASE_S3_SECRET")
    AWS_STORAGE_BUCKET_NAME = BUCKET
    AWS_S3_ENDPOINT_URL = f"https://{REF}.supabase.co/storage/v1/s3"
    AWS_S3_REGION_NAME = os.getenv("SUPABASE_REGION", "eu-central-1")
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_S3_CUSTOM_DOMAIN = f"{REF}.supabase.co/storage/v1/object/public/{BUCKET}"
    AWS_QUERYSTRING_AUTH = False
    AWS_DEFAULT_ACL = None
else:
    MEDIA_URL = "/media/"; MEDIA_ROOT = BASE_DIR / "media"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
LANGUAGE_CODE = "en"; TIME_ZONE = "Africa/Dar_es_Salaam"; USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
