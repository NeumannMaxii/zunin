"""
URL configuration for IESETyFP Bedelia project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("gestion_asistencia.urls")),
]
