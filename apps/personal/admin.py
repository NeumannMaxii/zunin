"""
Configuración del panel de administración para el módulo de Personal.
Gestiona Docentes, Cargos, Carreras, Espacios Curriculares y Catálogos.
"""

from django.contrib import admin
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    TipoAutorizacion,
)


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("codigo", "nombre")
    ordering = ("nombre",)


@admin.register(CargoCatalogo)
class CargoCatalogoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "activo")
    list_filter = ("activo",)
    search_fields = ("codigo", "descripcion")
    ordering = ("codigo",)


@admin.register(TipoAutorizacion)
class TipoAutorizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = (
        "apellido",
        "nombre",
        "tipo_documento",
        "dni",
        "cuil_dgi",
        "localidad",
        "total_horas_semanales",
        "activo",
    )
    list_filter = ("activo", "sexo", "estado_civil", "localidad", "provincia")
    search_fields = (
        "apellido",
        "nombre",
        "dni",
        "cuil_dgi",
        "inscripcion_dgr",
        "domicilio_calle",
    )
    ordering = ("apellido", "nombre")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EspacioCurricular)
class EspacioCurricularAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "carrera",
        "anio",
        "comision",
        "turno",
        "regimen",
        "aula",
    )
    list_filter = ("carrera", "anio", "turno", "regimen", "comision")
    search_fields = ("codigo", "nombre", "carrera", "plan_estudio", "aula")
    ordering = ("carrera", "anio", "nombre")


@admin.register(CargoDocente)
class CargoDocenteAdmin(admin.ModelAdmin):
    list_display = (
        "docente",
        "tipo_cargo",
        "materia",
        "situacion_revista",
        "carrera_ref",
        "cargo_catalogo",
        "desde_texto",
        "hasta_texto",
        "total_horas_semanales",
        "activo",
    )
    list_filter = (
        "tipo_cargo",
        "situacion_revista",
        "activo",
        "carrera_ref",
        "tipo_autorizacion",
    )
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "materia__nombre",
        "codigo_cargo",
        "codigo_motivo",
        "resolucion",
        "numero_autorizacion",
        "docente_reemplazado__apellido",
        "docente_reemplazado__nombre",
    )

    def has_delete_permission(self, request, obj=None):
        return False
