"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25)
y Ticket 7: Justificación Diferida y regla RN-03.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView
from apps.licencias.forms import JustificacionDiferidaForm
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


class JustificacionDiferidaView(
    LoginRequiredMixin, UserPassesTestMixin, FormView
):
    """
    Vista protegida para procesar justificaciones diferidas (Ticket 7 y RN-03).
    Permisos: Solo accesible para Admin_Institucional y Bedelia_Operadoras.
    Usuarios del grupo Consulta_Directiva o no autenticados reciben 403 Forbidden.
    """

    template_name = "licencias/justificacion_diferida.html"
    form_class = JustificacionDiferidaForm
    success_url = reverse_lazy("licencias:planilla_list")
    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["Admin_Institucional", "Bedelia_Operadoras"]
            ).exists()
            or user.has_perm("licencias.add_renglonplanillamensual")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Justificación Diferida de Inasistencias"
        context["accion"] = "Registrar Justificación"
        return context

    def form_valid(self, form):
        try:
            form.save(usuario=self.request.user)
            messages.success(
                self.request,
                "Justificación diferida procesada y registrada exitosamente.",
            )
            return super().form_valid(form)
        except Exception as exc:
            messages.error(
                self.request,
                f"Error al procesar la justificación diferida: {exc}",
            )
            return self.form_invalid(form)
