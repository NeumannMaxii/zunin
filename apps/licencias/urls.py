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
        "planillas/exportar-csv/",
        views.ExportarPlanillaCSVView.as_view(),
        name="exportar_planilla_csv",
    ),
    path(
        "planillas/csv/",
        views.ExportarPlanillaCSVView.as_view(),
        name="planilla_csv",
    ),
    path(
        "planillas/<int:pk>/cambiar-licencia/",
        views.CambiarLicenciaRenglonView.as_view(),
        name="renglon_cambiar_licencia",
    ),
    path(
        "planillas/<int:pk>/editar-articulo/",
        views.CambiarLicenciaRenglonView.as_view(),
        name="renglon_editar_articulo",
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
    # API Autocompletado de Licencias (Ticket 10)
    path(
        "api/autocompletar/",
        views.AutocompletarLicenciaAPIView.as_view(),
        name="api_autocompletar",
    ),
    path(
        "autocompletar/",
        views.AutocompletarLicenciaAPIView.as_view(),
        name="autocompletar",
    ),
]
