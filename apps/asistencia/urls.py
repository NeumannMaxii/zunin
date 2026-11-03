"""
Rutas URL para apps.asistencia.
"""

from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "asistencia"

urlpatterns = [
    path(
        "",
        views.RegistroAsistenciaListView.as_view(),
        name="asistencia_list",
    ),
    path(
        "consulta/",
        views.ConsultaAsistenciaView.as_view(),
        name="consulta_asistencia",
    ),
    path(
        "consultar/",
        RedirectView.as_view(
            pattern_name="asistencia:consulta_asistencia", permanent=True
        ),
    ),
    path(
        "diaria/",
        views.AsistenciaDiariaView.as_view(),
        name="asistencia_diaria",
    ),
    path(
        "carga-masiva/",
        RedirectView.as_view(
            pattern_name="asistencia:asistencia_diaria", permanent=True
        ),
        name="carga_masiva",
    ),
    path(
        "justificaciones-lote/",
        views.JustificacionesLoteView.as_view(),
        name="justificaciones_lote",
    ),
    # ABM de Feriados y Días No Laborables (Ticket 4)
    path(
        "feriados/",
        views.DiaNoLaborableListView.as_view(),
        name="feriado_list",
    ),
    path(
        "feriados/crear/",
        views.DiaNoLaborableCreateView.as_view(),
        name="feriado_create",
    ),
    path(
        "feriados/<int:pk>/editar/",
        views.DiaNoLaborableUpdateView.as_view(),
        name="feriado_update",
    ),
    path(
        "feriados/<int:pk>/eliminar/",
        views.DiaNoLaborableDeleteView.as_view(),
        name="feriado_delete",
    ),
    # Redirecciones 301 para rutas legadas dias-no-laborables/* (Ticket 12.11)
    path(
        "dias-no-laborables/",
        RedirectView.as_view(
            pattern_name="asistencia:feriado_list", permanent=True
        ),
    ),
    path(
        "dias-no-laborables/crear/",
        RedirectView.as_view(
            pattern_name="asistencia:feriado_create", permanent=True
        ),
    ),
    path(
        "dias-no-laborables/<int:pk>/editar/",
        RedirectView.as_view(
            pattern_name="asistencia:feriado_update", permanent=True
        ),
    ),
    path(
        "dias-no-laborables/<int:pk>/eliminar/",
        RedirectView.as_view(
            pattern_name="asistencia:feriado_delete", permanent=True
        ),
    ),
]
