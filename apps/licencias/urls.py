"""
Rutas URL para apps.licencias.
"""

from django.urls import path
from django.views.generic import RedirectView
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
        "planillas/exportar/",
        RedirectView.as_view(
            pattern_name="licencias:exportar_planilla_csv", permanent=True
        ),
    ),
    path(
        "planillas/csv/",
        RedirectView.as_view(
            pattern_name="licencias:exportar_planilla_csv", permanent=True
        ),
    ),
    path(
        "planillas/<int:pk>/cambiar-licencia/",
        views.CambiarLicenciaRenglonView.as_view(),
        name="renglon_cambiar_licencia",
    ),
    path(
        "planillas/<int:pk>/editar-articulo/",
        RedirectView.as_view(
            pattern_name="licencias:renglon_cambiar_licencia", permanent=True
        ),
    ),
    path(
        "planillas/<int:pk>/instrumento/",
        views.CambiarLicenciaRenglonView.as_view(),
        name="renglon_actualizar_instrumento",
    ),
    path(
        "justificacion-diferida/",
        views.JustificacionDiferidaView.as_view(),
        name="justificacion_diferida",
    ),
    path(
        "justificar/",
        RedirectView.as_view(
            pattern_name="licencias:justificacion_diferida", permanent=True
        ),
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
    # API Cálculo de Fechas y Reintegro (Ticket 16.2)
    path(
        "api/calcular-fechas/",
        views.CalcularFechasLicenciaAPIView.as_view(),
        name="api_calcular_fechas",
    ),
    path(
        "calcular-fechas/",
        views.CalcularFechasLicenciaAPIView.as_view(),
        name="calcular_fechas",
    ),
    # API Validación de Régimen de Revista (Ticket 17.1)
    path(
        "api/validar-regimen/",
        views.ValidarRegimenLicenciaAPIView.as_view(),
        name="api_validar_regimen",
    ),
    path(
        "validar-regimen/",
        views.ValidarRegimenLicenciaAPIView.as_view(),
        name="validar_regimen",
    ),
    # Solicitudes y Otorgamientos (Ticket 16.1 / 17.1)
    path(
        "solicitudes/",
        views.LicenciaOtorgadaListView.as_view(),
        name="licenciaotorgada_list",
    ),
    path(
        "solicitudes/nueva/",
        views.LicenciaOtorgadaCreateView.as_view(),
        name="licenciaotorgada_create",
    ),
]
