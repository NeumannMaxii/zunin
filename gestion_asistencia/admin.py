from django.contrib import admin
from .models import (
    Docente,
    EspacioCurricular,
    CargoDocente,
    TipoLicencia,
    RegistroAsistencia,
)

# Personalización del Panel de Administración IESETyFP
admin.site.site_header = "IESETyFP - Bedelía y Gestión Docente"
admin.site.site_title = "IESETyFP Bedelía"
admin.site.index_title = "Panel de Administración"


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = (
        "apellido",
        "nombre",
        "dni",
        "sexo",
        "contacto",
        "total_horas_semanales",
        "activo",
    )
    list_filter = ("activo", "sexo")
    search_fields = ("apellido", "nombre", "dni")
    ordering = ("apellido", "nombre")


@admin.register(EspacioCurricular)
class EspacioCurricularAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "carrera", "anio")
    list_filter = ("carrera", "anio")
    search_fields = ("codigo", "nombre", "carrera")
    ordering = ("carrera", "anio", "nombre")


@admin.register(CargoDocente)
class CargoDocenteAdmin(admin.ModelAdmin):
    list_display = (
        "docente",
        "materia",
        "situacion_revista",
        "total_horas_semanales",
        "resolucion",
        "fecha_alta",
    )
    list_filter = ("situacion_revista", "materia__carrera")
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "materia__nombre",
    )


@admin.register(TipoLicencia)
class TipoLicenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "articulo",
        "descripcion",
        "goce_haberes",
        "tope_anual",
        "activo",
    )
    list_filter = ("goce_haberes", "activo")
    search_fields = ("codigo", "articulo", "descripcion")


@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "docente",
        "estado",
        "tipo_licencia",
        "horas_afectadas",
    )
    list_filter = ("estado", "fecha", "tipo_licencia")
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "observaciones",
    )
    date_hierarchy = "fecha"
