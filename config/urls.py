from django.contrib import admin
from django.contrib.auth import views as auth
from core import views_password as password_views
import os
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
password_reset = [
    path("password-reset/", password_views.password_reset, name="password_reset"),
    path("password-reset/sent/", password_views.password_reset_done, name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
urlpatterns = [path(settings.ADMIN_URL, admin.site.urls), path("dashboard/", include("dashboard.urls")),
               path("account/", include(password_reset)), path("account/", include("members.urls")), path("", include("core.urls"))]
if hasattr(settings, "MEDIA_ROOT"):  # local disk media; with Supabase Storage files are served by Supabase
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    elif getattr(settings, "SERVE_MEDIA", False):  # production without Supabase Storage: Django serves the uploads itself
        def cached_serve(request, path, **kw):   # uploads get a new name when replaced, so browsers may keep them for a week
            resp = serve(request, path, **kw)
            resp["Cache-Control"] = "public, max-age=604800"
            return resp
        urlpatterns += [re_path(r"^media/(?P<path>.*)$", cached_serve, {"document_root": settings.MEDIA_ROOT})]
