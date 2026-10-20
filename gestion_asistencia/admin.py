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
        "docente_reemplazado",
        "total_horas_semanales",
        "codigo_cargo",
        "fecha_alta",
        "fecha_baja",
    )
    list_filter = ("tipo_cargo", "situacion_revista", "materia__carrera")
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "materia__nombre",
        "codigo_cargo",
        "codigo_motivo",
        "resolucion",
        "docente_reemplazado__apellido",
        "docente_reemplazado__nombre",
    )


@admin.register(TipoLicencia)
class TipoLicenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "articulo",
        "descripcion",
        "categoria",
        "forma_pago",
        "goce_haberes",
        "tope_anual",
        "activo",
    )
    list_filter = ("categoria", "forma_pago", "goce_haberes", "activo")
    search_fields = ("codigo", "articulo", "descripcion")


@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "fecha_hasta",
        "docente",
        "estado",
        "justifica",
        "tipo_licencia",
        "numero_disposicion",
        "horas_afectadas",
    )
    list_filter = ("estado", "justifica", "fecha", "tipo_licencia")
    search_fields = (
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "numero_disposicion",
        "observaciones",
    )
    date_hierarchy = "fecha"
