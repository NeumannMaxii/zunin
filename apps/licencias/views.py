"""
Vistas para la aplicación Licencias y Planillas Mensuales.
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25),
Ticket 7: Justificación Diferida y regla RN-03, y
Ticket 8: Pantalla 2 — Catálogo Licencias con filtros por cuadro y búsqueda.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView
from apps.licencias.forms import (
    JustificacionDiferidaForm,
    TipoLicenciaSearchForm,
)
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia


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
        q_val = self.request.GET.get("q", "").strip()

        context["form"] = getattr(
            self, "form", TipoLicenciaSearchForm(self.request.GET)
        )
        context["q"] = q_val
        context["cuadro"] = cuadro_val
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["tipo_licencias"].count()
        )
        context["sugerencias"] = TipoLicencia.objects.filter(
            activo=True
        ).values_list("codigo", "articulo", "descripcion")
        return context


class RenglonPlanillaMensualListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para los renglones consolidados de planillas mensuales.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = RenglonPlanillaMensual
    template_name = "licencias/planilla_list.html"
    context_object_name = "renglones"
    paginate_by = 25
    ordering = ["-anio", "-mes", "docente__apellido"]


class JustificacionDiferidaView(
    LoginRequiredMixin, UserPassesTestMixin, FormView
):
    """
    Vista protegida para procesar justificaciones diferidas (Ticket 7 y RN-03).
    Permisos: Solo accesible para Admin_Institucional y Bedelia_Operadoras.
    Usuarios del grupo Consulta_Directiva o no autenticados reciben 403 Forbidden.
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

        q_filter = (
            Q(articulo__icontains=art_clean) | Q(codigo__icontains=art_clean)
        )
        if norm_val:
            q_filter |= (
                Q(articulo__icontains=norm_val) | Q(codigo__icontains=norm_val)
            )

        qs = TipoLicencia.objects.filter(q_filter).distinct().order_by("codigo")

        if qs.exists():
            resultados = [
                {
                    "id": lic.pk,
                    "codigo": lic.codigo,
                    "articulo": lic.articulo,
                    "descripcion": lic.descripcion,
                    "cuadro": (
                        "IL-01"
                        if getattr(lic, "cuadro_mensual", "")
                        in ["IL-01", "DL-01"]
                        else "IL-02"
                    ),
                    "cuadro_mensual": getattr(lic, "cuadro_mensual", "IL-02"),
                    "categoria": lic.categoria,
                    "forma_pago": lic.forma_pago,
                    "goce_haberes": lic.goce_haberes,
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
