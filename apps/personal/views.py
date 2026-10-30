"""
Vistas para la aplicación Personal (Docentes y Cargos).
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25).
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import FormView
from apps.personal.forms import ImportarCSVForm
from apps.personal.importer import importar_legajos_csv
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


class ImportarCSVView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """
    Vista para importar docentes y cargos desde un archivo CSV.
    Acceso restringido exclusivamente a Superusuarios o usuarios
    del grupo Admin_Institucional (HTTP 403 Forbidden para otros roles).
    """

    template_name = "personal/importar_csv.html"
    form_class = ImportarCSVForm
    success_url = reverse_lazy("personal:docente_list")
    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Admin_Institucional").exists()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Importar Docentes y Cargos desde CSV"
        return context

    def form_valid(self, form):
        archivo = form.cleaned_data["archivo"]
        try:
            resumen = importar_legajos_csv(
                archivo,
                usuario=self.request.user,
                encoding="utf-8-sig",
            )
            doc_c = resumen.get("docentes_creados", 0)
            doc_a = resumen.get("docentes_actualizados", 0)
            carg_c = resumen.get("cargos_creados", 0)
            carg_a = resumen.get("cargos_actualizados", 0)
            errores = resumen.get("errores", [])

            msg = (
                f"Importación CSV procesada con éxito: "
                f"{doc_c} docente(s) creado(s), {doc_a} actualizado(s); "
                f"{carg_c} cargo(s) creado(s), {carg_a} actualizado(s)."
            )
            messages.success(self.request, msg)

            if errores:
                for err in errores[:5]:
                    messages.warning(self.request, err)

            return super().form_valid(form)
        except Exception as exc:
            messages.error(
                self.request, f"Error durante la importación: {exc}"
            )
            return self.form_invalid(form)
