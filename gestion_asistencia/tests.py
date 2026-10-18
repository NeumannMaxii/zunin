from django.test import TestCase, Client
from django.urls import reverse
from django.apps import apps
from gestion_asistencia.apps import GestionAsistenciaConfig


class GestionAsistenciaAppTests(TestCase):
    """Pruebas de configuración y arranque de la aplicación."""

    def test_app_is_installed(self):
        """Verifica que la app gestion_asistencia esté registrada en el proyecto."""
        self.assertTrue(apps.is_installed("gestion_asistencia"))

    def test_app_config_name(self):
        """Verifica que el AppConfig tenga el nombre correcto."""
        self.assertEqual(GestionAsistenciaConfig.name, "gestion_asistencia")


class VistaPrincipalTests(TestCase):
    """Pruebas para la vista inicial del dashboard de Bedelía."""

    def setUp(self):
        self.client = Client()

    def test_index_url_status_code(self):
        """Verifica que la página principal retorne código HTTP 200."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertEqual(response.status_code, 200)

    def test_index_template_used(self):
        """Verifica que se usen las plantillas base.html e index.html."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "gestion_asistencia/index.html")

    def test_index_context_and_content(self):
        """Verifica la presencia de la marca institucional IESETyFP."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertContains(response, "IESETyFP")
        self.assertContains(response, "Bedelía")
