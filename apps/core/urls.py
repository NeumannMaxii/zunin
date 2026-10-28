"""
URLs para la aplicación Core.
"""

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
]
