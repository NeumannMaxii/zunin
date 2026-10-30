"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia


class TipoLicenciaListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para el catálogo de tipos de licencias.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = TipoLicencia
    template_name = "licencias/tipolicencia_list.html"
    context_object_name = "tipo_licencias"
    paginate_by = 25
    ordering = ["codigo"]


class RenglonPlanillaMensualListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para los renglones consolidados de planillas mensuales.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = RenglonPlanillaMensual
    template_name = "licencias/planilla_list.html"
    context_object_name = "renglones"
    paginate_by = 25
    ordering = ["-anio", "-mes", "docente__apellido"]
