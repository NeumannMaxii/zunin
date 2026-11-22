"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa:
- Ticket 3.8: Paginación obligatoria (paginate_by = 25).
- Ticket 7: Justificación Diferida y regla RN-03.
- Ticket 8: Pantalla 2 — Catálogo Licencias con filtros y búsqueda.
- Ticket 9: Pantalla Mensual (Planillas), exportación CSV y cambio de artículo
  preservando número de instrumento.
- Ticket 18.5: Exportación Oficial a Excel (.xlsx) Formateado según IL-01 e IL-02.
"""

import csv
import datetime
import io
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView
from apps.core.audit import audit_save
from apps.core.mixins import PermisosEstrictosMixin
from apps.licencias.calculador import calcular_fechas_licencia
from apps.licencias.forms import (
    JustificacionDiferidaForm,
    LicenciaOtorgadaForm,
    TipoLicenciaSearchForm,
)
from apps.licencias.models import (
    LicenciaOtorgada,
    RenglonPlanillaMensual,
    TipoLicencia,
)


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
        regimen_param = self.request.GET.get("regimen", "")
        regimen_val = regimen_param.strip().upper()
        q_val = self.request.GET.get("q", "").strip()

        context["form"] = getattr(
            self, "form", TipoLicenciaSearchForm(self.request.GET)
        )
        context["q"] = q_val
        context["cuadro"] = cuadro_val
        context["regimen"] = regimen_val
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["tipo_licencias"].count()
        )
        context["sugerencias"] = TipoLicencia.objects.filter(activo=True).values_list(
            "codigo", "articulo", "descripcion"
        )
        return context


class RenglonPlanillaMensualListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para los renglones consolidados de planillas mensuales (Ticket 9).
    Permite visualizar los cuadros IL-01 e IL-02 con selector de edición de tipo de
    licencia por renglón y exportación directa a CSV.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = RenglonPlanillaMensual
    template_name = "licencias/planilla_list.html"
    context_object_name = "renglones"
    paginate_by = 25
    ordering = [
        "-anio",
        "-mes",
        "cuadro",
        "numero_instrumento",
        "docente__apellido",
    ]

    def get_queryset(self):
        queryset = RenglonPlanillaMensual.objects.vigentes().select_related(
            "docente",
            "cargo__materia",
            "cargo__cargo_catalogo",
            "tipo_licencia",
        )
        cuadro = (self.request.GET.get("cuadro") or "").strip().upper()
        if cuadro in ["IL-01", "IL-02"]:
            queryset = queryset.filter(cuadro=cuadro)

        mes = self.request.GET.get("mes")
        if mes and str(mes).isdigit():
            queryset = queryset.filter(mes=int(mes))

        anio = self.request.GET.get("anio")
        if anio and str(anio).isdigit():
            queryset = queryset.filter(anio=int(anio))

        return queryset

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv" or request.GET.get("format") == "csv":
            export_view = ExportarPlanillaCSVView.as_view()
            return export_view(request, *args, **kwargs)
        if request.GET.get("export") in [
            "excel",
            "xlsx",
        ] or request.GET.get("format") in ["excel", "xlsx"]:
            export_view = ExportarPlanillaExcelView.as_view()
            return export_view(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        renglon_id = (
            request.POST.get("renglon_id")
            or request.POST.get("id")
            or request.POST.get("pk")
        )
        if renglon_id:
            view = CambiarLicenciaRenglonView.as_view()
            return view(request, pk=renglon_id)
        return redirect("licencias:planilla_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuadro_actual = (self.request.GET.get("cuadro") or "").strip().upper()
        context["cuadro_actual"] = cuadro_actual
        context["mes_actual"] = self.request.GET.get("mes", "")
        context["anio_actual"] = self.request.GET.get("anio", "")
        context["tipos_licencia"] = TipoLicencia.objects.filter(activo=True).order_by(
            "cuadro_mensual", "codigo"
        )
        context["total_il01"] = (
            RenglonPlanillaMensual.objects.vigentes().filter(cuadro="IL-01").count()
        )
        context["total_il02"] = (
            RenglonPlanillaMensual.objects.vigentes().filter(cuadro="IL-02").count()
        )
        return context


class ExportarPlanillaCSVView(LoginRequiredMixin, View):
    """
    Ticket 9: Exportación de Planilla Mensual Consolidada a CSV.
    Columnas exactas requeridas:
    Cuadro, N° Disposición, Docente, DNI, Desde, Hasta, Materias, Horas, Tipo Licencia
    """

    def get(self, request, *args, **kwargs):
        queryset = (
            RenglonPlanillaMensual.objects.vigentes()
            .select_related(
                "docente",
                "cargo__materia",
                "cargo__cargo_catalogo",
                "tipo_licencia",
            )
            .order_by(
                "-anio",
                "-mes",
                "cuadro",
                "numero_instrumento",
                "docente__apellido",
            )
        )

        cuadro = (request.GET.get("cuadro") or "").strip().upper()
        if cuadro in ["IL-01", "IL-02"]:
            queryset = queryset.filter(cuadro=cuadro)

        mes = request.GET.get("mes")
        if mes and str(mes).isdigit():
            queryset = queryset.filter(mes=int(mes))

        anio = request.GET.get("anio")
        if anio and str(anio).isdigit():
            queryset = queryset.filter(anio=int(anio))

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"planillas_{cuadro.lower() if cuadro else 'mensuales'}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Inyectar BOM de UTF-8 (\ufeff) para compatibilidad con Microsoft Excel
        response.write("\ufeff")

        writer = csv.writer(response)
        headers = [
            "Cuadro",
            "N° Disposición",
            "Docente",
            "DNI",
            "Desde",
            "Hasta",
            "Materias",
            "Horas",
            "Tipo Licencia",
        ]
        writer.writerow(headers)

        for r in queryset:
            materia_str = ""
            if r.cargo:
                if r.cargo.materia and r.cargo.materia.nombre:
                    materia_str = r.cargo.materia.nombre
                elif r.cargo.cargo_catalogo and r.cargo.cargo_catalogo.descripcion:
                    materia_str = r.cargo.cargo_catalogo.descripcion
                else:
                    materia_str = str(r.cargo)

            tipo_lic_str = r.tipo_licencia.codigo if r.tipo_licencia else ""

            # Ticket 10.3: Si es Resolución Ministerial, reflejar "Resolución"
            # con su número oficial
            if r.tipo_instrumento == "RESOLUCION":
                num_inst = (r.numero_instrumento or "").strip()
                num_lower = num_inst.lower()
                if "resolución" in num_lower or "resolucion" in num_lower:
                    instrumento_str = num_inst
                elif num_lower.startswith("res.") or num_lower.startswith("res "):
                    instrumento_str = f"Resolución {num_inst[4:].strip()}".strip()
                else:
                    instrumento_str = f"Resolución {num_inst}".strip()
            else:
                instrumento_str = r.numero_instrumento or ""

            fila = [
                r.cuadro,
                instrumento_str,
                r.docente.nombre_completo,
                r.docente.dni,
                r.desde.strftime("%d/%m/%Y") if r.desde else "",
                r.hasta.strftime("%d/%m/%Y") if r.hasta else "",
                materia_str,
                r.horas_afectadas,
                tipo_lic_str,
            ]
            writer.writerow(fila)

        return response


MESES_NOMBRES_OFICIALES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

COLUMNAS_EXCEL_BEDELIA = [
    "D.N.I",
    "APELLIDO Y NOMBRE",
    "SEXO",
    "SIT. DE REVISTA",
    "COD. DE CARGOS",
    "DESCRIPCIÓN DE CARGOS",
    "HORAS",
    "COD. LIC.",
    "ART.",
    "TIPO INSTRUMENTO",
    "OFICINA",
    "N° INSTRUMENTO",
    "AÑO",
    "DESDE",
    "HASTA",
]


def construir_libro_excel_planillas(
    renglones_il01,
    renglones_il02,
    mes,
    anio,
    oficina="1452",
):
    """
    Construye un libro de cálculo openpyxl estructurado en dos secciones:
    IL-01 (Salud arriba) e IL-02 (Otros / Permisos abajo) con membretes
    institucionales y espaciador intermedio (Ticket 18.5).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Planilla {mes}_{anio}"[:31]

    if str(mes).isdigit() and int(mes) in MESES_NOMBRES_OFICIALES:
        mes_nombre = MESES_NOMBRES_OFICIALES[int(mes)]
    else:
        mes_nombre = str(mes).upper()

    font_sello = Font(name="Calibri", size=9, bold=True, color="475569")
    font_titulo_il01 = Font(name="Calibri", size=12, bold=True, color="0369A1")
    font_titulo_il02 = Font(name="Calibri", size=12, bold=True, color="4338CA")
    font_meta_label = Font(name="Calibri", size=9, bold=True, color="334155")
    font_meta_val = Font(name="Calibri", size=9, color="0F172A")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=9, color="1E293B")
    font_empty = Font(name="Calibri", size=9, italic=True, color="64748B")

    fill_header_il01 = PatternFill(
        start_color="0369A1", end_color="0369A1", fill_type="solid"
    )
    fill_header_il02 = PatternFill(
        start_color="4338CA", end_color="4338CA", fill_type="solid"
    )

    thin_side = Side(border_style="thin", color="CBD5E1")
    border_cell = Border(
        left=thin_side, right=thin_side, top=thin_side, bottom=thin_side
    )
    border_header = Border(
        left=Side(border_style="thin", color="94A3B8"),
        right=Side(border_style="thin", color="94A3B8"),
        top=Side(border_style="thin", color="94A3B8"),
        bottom=Side(border_style="medium", color="0F172A"),
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

    inst_educativa = (
        "INSTITUTO DE EDUCACIÓN SUPERIOR DE EDUCACIÓN TÉCNICA "
        "Y FORMACIÓN PROFESIONAL"
    )
    oficina_val = int(oficina) if str(oficina).isdigit() else oficina

    membrete_rows = set()

    def escribir_bloque(fila_inicio, titulo, font_titulo, fill_header, renglones):
        r = fila_inicio

        # Membrete Fila 1: Sello Regional y Título de Sección
        ws.cell(row=r, column=1, value="SELLO REGIONAL").font = font_sello
        ws.cell(row=r, column=1).alignment = align_center

        cell_tit = ws.cell(row=r, column=2, value=titulo)
        cell_tit.font = font_titulo
        cell_tit.alignment = align_left
        membrete_rows.add(r)

        # Membrete Fila 2: Mes, Código y Unidad Educativa
        ws.cell(row=r + 1, column=2, value=f"MES: {mes_nombre}").font = font_meta_label
        ws.cell(row=r + 1, column=4, value="CÓDIGO").font = font_meta_label
        ws.cell(row=r + 1, column=6, value="CÓDIGO").font = font_meta_label
        ws.cell(row=r + 1, column=8, value="UNIDAD EDUCATIVA").font = font_meta_label
        membrete_rows.add(r + 1)

        # Membrete Fila 3: Año, Número de Oficina, Anexo e Institución
        ws.cell(row=r + 2, column=2, value=f"AÑO: {anio}").font = font_meta_label
        ws.cell(row=r + 2, column=4, value="DE OFICINA:").font = font_meta_label
        ws.cell(row=r + 2, column=5, value=oficina_val).font = font_meta_val
        ws.cell(row=r + 2, column=6, value="ANEXO:").font = font_meta_label
        ws.cell(row=r + 2, column=7, value=0).font = font_meta_val
        cell_inst = ws.cell(row=r + 2, column=8, value=inst_educativa)
        cell_inst.font = font_meta_val
        membrete_rows.add(r + 2)

        # Membrete Fila 4: Sello ASN
        ws.cell(
            row=r + 3, column=1, value="A.S. Nº (------_-------_-------)"
        ).font = font_meta_label
        membrete_rows.add(r + 3)

        # Fila 5: Cabecera estilizada de la tabla
        r_header = r + 4
        ws.row_dimensions[r_header].height = 26
        for idx, col_name in enumerate(COLUMNAS_EXCEL_BEDELIA, start=1):
            c = ws.cell(row=r_header, column=idx, value=col_name)
            c.font = font_header
            c.fill = fill_header
            c.alignment = align_header
            c.border = border_header

        # Filas de datos
        r_actual = r_header + 1
        if not renglones:
            ws.cell(
                row=r_actual,
                column=2,
                value="Sin novedades registradas para este cuadro en el período.",
            ).font = font_empty
            for c_idx in range(1, len(COLUMNAS_EXCEL_BEDELIA) + 1):
                ws.cell(row=r_actual, column=c_idx).border = border_cell
            r_actual += 1
        else:
            for item in renglones:
                sit = ""
                cod_cargo = ""
                desc_cargo = ""
                if item.cargo:
                    if item.cargo.situacion_revista:
                        s_rev = str(item.cargo.situacion_revista).upper()
                        if "TIT" in s_rev:
                            sit = "TIT"
                        elif "INT" in s_rev:
                            sit = "INT"
                        elif "SUP" in s_rev:
                            sit = "SUP"
                        else:
                            sit = item.cargo.situacion_revista
                    if item.cargo.codigo_cargo:
                        cod_cargo = str(item.cargo.codigo_cargo)
                    elif (
                        item.cargo.cargo_catalogo
                        and item.cargo.cargo_catalogo.codigo
                    ):
                        cod_cargo = str(item.cargo.cargo_catalogo.codigo)
                    if item.cargo.materia and item.cargo.materia.nombre:
                        desc_cargo = item.cargo.materia.nombre
                    elif (
                        item.cargo.cargo_catalogo
                        and item.cargo.cargo_catalogo.descripcion
                    ):
                        desc_cargo = item.cargo.cargo_catalogo.descripcion
                    else:
                        desc_cargo = str(item.cargo)

                cod_lic = (
                    item.tipo_licencia.codigo
                    if item.tipo_licencia
                    else (item.marca_origen or "")
                )
                art_lic = (
                    item.tipo_licencia.articulo if item.tipo_licencia else ""
                )
                tipo_inst = (
                    "RESOLUCIÓN"
                    if item.tipo_instrumento == "RESOLUCION"
                    else "DISPOSICIÓN"
                )
                num_inst = item.numero_instrumento or ""
                desde_str = (
                    item.desde.strftime("%d/%m/%Y") if item.desde else ""
                )
                hasta_str = (
                    item.hasta.strftime("%d/%m/%Y") if item.hasta else ""
                )

                row_vals = [
                    str(item.docente.dni) if item.docente else "",
                    item.docente.nombre_completo if item.docente else "",
                    item.docente.sexo if item.docente else "",
                    sit,
                    cod_cargo,
                    desc_cargo,
                    item.horas_afectadas,
                    cod_lic,
                    art_lic,
                    tipo_inst,
                    item.oficina or oficina_val,
                    num_inst,
                    item.anio,
                    desde_str,
                    hasta_str,
                ]

                ws.row_dimensions[r_actual].height = 20
                for c_idx, val in enumerate(row_vals, start=1):
                    cell = ws.cell(row=r_actual, column=c_idx, value=val)
                    cell.font = font_data
                    cell.border = border_cell
                    if c_idx in [1, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15]:
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left
                r_actual += 1

        return r_actual

    # Bloque IL-01 (Salud)
    tit_il01 = "INFORME MENSUAL DE LICENCIAS POR ENFERMEDAD (IL-01) - ANEXO I"
    fila_fin_il01 = escribir_bloque(
        fila_inicio=1,
        titulo=tit_il01,
        font_titulo=font_titulo_il01,
        fill_header=fill_header_il01,
        renglones=renglones_il01,
    )

    # Espaciador intermedio (2 filas en blanco)
    fila_inicio_il02 = fila_fin_il01 + 2

    # Bloque IL-02 (Otros / Permisos)
    tit_il02 = "INFORME MENSUAL DE LICENCIAS Y OTROS (IL-02) - ANEXO I"
    escribir_bloque(
        fila_inicio=fila_inicio_il02,
        titulo=tit_il02,
        font_titulo=font_titulo_il02,
        fill_header=fill_header_il02,
        renglones=renglones_il02,
    )

    # Ajuste dinámico de anchos de columna para evitar textos recortados
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            if cell.row in membrete_rows:
                continue
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    return wb


class ExportarPlanillaExcelView(LoginRequiredMixin, View):
    """
    Ticket 18.5: Exportación oficial a Excel (.xlsx) estructurado según cuadros
    IL-01 (Salud) e IL-02 (Otras causales y permisos).
    Recepción de parámetros ?mes= y ?anio= con ajuste dinámico de anchos y
    membretes oficiales institucionales.
    """

    def get(self, request, *args, **kwargs):
        mes_param = request.GET.get("mes")
        anio_param = request.GET.get("anio")
        cuadro_param = (request.GET.get("cuadro") or "").strip().upper()

        vigentes = RenglonPlanillaMensual.objects.vigentes().select_related(
            "docente",
            "cargo__materia",
            "cargo__cargo_catalogo",
            "tipo_licencia",
        )

        mes = None
        anio = None

        if mes_param and str(mes_param).isdigit():
            mes = int(mes_param)
        if anio_param and str(anio_param).isdigit():
            anio = int(anio_param)

        if mes is None or anio is None:
            ultimo = vigentes.order_by("-anio", "-mes").first()
            if mes is None:
                mes = (
                    ultimo.mes
                    if ultimo
                    else datetime.date.today().month
                )
            if anio is None:
                anio = (
                    ultimo.anio
                    if ultimo
                    else datetime.date.today().year
                )

        base_qs = vigentes.filter(mes=mes, anio=anio).order_by(
            "numero_instrumento",
            "docente__apellido",
            "desde",
        )

        oficina = getattr(settings, "DEFAULT_OFICINA_CODE", "1452")
        primer_con_oficina = base_qs.exclude(oficina="").first()
        if primer_con_oficina and primer_con_oficina.oficina:
            oficina = primer_con_oficina.oficina

        if cuadro_param == "IL-01":
            renglones_il01 = [
                r
                for r in base_qs
                if r.cuadro == "IL-01"
                or (
                    r.tipo_licencia
                    and r.tipo_licencia.cuadro_mensual == "IL-01"
                )
            ]
            renglones_il02 = []
        elif cuadro_param == "IL-02":
            renglones_il01 = []
            renglones_il02 = [
                r
                for r in base_qs
                if r.cuadro == "IL-02"
                or (
                    r.tipo_licencia
                    and r.tipo_licencia.cuadro_mensual == "IL-02"
                )
            ]
        else:
            renglones_il01 = [
                r
                for r in base_qs
                if r.cuadro == "IL-01"
                or (
                    r.tipo_licencia
                    and r.tipo_licencia.cuadro_mensual == "IL-01"
                )
            ]
            renglones_il02 = [r for r in base_qs if r not in renglones_il01]

        wb = construir_libro_excel_planillas(
            renglones_il01=renglones_il01,
            renglones_il02=renglones_il02,
            mes=mes,
            anio=anio,
            oficina=oficina,
        )

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        mes_slug = (
            str(mes_param)
            if (mes_param and str(mes_param).isdigit())
            else str(mes)
        )
        anio_slug = (
            str(anio_param)
            if (anio_param and str(anio_param).isdigit())
            else str(anio)
        )
        filename = f"Planilla_Mensual_{mes_slug}_{anio_slug}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CambiarLicenciaRenglonView(PermisosEstrictosMixin, View):
    """
    Ticket 9 y Ticket 10.3:
    Permite modificar el Tipo de Licencia / Artículo de un Renglón y/o
    conmutar su instrumento entre Disposición Interna y Resolución Ministerial externa
    con su correspondiente número oficial.
    Blindaje de permisos backend (Ticket 10.6 y Ticket 11): Restringe el endpoint POST a
    roles operativos (Admin_Institucional o Bedelia_Operadoras). Consulta_Directiva
    recibe HTTP 403 Forbidden.
    """

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
            or user.has_perm("licencias.change_renglonplanillamensual")
        )

    def post(self, request, pk):
        renglon = get_object_or_404(RenglonPlanillaMensual, pk=pk)

        # 1. Actualización de Tipo de Licencia (Ticket 9)
        nuevo_tipo_id = request.POST.get("tipo_licencia")
        if nuevo_tipo_id:
            if isinstance(nuevo_tipo_id, TipoLicencia):
                nuevo_tipo = nuevo_tipo_id
            elif str(nuevo_tipo_id).isdigit():
                nuevo_tipo = TipoLicencia.objects.filter(pk=int(nuevo_tipo_id)).first()
            else:
                nuevo_tipo = TipoLicencia.objects.filter(codigo=nuevo_tipo_id).first()

            if nuevo_tipo:
                num_original = renglon.numero_instrumento
                renglon.tipo_licencia = nuevo_tipo
                if nuevo_tipo.cuadro_mensual in ["IL-01", "DL-01"]:
                    renglon.cuadro = "IL-01"
                else:
                    renglon.cuadro = "IL-02"

                # Preservar el correlativo si no se envió cambio explícito
                if not request.POST.get("numero_instrumento"):
                    renglon.numero_instrumento = num_original

        # 2. Conmutación de Instrumento (Ticket 10.3)
        tipo_inst = request.POST.get("tipo_instrumento")
        if tipo_inst in ["DISPOSICION", "RESOLUCION"]:
            renglon.tipo_instrumento = tipo_inst

        # 3. Número oficial externo o interno
        nuevo_num = (
            request.POST.get("numero_instrumento")
            or request.POST.get("numero_resolucion")
            or request.POST.get("numero_disposicion")
        )
        if nuevo_num is not None and nuevo_num.strip():
            renglon.numero_instrumento = nuevo_num.strip()

        if renglon.tipo_instrumento == "DISPOSICION" and renglon.numero_instrumento:
            from apps.licencias.services import (
                confirmar_correlativo_disposicion,
            )

            confirmar_correlativo_disposicion(
                renglon.numero_instrumento,
                anio=renglon.anio,
                usuario=request.user,
            )

        audit_save(renglon, user=request.user, created=False)

        tipo_desc = (
            "Resolución Ministerial"
            if renglon.tipo_instrumento == "RESOLUCION"
            else "Disposición Interna"
        )
        messages.success(
            request,
            f"Renglón de {renglon.docente.nombre_completo} actualizado: "
            f"{tipo_desc} N° {renglon.numero_instrumento or '-'}.",
        )

        next_url = (
            request.POST.get("next")
            or request.META.get("HTTP_REFERER")
            or reverse("licencias:planilla_list")
        )
        return redirect(next_url)


