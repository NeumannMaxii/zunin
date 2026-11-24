"""
Pruebas automatizadas para el Ticket 25:
Manual de Usuario Oficial del Sistema Zunin (Web y PDF).
"""

import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from generar_manual_pdf import generar_manual_pdf

User = get_user_model()


class Ticket25ManualUsuarioTests(TestCase):
    def setUp(self):
        # Grupos de seguridad
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )

        # Usuario autenticado de Bedelía
        self.user_bedelia = User.objects.create_user(
            username="bedelia_manual",
            password="password123",
            first_name="Zunilda",
            last_name="Aquino",
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.url_web = reverse("core:manual_usuario")
        self.url_pdf = reverse("core:manual_usuario_pdf")

    def test_acceso_anonimo_redirige_a_login(self):
        """Usuarios no autenticados deben ser redirigidos al login institucional."""
        res_web = self.client.get(self.url_web)
        self.assertEqual(res_web.status_code, 302)
        self.assertIn("/login/", res_web.url)

        res_pdf = self.client.get(self.url_pdf)
        self.assertEqual(res_pdf.status_code, 302)
        self.assertIn("/login/", res_pdf.url)

    def test_vista_web_manual_usuario_autenticado(self):
        """Usuario autenticado puede acceder a /manual/ con los 5 módulos oficiales."""
        self.client.force_login(self.user_bedelia)
        response = self.client.get(self.url_web)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/manual_usuario.html")

        # Botón destacado de descarga PDF oficial
        self.assertContains(response, "Descargar PDF Oficial")
        self.assertContains(response, self.url_pdf)

        # Contenido de los 5 módulos requeridos
        self.assertContains(response, "Módulo 1")
        self.assertContains(response, "Inicio y Roles")
        self.assertContains(response, "Módulo 2")
        self.assertContains(response, "Planta Docente y Cargos")
        self.assertContains(response, "Módulo 3")
        self.assertContains(response, "Asistencia y Parte Diario")
        self.assertContains(response, "Módulo 4")
        self.assertContains(response, "Régimen de Licencias y Planillas Mensuales")
        self.assertContains(response, "Módulo 5")
        self.assertContains(response, "Feriados y Resguardo de Datos")

        # Criterios específicos de tickets integrados
        self.assertContains(response, "Instrumento / Disposición de Designación")
        self.assertContains(response, "Justificación Diferida")
        self.assertContains(response, "Vista Planilla Continua")
        self.assertContains(response, "BOM UTF-8")

    def test_enlaces_manual_en_base_html(self):
        """
        El enlace al Manual debe estar disponible en la barra de navegación
        y pie de página.
        """
        self.client.force_login(self.user_bedelia)
        # Probamos desde el dashboard
        response = self.client.get(reverse("core:dashboard_home"))
        self.assertEqual(response.status_code, 200)

        # Enlace visible en navbar y en footer
        self.assertContains(response, self.url_web)
        self.assertContains(response, "Manual de Usuario")

    def test_descarga_pdf_oficial_attachment(self):
        """Descarga de PDF oficial en modo attachment."""
        self.client.force_login(self.user_bedelia)
        response = self.client.get(self.url_pdf)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("Manual_Usuario_Zunin_IESETyFP.pdf", disposition)

        # Verificar cabecera mágica de PDF
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 5000)

    def test_descarga_pdf_oficial_inline(self):
        """Visualización de PDF oficial en modo inline para el navegador."""
        self.client.force_login(self.user_bedelia)
        response = self.client.get(f"{self.url_pdf}?view=inline")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])

    def test_script_generador_pdf_programatico(self):
        """Verificar que generar_manual_pdf funciona como función importable."""
        md_path = str(settings.BASE_DIR / "docs" / "manual_usuario.md")
        pdf_path = str(settings.BASE_DIR / "docs" / "manual_usuario_zunin.pdf")

        self.assertTrue(os.path.exists(md_path))
        resultado = generar_manual_pdf(md_path, pdf_path)
        self.assertTrue(resultado)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 5000)
