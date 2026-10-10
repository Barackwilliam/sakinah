from django.contrib import admin
from django.contrib.auth import views as auth
import os
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
password_reset = [
    path("password-reset/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
urlpatterns = [path("admin/", admin.site.urls), path("dashboard/", include("dashboard.urls")),
               path("account/", include(password_reset)), path("account/", include("members.urls")), path("", include("core.urls"))]
if hasattr(settings, "MEDIA_ROOT"):  # local disk media; with Supabase Storage files are served by Supabase
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    elif os.getenv("SERVE_MEDIA") == "True":  # e.g. a Render persistent disk mounted at MEDIA_ROOT
        urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
