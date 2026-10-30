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
        self.assertNotContains(response, 'href="/admin/"')

    def test_enlace_admin_solo_visible_para_staff(self):
        """
        Valida que el botón de Django Admin solo se renderice para usuarios is_staff.
        """
        # Usuario común (no staff) no ve el enlace a /admin/
        self.client.login(username="docente_dashboard", password="password123")
        resp_comun = self.client.get(reverse("core:dashboard_home"))
        self.assertNotContains(resp_comun, 'href="/admin/"')

        # Usuario staff ve el enlace a /admin/
        User = get_user_model()
        User.objects.create_user(
            username="admin_user",
            password="password123",
            is_staff=True,
        )
        self.client.login(username="admin_user", password="password123")
        resp_staff = self.client.get(reverse("core:dashboard_home"))
        self.assertContains(resp_staff, 'href="/admin/"')