class JustificacionDiferidaView(PermisosEstrictosMixin, FormView):
    """
    Vista protegida para justificaciones diferidas (Ticket 7, RN-03 y Ticket 11).
    Permisos: Solo accesible para Admin_Institucional y Bedelia_Operadoras.
    Usuarios no autenticados son redirigidos a login (302).
    Usuarios del grupo Consulta_Directiva u otros sin privilegios reciben 403 Forbidden.
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


CATALOGO_ESTATUTARIO_BASE = {
    "340": {
        "codigo": "LIC-340",
        "articulo": "340",
        "descripcion": "Licencia por Enfermedad",
        "cuadro": "IL-01",
    },
    "340-A": {
        "codigo": "LIC-340A",
        "articulo": "340-A",
        "descripcion": "Enfermedad de Corto Tratamiento",
        "cuadro": "IL-01",
    },
    "340A": {
        "codigo": "LIC-340A",
        "articulo": "340-A",
        "descripcion": "Enfermedad de Corto Tratamiento",
        "cuadro": "IL-01",
    },
    "340-B": {
        "codigo": "LIC-340B",
        "articulo": "340-B",
        "descripcion": "Afección de Largo Tratamiento",
        "cuadro": "IL-01",
    },
    "340B": {
        "codigo": "LIC-340B",
        "articulo": "340-B",
        "descripcion": "Afección de Largo Tratamiento",
        "cuadro": "IL-01",
    },
    "340-C": {
        "codigo": "LIC-340C",
        "articulo": "340-C",
        "descripcion": "Accidente de Trabajo / Enfermedad Profesional",
        "cuadro": "IL-01",
    },
    "340C": {
        "codigo": "LIC-340C",
        "articulo": "340-C",
        "descripcion": "Accidente de Trabajo / Enfermedad Profesional",
        "cuadro": "IL-01",
    },
    "340-D": {
        "codigo": "LIC-340D",
        "articulo": "340-D",
        "descripcion": "Atención Familiar Enfermo",
        "cuadro": "IL-01",
    },
    "340D": {
        "codigo": "LIC-340D",
        "articulo": "340-D",
        "descripcion": "Atención Familiar Enfermo",
        "cuadro": "IL-01",
    },
    "341": {
        "codigo": "LIC-341",
        "articulo": "341",
        "descripcion": "Licencia por Maternidad",
        "cuadro": "IL-02",
    },
    "342": {
        "codigo": "LIC-342",
        "articulo": "342",
        "descripcion": "Nacimiento de Hijo / Adopción",
        "cuadro": "IL-02",
    },
    "343": {
        "codigo": "LIC-343",
        "articulo": "343",
        "descripcion": "Matrimonio",
        "cuadro": "IL-02",
    },
    "344": {
        "codigo": "LIC-344",
        "articulo": "344",
        "descripcion": "Duelo Familiar",
        "cuadro": "IL-02",
    },
    "345": {
        "codigo": "LIC-345",
        "articulo": "345",
        "descripcion": "Exámenes o Perfeccionamiento Docente",
        "cuadro": "IL-02",
    },
    "346": {
        "codigo": "LIC-346",
        "articulo": "346",
        "descripcion": "Razones Particulares",
        "cuadro": "IL-02",
    },
    "347": {
        "codigo": "LIC-347",
        "articulo": "347",
        "descripcion": "Permiso Especial",
        "cuadro": "IL-02",
    },
}


class AutocompletarLicenciaAPIView(View):
    """
    Endpoint API interno para autocompletar códigos de licencia (Ticket 10).
    Ruta: GET /api/.../autocompletar/?articulo=<codigo>

    Respuestas:
    - 200 con array [...] si encuentra coincidencia.
    - 200 con array vacío [] si no hay coincidencias.
    - 400 Bad Request si falta el parámetro ?articulo=.
    """

    def get(self, request, *args, **kwargs):
        articulo = request.GET.get("articulo")
        if articulo is None:
            return JsonResponse(
                {"error": "El parámetro 'articulo' es obligatorio."},
                status=400,
            )

        art_clean = articulo.strip()
        if not art_clean:
            return JsonResponse(
                {"error": "El parámetro 'articulo' no puede estar vacío."},
                status=400,
            )

        norm_val = (
            art_clean.upper()
            .replace("ARTÍCULO", "")
            .replace("ARTICULO", "")
            .replace("ART.", "")
            .replace("ART", "")
            .strip()
        )

        q_filter = Q(articulo__icontains=art_clean) | Q(codigo__icontains=art_clean)
        if norm_val:
            q_filter |= Q(articulo__icontains=norm_val) | Q(codigo__icontains=norm_val)

        qs = TipoLicencia.objects.filter(q_filter).distinct().order_by("codigo")

        regimen = request.GET.get("regimen")
        cargo_id = request.GET.get("cargo_id") or request.GET.get("cargo")
        if regimen or cargo_id:
            from apps.licencias.validaciones import (
                filtrar_tipos_licencia_por_regimen,
            )

            qs = filtrar_tipos_licencia_por_regimen(
                queryset=qs,
                situacion_revista=regimen,
                cargo=cargo_id,
            )

        if qs.exists():
            resultados = [
                {
                    "id": lic.pk,
                    "codigo": lic.codigo,
                    "articulo": lic.articulo,
                    "descripcion": lic.descripcion,
                    "cuadro": (
                        "IL-01"
                        if getattr(lic, "cuadro_mensual", "") in ["IL-01", "DL-01"]
                        else "IL-02"
                    ),
                    "cuadro_mensual": getattr(lic, "cuadro_mensual", "IL-02"),
                    "categoria": lic.categoria,
                    "forma_pago": lic.forma_pago,
                    "goce_haberes": lic.goce_haberes,
                    "regimen": getattr(lic, "regimen", ""),
                    "situacion_revista_aplicable": getattr(
                        lic, "situacion_revista_aplicable", ""
                    ),
                }
                for lic in qs
            ]
            return JsonResponse(resultados, safe=False, status=200)

        # Fallback al catálogo estatutario si no hay registro específico en BD
        if norm_val in CATALOGO_ESTATUTARIO_BASE:
            return JsonResponse(
                [CATALOGO_ESTATUTARIO_BASE[norm_val]],
                safe=False,
                status=200,
            )

        return JsonResponse([], safe=False, status=200)


autocompletar_licencia_api = AutocompletarLicenciaAPIView.as_view()


class CalcularFechasLicenciaAPIView(View):
    """
    Endpoint API para calcular automáticamente fecha de reintegro y días
    consumidos según la unidad del tipo (Ticket 16.2).
    Ruta: GET o POST /api/licencias/calcular-fechas/

    Parámetros (GET query params o POST body/form):
    - fecha_desde: YYYY-MM-DD (Obligatorio)
    - dias: int (Opcional si se especifica fecha_hasta)
    - fecha_hasta: YYYY-MM-DD (Opcional si se especifica dias)
    - unidad: 'HABILES' o 'CORRIDOS' (Opcional)
    - tipo_licencia: ID o código de TipoLicencia (Opcional)

    Responde:
    200 OK con JSON de CalculoFechasLicencia.to_dict()
    400 Bad Request ante parámetros inválidos o errores de validación.
    """

    def _procesar(self, params):
        fecha_desde = params.get("fecha_desde")
        if not fecha_desde:
            return JsonResponse(
                {"error": "El parámetro 'fecha_desde' es obligatorio."},
                status=400,
            )

        dias = params.get("dias")
        fecha_hasta = params.get("fecha_hasta")

        if not dias and not fecha_hasta:
            return JsonResponse(
                {
                    "error": (
                        "Debe especificar 'dias' o 'fecha_hasta' para "
                        "calcular el período."
                    )
                },
                status=400,
            )

        tipo_lic_id = params.get("tipo_licencia")
        tipo_lic = None
        if tipo_lic_id:
            if str(tipo_lic_id).isdigit():
                tipo_lic = TipoLicencia.objects.filter(pk=int(tipo_lic_id)).first()
            else:
                tipo_lic = TipoLicencia.objects.filter(codigo=tipo_lic_id).first()

        unidad = params.get("unidad")

        try:
            resultado = calcular_fechas_licencia(
                fecha_desde=fecha_desde,
                dias=dias,
                fecha_hasta=fecha_hasta,
                unidad=unidad,
                tipo_licencia=tipo_lic,
            )
            return JsonResponse({"status": "success", "data": resultado.to_dict()})
        except ValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, "messages") else str(exc)
            return JsonResponse({"status": "error", "error": msg}, status=400)
        except Exception as exc:
            return JsonResponse({"status": "error", "error": str(exc)}, status=400)

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        return self._procesar(request.POST)


calcular_fechas_licencia_api = CalcularFechasLicenciaAPIView.as_view()


class ValidarRegimenLicenciaAPIView(View):
    """
    Endpoint API para validar la compatibilidad de una licencia con el régimen
    de revista de un cargo docente (Ticket 17.1).
    Ruta: GET /api/licencias/validar-regimen/?tipo_licencia=<id|cod>&regimen=<reg>
    """

    def _procesar(self, params):
        tipo_param = params.get("tipo_licencia") or params.get("codigo")
        regimen_param = params.get("regimen")
        cargo_id = params.get("cargo_id") or params.get("cargo")

        if not tipo_param:
            return JsonResponse(
                {
                    "status": "error",
                    "error": "El parámetro 'tipo_licencia' es obligatorio.",
                },
                status=400,
            )

        if str(tipo_param).isdigit():
            tipo_lic = TipoLicencia.objects.filter(pk=int(tipo_param)).first()
        else:
            tipo_lic = TipoLicencia.objects.filter(codigo=tipo_param).first()

        if not tipo_lic:
            return JsonResponse(
                {
                    "status": "error",
                    "error": f"No se encontró el tipo de licencia '{tipo_param}'.",
                },
                status=404,
            )

        from apps.licencias.validaciones import (
            obtener_regimenes_permitidos,
            validar_regimen_revista,
        )

        permitidos = list(sorted(obtener_regimenes_permitidos(tipo_lic)))

        try:
            validar_regimen_revista(
                tipo_licencia=tipo_lic,
                situacion_revista=regimen_param,
                cargo=cargo_id,
            )
            valido = True
            mensaje = "El tipo de licencia es compatible con el régimen del cargo."
        except ValidationError as exc:
            valido = False
            mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)

        return JsonResponse(
            {
                "status": "success",
                "valido": valido,
                "mensaje": mensaje,
                "regimenes_permitidos": permitidos,
                "tipo_licencia": tipo_lic.codigo,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST or {}
        if not data and request.body:
            import json

            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
        return self._procesar(data)


validar_regimen_licencia_api = ValidarRegimenLicenciaAPIView.as_view()


class ValidarAntiguedadLicenciaAPIView(View):
    """
    Endpoint API para consultar antigüedad de un docente y validar tope
    efectivo de licencias (Ticket 17.2).
    Ruta: GET/POST /api/licencias/validar-antiguedad/
    """

    def _procesar(self, params):
        tipo_param = params.get("tipo_licencia") or params.get("codigo")
        docente_id = params.get("docente_id") or params.get("docente")
        cargo_id = params.get("cargo_id") or params.get("cargo")
        fecha_desde = params.get("fecha_desde")
        fecha_hasta = params.get("fecha_hasta")
        dias = params.get("dias")

        if not tipo_param:
            return JsonResponse(
                {
                    "status": "error",
                    "error": "El parámetro 'tipo_licencia' es obligatorio.",
                },
                status=400,
            )

        if str(tipo_param).isdigit():
            tipo_lic = TipoLicencia.objects.filter(pk=int(tipo_param)).first()
        else:
            tipo_lic = TipoLicencia.objects.filter(codigo=tipo_param).first()

        if not tipo_lic:
            return JsonResponse(
                {
                    "status": "error",
                    "error": (f"No se encontró el tipo de licencia '{tipo_param}'."),
                },
                status=404,
            )

        from apps.licencias.validaciones import (
            obtener_tope_efectivo_licencia,
            validar_antiguedad_minima,
        )

        info_tope = obtener_tope_efectivo_licencia(
            tipo_licencia=tipo_lic,
            cargo=cargo_id,
            docente=docente_id,
            fecha_referencia=fecha_desde,
        )

        try:
            validar_antiguedad_minima(
                tipo_licencia=tipo_lic,
                docente=docente_id,
                cargo=cargo_id,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                dias=dias,
            )
            valido = True
            mensaje = "Cumple con las restricciones de antigüedad estatutaria."
        except ValidationError as exc:
            valido = False
            mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)

        return JsonResponse(
            {
                "status": "success",
                "valido": valido,
                "mensaje": mensaje,
                "antiguedad_meses": info_tope["antiguedad_meses"],
                "tope_dias": info_tope["tope_dias"],
                "tope_reducido": info_tope["tope_reducido"],
                "regimen": info_tope["regimen"],
                "es_enfermedad_comun": info_tope["es_enfermedad_comun"],
                "tipo_licencia": tipo_lic.codigo,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST or {}
        if not data and request.body:
            import json

            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
        return self._procesar(data)


validar_antiguedad_licencia_api = ValidarAntiguedadLicenciaAPIView.as_view()


class ValidarSolapamientoLicenciaAPIView(View):
    """
    Endpoint API para validar que un cargo docente no posea licencias
    activas superpuestas en el período solicitado (Ticket 17.3).
    Ruta: GET o POST /api/licencias/validar-solapamiento/
    """

    def _procesar(self, params):
        cargo_id = params.get("cargo_id") or params.get("cargo")
        fecha_desde = params.get("fecha_desde")
        fecha_hasta = params.get("fecha_hasta")
        excluir_id = params.get("excluir_id")
        docente_id = params.get("docente_id") or params.get("docente")
        tipo_licencia_id = (
            params.get("tipo_licencia_id") or params.get("tipo_licencia")
        )

        if not cargo_id and not docente_id:
            return JsonResponse(
                {
                    "status": "error",
                    "error": (
                        "Debe especificar al menos 'cargo' o 'docente' "
                        "para validar solapamiento."
                    ),
                },
                status=400,
            )

        if not fecha_desde or not fecha_hasta:
            return JsonResponse(
                {
                    "status": "error",
                    "error": (
                        "Los parámetros 'fecha_desde' y 'fecha_hasta' "
                        "son obligatorios."
                    ),
                },
                status=400,
            )

        from apps.licencias.validaciones import (
            buscar_licencias_solapadas,
            es_licencia_medica_o_reposo,
            validar_solapamiento_licencias,
        )

        excluir_pk = int(excluir_id) if str(excluir_id).isdigit() else None
        solapadas = buscar_licencias_solapadas(
            cargo=cargo_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            excluir_id=excluir_pk,
            docente=docente_id,
            tipo_licencia=tipo_licencia_id,
        )

        hay_solapamiento = solapadas.exists()
        solapadas_data = [
            {
                "id": lic.pk,
                "tipo_licencia": (
                    lic.tipo_licencia.codigo if lic.tipo_licencia else "S/T"
                ),
                "articulo": (
                    lic.tipo_licencia.articulo if lic.tipo_licencia else ""
                ),
                "descripcion": (
                    lic.tipo_licencia.descripcion if lic.tipo_licencia else ""
                ),
                "cargo": str(lic.cargo) if lic.cargo else "Alcance Institucional",
                "cargo_id": lic.cargo_id,
                "es_institucional": lic.cargo_id is None,
                "es_medica": es_licencia_medica_o_reposo(lic.tipo_licencia),
                "fecha_desde": lic.fecha_desde.strftime("%Y-%m-%d"),
                "fecha_hasta": lic.fecha_hasta_prevista.strftime("%Y-%m-%d"),
                "estado": lic.estado,
            }
            for lic in solapadas
        ]

        dummy_inst = None
        if excluir_pk:
            dummy_inst = type("Obj", (), {"pk": excluir_pk})()

        try:
            validar_solapamiento_licencias(
                cargo=cargo_id,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                instancia_actual=dummy_inst,
                docente=docente_id,
                tipo_licencia=tipo_licencia_id,
            )
            valido = True
            mensaje = (
                "No existen licencias superpuestas en el período para el cargo."
            )
        except ValidationError as exc:
            valido = False
            mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)

        return JsonResponse(
            {
                "status": "success",
                "valido": valido,
                "hay_solapamiento": hay_solapamiento,
                "mensaje": mensaje,
                "cantidad_solapadas": len(solapadas_data),
                "licencias_solapadas": solapadas_data,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST or {}
        if not data and request.body:
            import json

            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
        return self._procesar(data)


validar_solapamiento_licencia_api = ValidarSolapamientoLicenciaAPIView.as_view()


class ValidarSaldosLicenciaAPIView(View):
    """
    Endpoint API para calcular el saldo disponible y validar que no se exceda
    el tope máximo permitido en el período (Ticket 17.4).
    Ruta: GET o POST /api/licencias/validar-saldos/
    """

    def _procesar(self, params):
        tipo_param = params.get("tipo_licencia") or params.get("codigo")
        docente_id = params.get("docente_id") or params.get("docente")
        cargo_id = params.get("cargo_id") or params.get("cargo")
        fecha_desde = params.get("fecha_desde")
        fecha_hasta = params.get("fecha_hasta")
        dias = params.get("dias")
        excluir_id = params.get("excluir_id")

        if not tipo_param:
            return JsonResponse(
                {
                    "status": "error",
                    "error": "El parámetro 'tipo_licencia' es obligatorio.",
                },
                status=400,
            )

        if str(tipo_param).isdigit():
            tipo_lic = TipoLicencia.objects.filter(pk=int(tipo_param)).first()
        else:
            tipo_lic = TipoLicencia.objects.filter(codigo=tipo_param).first()

        if not tipo_lic:
            return JsonResponse(
                {
                    "status": "error",
                    "error": (f"No se encontró el tipo de licencia '{tipo_param}'."),
                },
                status=404,
            )

        from apps.licencias.validaciones import (
            calcular_saldo_licencia,
            validar_control_saldos_y_topes,
        )

        excluir_pk = int(excluir_id) if str(excluir_id).isdigit() else None
        res_saldo = calcular_saldo_licencia(
            tipo_licencia=tipo_lic,
            docente=docente_id,
            cargo=cargo_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            dias_solicitados=dias,
            excluir_id=excluir_pk,
        )

        dummy_inst = None
        if excluir_pk:
            dummy_inst = type("Obj", (), {"pk": excluir_pk})()

        try:
            validar_control_saldos_y_topes(
                tipo_licencia=tipo_lic,
                docente=docente_id,
                cargo=cargo_id,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                dias=dias,
                instancia_actual=dummy_inst,
            )
            valido = True
            mensaje = "La solicitud se encuentra dentro del saldo y tope disponible."
        except ValidationError as exc:
            valido = False
            mensaje = exc.messages[0] if hasattr(exc, "messages") else str(exc)

        dias_restantes = (
            max(0, res_saldo["tope_maximo"] - res_saldo["total_acumulado"])
            if res_saldo["tope_maximo"] is not None
            else None
        )

        return JsonResponse(
            {
                "status": "success",
                "valido": valido,
                "supera_tope": res_saldo["supera_tope"],
                "saldo_disponible": res_saldo["saldo_disponible"],
                "dias_consumidos": res_saldo["dias_consumidos"],
                "dias_solicitados": res_saldo["dias_solicitados"],
                "total_acumulado": res_saldo["total_acumulado"],
                "dias_restantes": dias_restantes,
                "tope_maximo": res_saldo["tope_maximo"],
                "tope_reducido": res_saldo["tope_reducido"],
                "periodo": res_saldo["periodo"],
                "tipo_licencia": tipo_lic.codigo,
                "mensaje": mensaje,
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST or {}
        if not data and request.body:
            import json

            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
        return self._procesar(data)


validar_saldos_licencia_api = ValidarSaldosLicenciaAPIView.as_view()


class DocenteCargosAPIView(View):
    """
    Ticket 18.2: Retorna los cargos activos de un docente para alimentar
    dinámicamente el selector del formulario de solicitud.
    Ruta: GET /api/licencias/docente-cargos/?docente=<id>
    """

    def get(self, request, *args, **kwargs):
        docente_id = request.GET.get("docente") or request.GET.get("docente_id")
        if not docente_id or not str(docente_id).isdigit():
            return JsonResponse(
                {"status": "error", "error": "Parámetro 'docente' inválido."},
                status=400,
            )

        from apps.personal.models import CargoDocente

        cargos = CargoDocente.objects.filter(
            docente_id=int(docente_id), activo=True
        ).select_related("materia")

        data = []
        for c in cargos:
            materia_nombre = c.materia.nombre if c.materia else str(c)
            revista_disp = c.get_situacion_revista_display()
            data.append(
                {
                    "id": c.id,
                    "materia": materia_nombre,
                    "situacion_revista": c.situacion_revista,
                    "situacion_revista_display": revista_disp,
                    "turno": getattr(c, "turno", ""),
                    "label": f"{c} ({revista_disp})",
                }
            )

        return JsonResponse({"status": "success", "cargos": data}, status=200)


docente_cargos_api = DocenteCargosAPIView.as_view()


class TiposLicenciaPorRegimenAPIView(View):
    """
    Ticket 18.2: Retorna los tipos de licencia estatutarios compatibles
    con el régimen de revista (TIT, INT, SUP) o con un cargo docente.
    Ruta: GET /api/licencias/tipos-por-regimen/?regimen=TIT
    """

    def get(self, request, *args, **kwargs):
        regimen = request.GET.get("regimen")
        cargo_id = request.GET.get("cargo") or request.GET.get("cargo_id")

        if not regimen and cargo_id and str(cargo_id).isdigit():
            from apps.personal.models import CargoDocente

            cargo = CargoDocente.objects.filter(pk=int(cargo_id)).first()
            if cargo:
                regimen = cargo.situacion_revista

        from apps.licencias.validaciones import (
            filtrar_tipos_licencia_por_regimen,
            normalizar_regimen,
        )

        reg_norm = normalizar_regimen(regimen) if regimen else None
        qs = TipoLicencia.objects.filter(activo=True)
        if reg_norm:
            qs = filtrar_tipos_licencia_por_regimen(
                queryset=qs, situacion_revista=reg_norm
            )

        tipos = []
        for t in qs.order_by("codigo"):
            tipos.append(
                {
                    "id": t.id,
                    "codigo": t.codigo,
                    "articulo": t.articulo,
                    "descripcion": t.descripcion,
                    "duracion_maxima": t.duracion_maxima,
                    "unidad": t.unidad or "Corridos",
                    "periodo_tope": t.periodo_tope or "Año calendario",
                    "label": f"{t.codigo} - {t.descripcion}"
                    + (f" ({t.articulo})" if t.articulo else ""),
                }
            )

        return JsonResponse(
            {
                "status": "success",
                "regimen": reg_norm,
                "tipos": tipos,
            },
            status=200,
        )


tipos_licencia_por_regimen_api = TiposLicenciaPorRegimenAPIView.as_view()


class EvaluarImpactoRevistaAPIView(View):
    """
    Ticket 19.2: Endpoint API para evaluar el impacto y desglose operativo
    de una licencia por materia y situación de revista antes de confirmar.
    Ruta: GET o POST /api/licencias/evaluar-impacto-revista/
    """

    def _procesar(self, params):
        docente_param = params.get("docente") or params.get("docente_id")
        tipo_param = (
            params.get("tipo_licencia")
            or params.get("tipo_id")
            or params.get("codigo")
        )
        cargo_param = params.get("cargo") or params.get("cargo_id")
        fecha_desde = params.get("fecha_desde")
        fecha_hasta = params.get("fecha_hasta")

        if not docente_param:
            return JsonResponse(
                {"status": "error", "error": "Parámetro 'docente' obligatorio."},
                status=400,
            )

        if not tipo_param:
            return JsonResponse(
                {
                    "status": "error",
                    "error": "Parámetro 'tipo_licencia' obligatorio.",
                },
                status=400,
            )

        from apps.licencias.validaciones import (
            evaluar_impacto_licencia_por_revista,
        )
        from apps.licencias.models import TipoLicencia
        from apps.personal.models import Docente

        doc_obj = (
            Docente.objects.filter(pk=int(docente_param)).first()
            if str(docente_param).isdigit()
            else None
        )
        if not doc_obj:
            return JsonResponse(
                {"status": "error", "error": "Docente no encontrado."},
                status=404,
            )

        tipo_obj = None
        if str(tipo_param).isdigit():
            tipo_obj = TipoLicencia.objects.filter(pk=int(tipo_param)).first()
        else:
            tipo_obj = TipoLicencia.objects.filter(codigo=tipo_param).first()

        if not tipo_obj:
            return JsonResponse(
                {"status": "error", "error": "Tipo de licencia no encontrado."},
                status=404,
            )

        cargo_id = (
            int(cargo_param)
            if (cargo_param and str(cargo_param).isdigit())
            else None
        )

        cargos_evaluados = evaluar_impacto_licencia_por_revista(
            docente=doc_obj,
            tipo_licencia=tipo_obj,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            cargo=cargo_id,
        )

        total_cargos = len(cargos_evaluados)
        aplicables = sum(1 for c in cargos_evaluados if c["aplica"])
        no_aplicables = total_cargos - aplicables

        return JsonResponse(
            {
                "status": "success",
                "docente": {
                    "id": doc_obj.id,
                    "nombre_completo": str(doc_obj),
                },
                "tipo_licencia": {
                    "id": tipo_obj.id,
                    "codigo": tipo_obj.codigo,
                    "articulo": tipo_obj.articulo,
                },
                "cargos": cargos_evaluados,
                "resumen": {
                    "total": total_cargos,
                    "aplicables": aplicables,
                    "no_aplicables": no_aplicables,
                    "todas_aplican": no_aplicables == 0,
                    "tiene_incompatibilidad": no_aplicables > 0,
                },
            },
            status=200,
        )

    def get(self, request, *args, **kwargs):
        return self._procesar(request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST or {}
        if not data and request.body:
            import json

            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
        return self._procesar(data)


evaluar_impacto_revista_api = EvaluarImpactoRevistaAPIView.as_view()


class SiguienteDisposicionAPIView(View):
    """
    Ticket 19.3: Endpoint API para obtener el siguiente número correlativo
    anual disponible en formato NNN/AAAA sin consumirlo de inmediato.
    Ruta: GET /api/licencias/siguiente-disposicion/?anio=2026
    """

    def get(self, request, *args, **kwargs):
        anio_param = request.GET.get("anio")
        target_anio = (
            int(anio_param)
            if (anio_param and str(anio_param).isdigit())
            else None
        )
        from apps.licencias.services import (
            obtener_siguiente_correlativo_disposicion,
        )

        siguiente = obtener_siguiente_correlativo_disposicion(
            anio=target_anio,
            reservar=False,
        )
        final_anio = target_anio or datetime.date.today().year
        return JsonResponse(
            {
                "status": "success",
                "siguiente": siguiente,
                "anio": final_anio,
            },
            status=200,
        )


siguiente_disposicion_api = SiguienteDisposicionAPIView.as_view()


class ValidarDisposicionAPIView(View):
    """
    Ticket 19.3: Endpoint API para verificar si un número de Disposición Interna
    ya fue asignado en el año indicado o se encuentra disponible.
    Ruta: GET /api/licencias/validar-disposicion/?numero=015/2026&anio=2026
    """

    def get(self, request, *args, **kwargs):
        numero = request.GET.get("numero", "").strip()
        anio_param = request.GET.get("anio")
        lic_id = request.GET.get("licencia_id")
        reng_id = request.GET.get("renglon_id")

        if not numero:
            return JsonResponse(
                {
                    "status": "error",
                    "error": "Parámetro 'numero' obligatorio.",
                },
                status=400,
            )

        target_anio = (
            int(anio_param)
            if (anio_param and str(anio_param).isdigit())
            else None
        )
        target_lic = (
            int(lic_id)
            if (lic_id and str(lic_id).isdigit())
            else None
        )
        target_reng = (
            int(reng_id)
            if (reng_id and str(reng_id).isdigit())
            else None
        )

        from apps.licencias.services import verificar_disposicion_duplicada

        res = verificar_disposicion_duplicada(
            numero_str=numero,
            anio=target_anio,
            excluir_licencia_id=target_lic,
            excluir_renglon_id=target_reng,
        )

        return JsonResponse(
            {
                "status": "success",
                "duplicado": res["duplicado"],
                "mensaje": res["mensaje"],
                "numero": res.get("numero"),
                "anio": res.get("anio"),
            },
            status=200,
        )


validar_disposicion_api = ValidarDisposicionAPIView.as_view()


class DocenteSaldosView(LoginRequiredMixin, View):
    """
    Ticket 18.2: Vista institucional para la visualización integral de
    saldos de licencias disponibles por docente.
    Rutas:
    - /licencias/saldos/
    - /licencias/saldos/<int:docente_id>/
    """

    template_name = "licencias/docente_saldos.html"

    def get(self, request, docente_id=None, *args, **kwargs):
        from apps.personal.models import Docente
        from apps.licencias.services import obtener_resumen_saldos_docente

        target_id = docente_id or request.GET.get("docente")
        docente = None
        if target_id and str(target_id).isdigit():
            docente = Docente.objects.filter(pk=int(target_id)).first()

        docentes_activos = Docente.objects.filter(activo=True).order_by(
            "apellido", "nombre"
        )

        if not docente and docentes_activos.exists():
            docente = docentes_activos.first()

        resumen = None
        licencias_recientes = []
        anio = request.GET.get("anio")
        anio_int = int(anio) if (anio and str(anio).isdigit()) else None

        if docente:
            resumen = obtener_resumen_saldos_docente(docente, anio=anio_int)
            licencias_recientes = (
                LicenciaOtorgada.objects.filter(docente=docente)
                .select_related("tipo_licencia", "cargo")
                .order_by("-fecha_desde")[:10]
            )

        context = {
            "docente_seleccionado": docente,
            "resumen": resumen,
            "docentes": docentes_activos,
            "licencias_recientes": licencias_recientes,
            "anio_actual": anio_int or datetime.date.today().year,
        }
        return render(request, self.template_name, context)


class LicenciaOtorgadaListView(LoginRequiredMixin, ListView):
    """
    Listado institucional de licencias otorgadas y solicitudes (Ticket 16.1 / 17.1).
    """

    model = LicenciaOtorgada
    template_name = "licencias/licenciaotorgada_list.html"
    context_object_name = "licencias"
    paginate_by = 25
    ordering = ["-fecha_desde", "-creado_en"]


class LicenciaOtorgadaCreateView(PermisosEstrictosMixin, CreateView):
    """
    Formulario de solicitud y registro de licencias docentes
    (Ticket 16.1 / 17.1 / 18.2).
    """

    model = LicenciaOtorgada
    form_class = LicenciaOtorgadaForm
    template_name = "licencias/licenciaotorgada_form.html"
    success_url = reverse_lazy("licencias:licenciaotorgada_list")
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
        )

    def get_initial(self):
        initial = super().get_initial()
        docente_id = self.request.GET.get("docente")
        cargo_id = self.request.GET.get("cargo")
        tipo_id = self.request.GET.get("tipo_licencia")
        if docente_id:
            initial["docente"] = docente_id
        if cargo_id:
            initial["cargo"] = cargo_id
        if tipo_id:
            initial["tipo_licencia"] = tipo_id
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET":
            docente_id = self.request.GET.get("docente")
            cargo_id = self.request.GET.get("cargo")
            if docente_id and str(docente_id).isdigit():
                kwargs["docente"] = int(docente_id)
            if cargo_id and str(cargo_id).isdigit():
                kwargs["cargo"] = int(cargo_id)
        return kwargs

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        tipo_inst = getattr(form.instance, "tipo_instrumento", "DISPOSICION")
        if tipo_inst == "DISPOSICION":
            from apps.licencias.services import (
                confirmar_correlativo_disposicion,
                obtener_siguiente_correlativo_disposicion,
            )

            anio_lic = (
                form.instance.fecha_desde.year
                if form.instance.fecha_desde
                else None
            )
            if not form.instance.instrumento_legal:
                form.instance.instrumento_legal = (
                    obtener_siguiente_correlativo_disposicion(
                        anio=anio_lic,
                        reservar=True,
                        usuario=self.request.user,
                    )
                )
            else:
                confirmar_correlativo_disposicion(
                    form.instance.instrumento_legal,
                    anio=anio_lic,
                    usuario=self.request.user,
                )

        response = super().form_valid(form)
        if form.instance.estado in ("OTORGADA", "APROBADA"):
            form.instance.sincronizar_asistencia(usuario=self.request.user)
        messages.success(
            self.request,
            f"Licencia para {form.instance.docente} registrada exitosamente.",
        )
        return response


class LicenciaOtorgadaAprobarView(PermisosEstrictosMixin, View):
    """
    Ticket 18.1: Acción para aprobar una licencia y reflejar automáticamente
    las marcas correspondientes en la asistencia diaria.
    """

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
        )

    def post(self, request, pk, *args, **kwargs):
        licencia = get_object_or_404(LicenciaOtorgada, pk=pk)
        licencia.aprobar(usuario=request.user)
        cod = licencia.tipo_licencia.codigo if licencia.tipo_licencia else "LIC"
        messages.success(
            request,
            f"Licencia #{licencia.pk} para {licencia.docente} aprobada exitosamente. "
            f"Se reflejaron las marcas '{cod}' en asistencia diaria.",
        )
        return redirect("licencias:licenciaotorgada_list")

    def get(self, request, pk, *args, **kwargs):
        return self.post(request, pk, *args, **kwargs)


class LicenciaOtorgadaAnularView(PermisosEstrictosMixin, View):
    """
    Ticket 18.1: Acción para anular una licencia y revertir automáticamente
    las marcas correspondientes en la asistencia diaria.
    """

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
        )

    def post(self, request, pk, *args, **kwargs):
        licencia = get_object_or_404(LicenciaOtorgada, pk=pk)
        motivo = request.POST.get("motivo", "")
        licencia.anular(usuario=request.user, motivo=motivo)
        messages.info(
            request,
            f"Licencia #{licencia.pk} para {licencia.docente} anulada. "
            "Se revirtieron las marcas de asistencia a su estado original.",
        )
        return redirect("licencias:licenciaotorgada_list")

    def get(self, request, pk, *args, **kwargs):
        return self.post(request, pk, *args, **kwargs)
