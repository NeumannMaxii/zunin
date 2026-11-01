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
    # Catálogos Institucionales (Ticket 10.1)
    path(
        "catalogos/",
        views.CatalogosHubView.as_view(),
        name="catalogos_hub",
    ),
    path(
        "catalogos/carreras/",
        views.CarreraListView.as_view(),
        name="carrera_list",
    ),
    path(
        "catalogos/carreras/crear/",
        views.CarreraCreateView.as_view(),
        name="carrera_create",
    ),
    path(
        "catalogos/carreras/<int:pk>/editar/",
        views.CarreraUpdateView.as_view(),
        name="carrera_update",
    ),
    path(
        "catalogos/cargos/",
        views.CargoCatalogoListView.as_view(),
        name="cargocatalogo_list",
    ),
    path(
        "catalogos/cargos/crear/",
        views.CargoCatalogoCreateView.as_view(),
        name="cargocatalogo_create",
    ),
    path(
        "catalogos/cargos/<int:pk>/editar/",
        views.CargoCatalogoUpdateView.as_view(),
        name="cargocatalogo_update",
    ),
    path(
        "catalogos/autorizaciones/",
        views.TipoAutorizacionListView.as_view(),
        name="tipoautorizacion_list",
    ),
    path(
        "catalogos/autorizaciones/crear/",
        views.TipoAutorizacionCreateView.as_view(),
        name="tipoautorizacion_create",
    ),
    path(
        "catalogos/autorizaciones/<int:pk>/editar/",
        views.TipoAutorizacionUpdateView.as_view(),
        name="tipoautorizacion_update",
    ),
]
