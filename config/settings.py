import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ON_RENDER = bool(os.getenv("RENDER"))  # Render sets RENDER=true on every service
DEBUG = os.getenv("DEBUG", "False" if ON_RENDER else "True") == "True"
SECRET_KEY = os.getenv("SECRET_KEY", "" if ON_RENDER else "dev-key")
if not SECRET_KEY: raise RuntimeError("Set the SECRET_KEY environment variable.")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*" if DEBUG else "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() if "://" in o else f"https://{o.strip()}" for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if os.getenv("RENDER_EXTERNAL_HOSTNAME"):  # the *.onrender.com address
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "django.contrib.humanize",
    "storages", "core", "dashboard", "members",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.LastSeenMiddleware",
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
DB_URL = os.getenv("DATABASE_URL", "").strip()
DATABASES = {"default": dj_database_url.parse(DB_URL or f"sqlite:///{BASE_DIR/'db.sqlite3'}", conn_max_age=60, conn_health_checks=True,
                                              ssl_require=bool(DB_URL) and os.getenv("DB_SSL", "True") == "True")}

# --- Supabase Storage bucket (S3-compatible) ---
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG
                    else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
REF = os.getenv("SUPABASE_PROJECT_REF", "")
BUCKET = os.getenv("SUPABASE_BUCKET", "nusrah-media")
if REF and os.getenv("SUPABASE_S3_KEY"):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
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
    MEDIA_URL = "/media/"; MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
LANGUAGE_CODE = "en"; TIME_ZONE = "Africa/Dar_es_Salaam"; USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTHENTICATION_BACKENDS = ["core.backends.EmailOrUsernameBackend"]
LOGIN_URL = "login"; LOGIN_REDIRECT_URL = "home"; LOGOUT_REDIRECT_URL = "home"

# --- email (password reset, admin emails). Without EMAIL_HOST, emails are printed to the log. ---
if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Sakinah <no-reply@sakinah.co.tz>")

# --- production hardening (Render terminates HTTPS in front of the app) ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}},
           "root": {"handlers": ["console"], "level": "WARNING"}}
