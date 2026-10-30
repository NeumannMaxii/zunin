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
        self.assertNotContains(response, "/admin/")

    def test_enlace_admin_eliminado_para_todos_los_usuarios(self):
        """
        Valida que el acceso a /admin/ esté totalmente eliminado de la interfaz
        y no figure en el contenido HTML para ningún rol (común, staff o superusuario).
        """
        # 1. Usuario común
        self.client.login(username="docente_dashboard", password="password123")
        resp_comun = self.client.get(reverse("core:dashboard_home"))
        self.assertNotContains(resp_comun, "/admin/")

        # 2. Usuario staff
        User = get_user_model()
        User.objects.create_user(
            username="staff_user",
            password="password123",
            is_staff=True,
        )
        self.client.login(username="staff_user", password="password123")
        resp_staff = self.client.get(reverse("core:dashboard_home"))
        self.assertNotContains(resp_staff, "/admin/")

        # 3. Superusuario
        User.objects.create_superuser(
            username="superuser_test",
            password="password123",
            email="super@test.com",
        )
        self.client.login(username="superuser_test", password="password123")
        resp_super = self.client.get(reverse("core:dashboard_home"))
        self.assertNotContains(resp_super, "/admin/")
