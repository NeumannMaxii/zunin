"""
Vistas para la aplicación Core (Panel de control / Dashboard principal).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard_home(request):
    """
    Vista principal del sistema Zunin (Dashboard de Bedelía).
    Requiere autenticación previa.
    """
    context = {
        "titulo": "Dashboard Institucional",
        "usuario": request.user,
    }
    return render(request, "core/dashboard.html", context)
