"""
Rutas URL para apps.personal.
"""

from django.urls import path
from . import views

app_name = "personal"

urlpatterns = [
    # Listado de personal docente
    path("", views.DocenteListView.as_view(), name="docente_list_root"),
    path("docentes/", views.DocenteListView.as_view(), name="docente_list"),
    # Alta de personal docente (Ticket 6)
    path(
        "docentes/crear/",
        views.DocenteCreateView.as_view(),
        name="docente_create",
    ),
    path(
        "crear/",
        views.DocenteCreateView.as_view(),
        name="docente_create_alias",
    ),
    # Edición de personal docente (Ticket 6)
    path(
        "docentes/<int:pk>/editar/",
        views.DocenteUpdateView.as_view(),
        name="docente_update",
    ),
    path(
        "<int:pk>/editar/",
        views.DocenteUpdateView.as_view(),
        name="docente_update_alias",
    ),
    # Baja lógica de docente: POST /personal/<pk>/baja/ (Ticket 6)
    path(
        "<int:pk>/baja/",
        views.DocenteBajaView.as_view(),
        name="docente_baja",
    ),
    path(
        "docentes/<int:pk>/baja/",
        views.DocenteBajaView.as_view(),
        name="docente_baja_alias",
    ),
    # Demás vistas existentes
    path(
        "cargos/",
        views.CargoDocenteListView.as_view(),
        name="cargodocente_list",
    ),
    path(
        "importar-csv/",
        views.ImportarCSVView.as_view(),
        name="importar_csv",
    ),
]
