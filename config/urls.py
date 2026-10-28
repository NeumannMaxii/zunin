"""
URL configuration for Proyecto Zunin (IESETyFP Bedelía).
Arquitectura modular y desacoplada mediante include().
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    # Ruta raíz principal del sistema (preparada para Dashboard Core)
    # path("", include("apps.core.urls")),
]
