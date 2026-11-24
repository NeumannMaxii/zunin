"""
Pruebas automatizadas para el Ticket 23:
Reubicación del Botón «Justificación Diferida» a la Pantalla de Asistencia.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class Ticket23ReubicacionJustificacionDiferidaTests(TestCase):
    def setUp(self):
        self.user_bedel = User.objects.create_user(
            username="bedel_t23",
            password="password123",
            is_staff=True,
        )
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.user_bedel.groups.add(grupo_bedelia)
        self.client.force_login(self.user_bedel)

    def test_asistencia_list_contiene_boton_justificacion_diferida(self):
        """
        La pantalla de registros de asistencia (/asistencia/) debe incluir
        el botón 'Justificación Diferida' en su barra superior de acciones.
        """
        url = reverse("asistencia:asistencia_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url_justif = reverse("licencias:justificacion_diferida")
        self.assertContains(response, f'href="{url_justif}"')
        self.assertContains(response, "Justificación Diferida")

    def test_planilla_list_no_contiene_boton_justificacion_diferida_en_cabecera(self):
        """
        La pantalla de planillas (/licencias/planillas/) no debe tener el botón
        de justificación diferida en su cabecera para evitar redundancia.
        """
        url = reverse("licencias:planilla_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # El botón ya no debe estar presente en la barra de acciones de planillas
        self.assertNotIn('<!-- Botón Secundario: Justificación Diferida -->', content)

    def test_justificacion_diferida_breadcrumbs_y_volver_a_asistencia(self):
        """
        La pantalla de justificación diferida debe incluir breadcrumbs
        hacia Asistencia y botón 'Volver a Asistencia'.
        """
        url = reverse("licencias:justificacion_diferida")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Volver a Asistencia")
        url_asistencia = reverse("asistencia:asistencia_list")
        self.assertContains(response, f'href="{url_asistencia}"')
