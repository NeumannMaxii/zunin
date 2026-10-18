from django.urls import path
from . import views

app_name = "gestion_asistencia"

urlpatterns = [
    path("", views.index_view, name="index"),
]
