"""
Vistas para la aplicación Asistencia.
Listados paginados y vistas de carga masiva / justificaciones (Tickets 3.8, 5 y 7).
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView
from apps.asistencia.models import RegistroAsistencia
from apps.asistencia.services import (
    guardar_asistencia_diaria_masiva,
    justificar_lote_asistencias,
)


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
