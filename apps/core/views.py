"""
Vistas para la aplicación Core (Panel de control / Dashboard principal).
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from apps.core.backup import generar_backup_completo_zip
from apps.core.mixins import SoloAdminInstitucionalMixin
from apps.core.services import obtener_panel_alertas_docentes


@login_required
def dashboard_home(request):
    """
    Vista principal del sistema Zunin (Dashboard de Bedelía).
    Requiere autenticación previa.
    Ticket 12 (RF-18): Integra panel de alertas de inasistencias docentes
    con cálculo de porcentajes respecto al límite legal anual optimizado en BD.
    """
    limite_param = request.GET.get("limite")
    try:
        limite_legal = int(limite_param) if limite_param else 15
    except (ValueError, TypeError):
        limite_legal = 15

    anio_param = request.GET.get("anio")
    try:
        anio = int(anio_param) if anio_param else timezone.now().year
    except (ValueError, TypeError):
        anio = timezone.now().year

    # QuerySet optimizado de todos los docentes activos con métricas de inasistencias
    todos_docentes = list(
        obtener_panel_alertas_docentes(
            limite_legal=limite_legal,
            anio=anio,
            solo_alertas=False,
        )
    )

    docentes_alertas = [
        d for d in todos_docentes if d.nivel_alerta in ("PRECAUCION", "CRITICO")
    ]

    total_precaucion = sum(
        1 for d in docentes_alertas if d.nivel_alerta == "PRECAUCION"
    )
    total_critico = sum(1 for d in docentes_alertas if d.nivel_alerta == "CRITICO")

    context = {
        "titulo": "Dashboard Institucional",
        "usuario": request.user,
        "limite_legal": limite_legal,
        "anio_alerta": anio,
        "docentes_alertas": docentes_alertas,
        "todos_docentes": todos_docentes,
        "total_docentes_seguimiento": len(todos_docentes),
        "total_alertas": len(docentes_alertas),
        "total_precaucion": total_precaucion,
        "total_critico": total_critico,
    }
    return render(request, "core/dashboard.html", context)


class ExportarBackupView(SoloAdminInstitucionalMixin, View):
    """
    Vista protegida para exportación de la base de datos completa en ZIP (Ticket 22).
    Restringida exclusivamente a Superusuarios y Admin_Institucional.
    Genera el archivo ZIP en memoria y lo envía como archivo adjunto de descarga.
    """

    def get(self, request, *args, **kwargs):
        zip_buffer, nombre_archivo, _ = generar_backup_completo_zip(
            usuario=request.user
        )

        response = HttpResponse(
            zip_buffer.getvalue(),
            content_type="application/zip",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{nombre_archivo}"'
        )
        response["Content-Length"] = len(zip_buffer.getvalue())
        return response


class ManualUsuarioView(LoginRequiredMixin, TemplateView):
    """
    Vista web oficial del Manual de Usuario del Sistema Zunin (Ticket 25).
    Presenta los 5 módulos institucionales interactivos y navegación rápida.
    """

    template_name = "core/manual_usuario.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Manual de Usuario Oficial"
        return context


class ManualUsuarioPdfView(LoginRequiredMixin, View):
    """
    Descarga del Manual de Usuario Oficial en formato PDF de alta fidelidad (Ticket 25).
    Verifica la existencia del archivo compilado y lo genera dinámicamente si falta
    o si el archivo Markdown fuente fue actualizado recientemente.
    """

    def get(self, request, *args, **kwargs):
        pdf_path = settings.BASE_DIR / "docs" / "manual_usuario_zunin.pdf"
        md_path = settings.BASE_DIR / "docs" / "manual_usuario.md"

        # Si el PDF no existe o es más viejo que el Markdown, regenerarlo
        regenerar = not pdf_path.exists()
        if not regenerar and md_path.exists():
            try:
                regenerar = pdf_path.stat().st_mtime < md_path.stat().st_mtime
            except OSError:
                regenerar = False

        if regenerar and md_path.exists():
            try:
                from generar_manual_pdf import generar_manual_pdf

                generar_manual_pdf(str(md_path), str(pdf_path))
            except Exception:
                pass

        if not pdf_path.exists():
            raise Http404("El manual en formato PDF no se encuentra disponible.")

        as_attachment = request.GET.get("view") != "inline"
        return FileResponse(
            open(pdf_path, "rb"),
            as_attachment=as_attachment,
            filename="Manual_Usuario_Zunin_IESETyFP.pdf",
            content_type="application/pdf",
        )
