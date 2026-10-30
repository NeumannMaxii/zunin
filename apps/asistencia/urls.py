"""
Rutas URL para apps.asistencia.
"""

from django.urls import path
from . import views

app_name = "asistencia"

urlpatterns = [
    path("", views.RegistroAsistenciaListView.as_view(), name="asistencia_list"),
    path("carga-masiva/", views.CargaDiariaMasivaView.as_view(), name="carga_masiva"),
    path(
        "justificaciones-lote/",
        views.JustificacionesLoteView.as_view(),
        name="justificaciones_lote",
    ),
]
