"""
Pruebas automatizadas para el Dashboard Core (Ticket 2):
- Validación de acceso protegido mediante @login_required.
- Respuesta HTTP 302 (redirect al login) para usuarios anónimos.
- Respuesta HTTP 200 y renderizado correcto para usuarios autenticados.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class DashboardCoreTests(TestCase):
    """Pruebas para la vista dashboard_home."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="docente_dashboard",
            password="password123",
        )

    def test_dashboard_usuario_anonimo_redirige_a_login(self):
        """
        4. Valida que un usuario anónimo que intenta acceder al Dashboard
        sea redirigido con HTTP 302 hacia la pantalla de login.
        """
        response = self.client.get(reverse("core:dashboard_home"))
        self.assertEqual(response.status_code, 302)
        login_url = reverse("login")
        self.assertIn(login_url, response.url)

    def test_dashboard_usuario_autenticado_retorna_200(self):
        """
        4. Valida que un usuario autenticado acceda exitosamente con HTTP 200
        y utilice las plantillas base.html y core/dashboard.html.
        """
        self.client.login(username="docente_dashboard", password="password123")
        response = self.client.get(reverse("core:dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertContains(response, "Dashboard Institucional")
        self.assertContains(response, "docente_dashboard")
        self.assertContains(response, "Proyecto Zunin")
