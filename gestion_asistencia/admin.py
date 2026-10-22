from django.contrib import admin
from .models import (
    Docente,
    EspacioCurricular,
    Carrera,
    CargoCatalogo,
    TipoAutorizacion,
    CargoDocente,
    TipoLicencia,
    DiaNoLaborable,
    RegistroAsistencia,
)

# Personalización del Panel de Administración IESETyFP
admin.site.site_header = "IESETyFP - Bedelía y Gestión Docente"
admin.site.site_title = "IESETyFP Bedelía"
admin.site.index_title = "Panel de Administración"


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


@admin.register(DiaNoLaborable)
class DiaNoLaborableAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "descripcion", "creado_por", "creado_en")
    list_filter = ("tipo", "fecha")
    search_fields = ("descripcion",)
    ordering = ("fecha",)
    date_hierarchy = "fecha"


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


@admin.register(TipoLicencia)
class TipoLicenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "articulo",
        "descripcion",
        "cuadro_mensual",
        "categoria",
        "forma_pago",
        "goce_haberes",
        "tope_anual",
        "activo",
    )
    list_filter = (
        "cuadro_mensual",
        "categoria",
        "forma_pago",
        "goce_haberes",
        "activo",
    )
    search_fields = (
        "codigo",
        "articulo",
        "descripcion",
        "tipo_novedad_excel",
    )


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
