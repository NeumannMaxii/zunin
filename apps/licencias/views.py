"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa:
- Ticket 3.8: Paginación obligatoria (paginate_by = 25).
- Ticket 7: Justificación Diferida y regla RN-03.
- Ticket 8: Pantalla 2 — Catálogo Licencias con filtros y búsqueda.
- Ticket 9: Pantalla Mensual (Planillas), exportación CSV y cambio de artículo
  preservando número de instrumento.
"""

import csv
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
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
                    "error": (
                        f"No se encontró el tipo de licencia '{tipo_param}'."
                    ),
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
    Formulario de solicitud y registro de licencias docentes (Ticket 16.1 / 17.1).
    """

    model = LicenciaOtorgada
    form_class = LicenciaOtorgadaForm
    template_name = "licencias/licenciaotorgada_form.html"
    success_url = reverse_lazy("licencias:licenciaotorgada_list")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(
            self.request,
            f"Licencia para {form.instance.docente} registrada exitosamente.",
        )
        return super().form_valid(form)
