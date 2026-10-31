"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25),
Ticket 7: Justificación Diferida y regla RN-03, y
Ticket 8: Pantalla 2 — Catálogo Licencias con filtros por cuadro y búsqueda.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView
from apps.licencias.forms import (
    JustificacionDiferidaForm,
    TipoLicenciaSearchForm,
)
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia


class TipoLicenciaListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para el catálogo de tipos de licencias (Pantalla 2 - Ticket 8).
    Permite consultar rápidamente los códigos y artículos estatutarios con
    filtros GET por cuadro (?cuadro=IL-01 o ?cuadro=IL-02) y barra de búsqueda (?q=).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    Solo lectura (la edición sigue centralizada en el Admin institucional).
    """

    model = TipoLicencia
    template_name = "licencias/tipolicencia_list.html"
    context_object_name = "tipo_licencias"
    paginate_by = 25
    ordering = ["codigo"]

    def get_queryset(self):
        queryset = super().get_queryset()
        self.form = TipoLicenciaSearchForm(self.request.GET)
        if self.form.is_valid():
            queryset = self.form.filtrar(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuadro_param = (
            self.request.GET.get("cuadro")
            or self.request.GET.get("cuadro_mensual")
            or ""
        )
        cuadro_val = cuadro_param.strip().upper()
        q_val = self.request.GET.get("q", "").strip()

        context["form"] = getattr(
            self, "form", TipoLicenciaSearchForm(self.request.GET)
        )
        context["q"] = q_val
        context["cuadro"] = cuadro_val
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["tipo_licencias"].count()
        )
        return context


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
