"""
Configuración del panel de administración para el módulo de Licencias.
Gestiona el Catálogo de Tipos de Licencias y los Renglones de Planilla Mensual.
"""

from django.contrib import admin
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia


@admin.register(TipoLicencia)
class TipoLicenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "articulo",
        "descripcion",
        "cuadro_mensual",
        "hoja_pdf",
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


@admin.register(RenglonPlanillaMensual)
class RenglonPlanillaMensualAdmin(admin.ModelAdmin):
    list_display = (
        "numero_instrumento",
        "cuadro",
        "mes",
        "anio",
        "docente",
        "cargo",
        "tipo_licencia",
        "desde",
        "hasta",
        "horas_afectadas",
        "tipo_instrumento",
        "oficina",
    )
    list_filter = (
        "cuadro",
        "anio",
        "mes",
        "tipo_instrumento",
        "oficina",
    )
    search_fields = (
        "numero_instrumento",
        "docente__apellido",
        "docente__nombre",
        "docente__dni",
        "cargo__materia__nombre",
    )
    ordering = ("-anio", "-mes", "numero_instrumento")

    def has_delete_permission(self, request, obj=None):
        return False
