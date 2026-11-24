"""
URLs para la aplicación Core.
"""

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("dashboard/", views.dashboard_home, name="dashboard"),
    path(
        "backup/exportar/",
        views.ExportarBackupView.as_view(),
        name="exportar_backup",
    ),
    path(
        "manual/",
        views.ManualUsuarioView.as_view(),
        name="manual_usuario",
    ),
    path(
        "manual/pdf/",
        views.ManualUsuarioPdfView.as_view(),
        name="manual_usuario_pdf",
    ),
]
