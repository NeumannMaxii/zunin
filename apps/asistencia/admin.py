"""
Configuración del panel de administración para el módulo de Asistencia.
Gestiona Días No Laborables y Registros Diarios de Asistencia.
"""

from django.contrib import admin
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia


@admin.register(DiaNoLaborable)
class DiaNoLaborableAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "descripcion", "creado_por", "creado_en")
    list_filter = ("tipo", "fecha")
    search_fields = ("descripcion",)
    ordering = ("fecha",)
    date_hierarchy = "fecha"


@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "fecha_hasta",
        "docente",
        "cargo",
        "estado",
        "marca_diaria",
        "oficina",
        "anio_planilla",
        "tipo_licencia",
        "justifica",
        "horas_afectadas",
    )
    list_filter = (
        "estado",
        "marca_diaria",
        "oficina",
        "anio_planilla",
        "justifica",
        "fecha",
        "tipo_licencia",
    )
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "numero_disposicion",
        "observaciones",
        "oficina",
    )
    date_hierarchy = "fecha"

    def has_delete_permission(self, request, obj=None):
        return False
