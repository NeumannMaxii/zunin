"""
Rutas API para apps.licencias (Ticket 10).
"""

from django.urls import path
from apps.licencias.views import (
    AutocompletarLicenciaAPIView,
    CalcularFechasLicenciaAPIView,
    ValidarRegimenLicenciaAPIView,
)

app_name = "api_licencias"

urlpatterns = [
    path(
        "autocompletar/",
        AutocompletarLicenciaAPIView.as_view(),
        name="autocompletar",
    ),
    path(
        "licencias/autocompletar/",
        AutocompletarLicenciaAPIView.as_view(),
        name="licencias_autocompletar",
    ),
    path(
        "calcular-fechas/",
        CalcularFechasLicenciaAPIView.as_view(),
        name="calcular_fechas",
    ),
    path(
        "licencias/calcular-fechas/",
        CalcularFechasLicenciaAPIView.as_view(),
        name="licencias_calcular_fechas",
    ),
    path(
        "validar-regimen/",
        ValidarRegimenLicenciaAPIView.as_view(),
        name="validar_regimen",
    ),
    path(
        "licencias/validar-regimen/",
        ValidarRegimenLicenciaAPIView.as_view(),
        name="licencias_validar_regimen",
    ),
]
