"""
Rutas URL para apps.asistencia.
"""

from django.urls import path
from . import views

app_name = "asistencia"

urlpatterns = [
    path(
        "",
        views.RegistroAsistenciaListView.as_view(),
        name="asistencia_list",
    ),
    path(
        "diaria/",
        views.AsistenciaDiariaView.as_view(),
        name="asistencia_diaria",
    ),
    path(
        "carga-masiva/",
        views.CargaDiariaMasivaView.as_view(),
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
    # Alias compatibles con dianolaborable_*
    path(
        "dias-no-laborables/",
        views.DiaNoLaborableListView.as_view(),
        name="dianolaborable_list",
    ),
    path(
        "dias-no-laborables/crear/",
        views.DiaNoLaborableCreateView.as_view(),
        name="dianolaborable_create",
    ),
    path(
        "dias-no-laborables/<int:pk>/editar/",
        views.DiaNoLaborableUpdateView.as_view(),
        name="dianolaborable_update",
    ),
    path(
        "dias-no-laborables/<int:pk>/eliminar/",
        views.DiaNoLaborableDeleteView.as_view(),
        name="dianolaborable_delete",
    ),
]
