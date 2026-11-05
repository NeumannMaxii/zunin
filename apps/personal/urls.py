"""
Rutas URL para apps.personal.
"""

from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "personal"

urlpatterns = [
    # Listado de personal docente
    path("", views.DocenteListView.as_view(), name="docente_list_root"),
    path("docentes/", views.DocenteListView.as_view(), name="docente_list"),
    # Alta de personal docente (Ticket 6 / 12.11)
    path(
        "docentes/crear/",
        views.DocenteCreateView.as_view(),
        name="docente_create",
    ),
    path(
        "crear/",
        RedirectView.as_view(
            pattern_name="personal:docente_create", permanent=True
        ),
    ),
    # Edición de personal docente (Ticket 6 / 12.11)
    path(
        "docentes/<int:pk>/editar/",
        views.DocenteUpdateView.as_view(),
        name="docente_update",
    ),
    path(
        "<int:pk>/editar/",
        RedirectView.as_view(
            pattern_name="personal:docente_update", permanent=True
        ),
    ),
    # Baja lógica de docente: POST /personal/docentes/<pk>/baja/ (Ticket 6 / 12.11)
    path(
        "docentes/<int:pk>/baja/",
        views.DocenteBajaView.as_view(),
        name="docente_baja",
    ),
    path(
        "<int:pk>/baja/",
        RedirectView.as_view(
            pattern_name="personal:docente_baja", permanent=True
        ),
    ),
    # Demás vistas existentes
    path(
        "docentes/<int:docente_id>/cargos/nuevo/",
        views.CargoDocenteCreateView.as_view(),
        name="cargo_create",
    ),
    path(
        "docentes/<int:docente_id>/cargos/crear/",
        views.CargoDocenteCreateView.as_view(),
        name="cargodocente_create",
    ),
    path(
        "cargos/nuevo/",
        views.CargoDocenteCreateView.as_view(),
        name="cargodocente_nuevo",
    ),
    path(
        "cargos/crear/",
        views.CargoDocenteCreateView.as_view(),
        name="cargodocente_crear",
    ),
    path(
        "cargos/<int:pk>/editar/",
        views.CargoDocenteUpdateView.as_view(),
        name="cargodocente_update",
    ),
    path(
        "cargos/<int:pk>/modificar/",
        views.CargoDocenteUpdateView.as_view(),
        name="cargo_update",
    ),
    path(
        "cargos/",
        views.CargoDocenteListView.as_view(),
        name="cargodocente_list",
    ),
    # Cese puntual de cargo: POST /personal/cargos/<pk>/baja/ (Ticket 10.2)
    path(
        "cargos/<int:pk>/baja/",
        views.CargoDocenteBajaView.as_view(),
        name="cargodocente_baja",
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
    path(
        "catalogos/espacios/",
        views.EspacioCurricularListView.as_view(),
        name="espaciocurricular_list",
    ),
    path(
        "catalogos/espacios/crear/",
        views.EspacioCurricularCreateView.as_view(),
        name="espaciocurricular_create",
    ),
    path(
        "catalogos/espacios/<int:pk>/editar/",
        views.EspacioCurricularUpdateView.as_view(),
        name="espaciocurricular_update",
    ),
]
