"""
URL configuration for Proyecto Zunin (IESETyFP Bedelía).
Arquitectura modular y desacoplada mediante include().
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("personal/", include("apps.personal.urls")),
    path("asistencia/", include("apps.asistencia.urls")),
    path("licencias/", include("apps.licencias.urls")),
    path(
        "serviceworker.js",
        TemplateView.as_view(
            template_name="pwa/serviceworker.js",
            content_type="application/javascript",
        ),
        name="serviceworker",
    ),
    path(
        "manifest.json",
        TemplateView.as_view(
            template_name="pwa/manifest.json",
            content_type="application/manifest+json",
        ),
        name="manifest",
    ),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
