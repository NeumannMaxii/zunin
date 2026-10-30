"""
URL configuration for Proyecto Zunin (IESETyFP Bedelía).
Arquitectura modular y desacoplada mediante include().
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("personal/", include("apps.personal.urls")),
    path("asistencia/", include("apps.asistencia.urls")),
    path("licencias/", include("apps.licencias.urls")),
    path("", include("apps.core.urls")),
]
