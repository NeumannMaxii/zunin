"""
Vistas para la aplicación Asistencia.
Listados paginados, ABM de Feriados (Ticket 4), carga masiva y justificaciones.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)
from apps.asistencia.forms import DiaNoLaborableForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import (
    guardar_asistencia_diaria_masiva,
    justificar_lote_asistencias,
)
from apps.core.audit import AuditoriaFormMixin


class RegistroAsistenciaListView(LoginRequiredMixin, ListView):
    """
    Listado paginado de registros de asistencia.
    Configuración obligatoria de paginate_by = 25 (Ticket 3.8).
    """

    model = RegistroAsistencia
    template_name = "asistencia/asistencia_list.html"
    context_object_name = "asistencias"
    paginate_by = 25
    ordering = ["-fecha", "docente__apellido"]


class CargaDiariaMasivaView(LoginRequiredMixin, View):
    """
    Vista para Carga Diaria Masiva de Novedades (Ticket 5 y 3.8).
    Asegura ejecución atómica con rollback total ante errores.
    """

    def get(self, request):
        return render(
            request,
            "asistencia/carga_masiva.html",
            {"titulo": "Carga Diaria Masiva de Asistencia"},
        )

    def post(self, request):
        lote_items = request.POST.getlist("items", [])
        if not lote_items:
            messages.warning(
                request, "No se recibieron datos para la carga masiva."
            )
            return redirect("asistencia:asistencia_list")

        try:
            guardar_asistencia_diaria_masiva(
                lote_items, usuario=request.user, request=request
            )
            messages.success(
                request, "Carga diaria masiva procesada correctamente."
            )
            return redirect("asistencia:asistencia_list")
        except (ValidationError, IntegrityError, Exception):
            # Error registrado en request por guardar_asistencia_diaria_masiva
            return render(
                request,
                "asistencia/carga_masiva.html",
                {"titulo": "Carga Diaria Masiva de Asistencia", "error": True},
                status=400,
            )


class JustificacionesLoteView(LoginRequiredMixin, View):
    """
    Vista para Justificaciones por Lote de Inasistencias (Ticket 7 y 3.8).
    """

    def get(self, request):
        return render(
            request,
            "asistencia/justificaciones_lote.html",
            {"titulo": "Justificaciones por Lote"},
        )

    def post(self, request):
        lote_items = request.POST.getlist("items", [])
        if not lote_items:
            messages.warning(
                request, "No se recibieron registros para justificar."
            )
            return redirect("asistencia:asistencia_list")

        try:
            justificar_lote_asistencias(
                lote_items, usuario=request.user, request=request
            )
            messages.success(
                request, "Lote de justificaciones procesado exitosamente."
            )
            return redirect("asistencia:asistencia_list")
        except (ValidationError, IntegrityError, Exception):
            return render(
                request,
                "asistencia/justificaciones_lote.html",
                {"titulo": "Justificaciones por Lote", "error": True},
                status=400,
            )


class DiaNoLaborableListView(LoginRequiredMixin, ListView):
    """
    Listado paginado de feriados, asuetos y días no laborables (Ticket 4).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = DiaNoLaborable
    template_name = "asistencia/dianolaborable_list.html"
    context_object_name = "feriados"
    paginate_by = 25
    ordering = ["-fecha"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Gestión de Feriados y Días No Laborables"
        return context


class DiaNoLaborableCreateView(LoginRequiredMixin, AuditoriaFormMixin, CreateView):
    """
    Alta de nuevo feriado o día no laborable con auditoría (Ticket 4).
    """

    model = DiaNoLaborable
    form_class = DiaNoLaborableForm
    template_name = "asistencia/dianolaborable_form.html"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Registrar Nuevo Día No Laborable"
        context["accion"] = "Crear"
        return context

    def form_valid(self, form):
        messages.success(
            self.request, "Día no laborable registrado con éxito."
        )
        return super().form_valid(form)


class DiaNoLaborableUpdateView(LoginRequiredMixin, AuditoriaFormMixin, UpdateView):
    """
    Edición de feriado o día no laborable existente con auditoría (Ticket 4).
    """

    model = DiaNoLaborable
    form_class = DiaNoLaborableForm
    template_name = "asistencia/dianolaborable_form.html"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar Día No Laborable"
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        messages.success(
            self.request, "Día no laborable modificado con éxito."
        )
        return super().form_valid(form)


class DiaNoLaborableDeleteView(LoginRequiredMixin, DeleteView):
    """
    Eliminación de un día no laborable / feriado del calendario (Ticket 4).
    """

    model = DiaNoLaborable
    template_name = "asistencia/dianolaborable_confirm_delete.html"
    context_object_name = "feriado"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Eliminar Día No Laborable"
        return context

    def form_valid(self, form):
        messages.success(
            self.request, "Día no laborable eliminado correctamente."
        )
        return super().form_valid(form)
