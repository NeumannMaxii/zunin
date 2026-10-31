"""
Rutas URL para apps.licencias.
"""

from django.urls import path
from . import views

app_name = "licencias"

urlpatterns = [
    path(
        "tipos/",
        views.TipoLicenciaListView.as_view(),
        name="tipolicencia_list",
    ),
    path(
        "planillas/",
        views.RenglonPlanillaMensualListView.as_view(),
        name="planilla_list",
    ),
    path(
        "justificacion-diferida/",
        views.JustificacionDiferidaView.as_view(),
        name="justificacion_diferida",
    ),
    path(
        "justificar/",
        views.JustificacionDiferidaView.as_view(),
        name="justificar_alias",
    ),
]
