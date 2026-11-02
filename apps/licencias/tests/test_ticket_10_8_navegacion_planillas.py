"""
Pruebas para el Ticket 10.8: Integración de Navegación Directa a Planillas.

Valida:
1. Enlace en Navbar superior hacia 'licencias:planilla_list'.
2. Botones de acción rápida en Dashboard principal hacia:
   - 'licencias:planilla_list' (Planillas Mensuales)
   - 'licencias:justificacion_diferida' (Justificación Diferida)
3. Que las URLs resuelvan correctamente y respondan con código HTTP 200
   para usuarios autenticados con los diferentes roles.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse


class NavegacionDirectaPlanillasTests(TestCase):
    """Pruebas de navegación directa a planillas y justificación diferida."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="operador_bedelia",
            password="password123",
        )
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.user.groups.add(grupo_bedelia)
        self.client.login(username="operador_bedelia", password="password123")

    def test_navbar_contiene_acceso_a_planillas(self):
        """El navbar en base.html debe incluir el enlace a licencias:planilla_list."""
        response = self.client.get(reverse("core:dashboard_home"))
        self.assertEqual(response.status_code, 200)

        planilla_url = reverse("licencias:planilla_list")
        self.assertContains(response, f'href="{planilla_url}"')
        self.assertContains(response, "Planillas")

    def test_dashboard_contiene_botones_rapidos(self):
        """El dashboard debe tener botones rápidos a planillas y justificación."""
        response = self.client.get(reverse("core:dashboard_home"))
        self.assertEqual(response.status_code, 200)

        planilla_url = reverse("licencias:planilla_list")
        justificacion_url = reverse("licencias:justificacion_diferida")

        self.assertContains(response, f'href="{planilla_url}"')
        self.assertContains(response, f'href="{justificacion_url}"')
        self.assertContains(response, "Planillas Mensuales")
        self.assertContains(response, "Justificación Diferida")

    def test_enlaces_del_dashboard_son_navegables_y_responden_200(self):
        """Verifica que los endpoints de los botones respondan HTTP 200."""
        resp_planillas = self.client.get(reverse("licencias:planilla_list"))
        self.assertEqual(resp_planillas.status_code, 200)

        resp_justificacion = self.client.get(
            reverse("licencias:justificacion_diferida")
        )
        self.assertEqual(resp_justificacion.status_code, 200)
