"""
Vistas para la aplicación Personal (Docentes y Cargos).
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from apps.personal.models import CargoDocente, Docente


class DocenteListView(LoginRequiredMixin, ListView):
    """
    Vista de listado de personal docente.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = Docente
    template_name = "personal/docente_list.html"
    context_object_name = "docentes"
    paginate_by = 25
    ordering = ["apellido", "nombre"]


class CargoDocenteListView(LoginRequiredMixin, ListView):
    """
    Vista de listado de cargos y designaciones docentes.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = CargoDocente
    template_name = "personal/cargodocente_list.html"
    context_object_name = "cargos"
    paginate_by = 25
    ordering = ["docente__apellido", "docente__nombre"]
