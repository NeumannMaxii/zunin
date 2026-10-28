"""
URL configuration for Proyecto Zunin (IESETyFP Bedelía).
Arquitectura modular y desacoplada mediante include().
"""

from django.contrib import admin
from django.urls import include, path  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    # Ruta raíz principal del sistema (preparada para Dashboard Core)
    # path("", include("apps.core.urls")),
]
