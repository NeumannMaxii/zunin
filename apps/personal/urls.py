"""
Rutas URL para apps.personal.
"""

from django.urls import path
from . import views

app_name = "personal"

urlpatterns = [
    path("docentes/", views.DocenteListView.as_view(), name="docente_list"),
    path("cargos/", views.CargoDocenteListView.as_view(), name="cargodocente_list"),
]
