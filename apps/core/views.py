"""
Vistas para la aplicación Core (Panel de control / Dashboard principal).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
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
