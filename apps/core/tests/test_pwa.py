"""
Pruebas automatizadas para los endpoints y configuración de la Progressive Web App (PWA).
"""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class PWATests(SimpleTestCase):
    def test_manifest_endpoint_retorna_json_correcto(self):
        """Verifica que /manifest.json esté disponible y con content-type correcto."""
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response.headers.get("Content-Type", ""))
        self.assertContains(response, "IESETyFP - Sistema Zunin")
        self.assertContains(response, "standalone")
        self.assertContains(response, "icon-192.png")
        self.assertContains(response, "icon-512.png")

    def test_serviceworker_endpoint_retorna_javascript_correcto(self):
        """Verifica que /serviceworker.js esté disponible en la raíz y con content-type js."""
        response = self.client.get("/serviceworker.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.headers.get("Content-Type", ""))
        self.assertContains(response, "zunin-pwa-v1")
        self.assertContains(response, "addEventListener('fetch'")

    def test_base_template_incluye_tags_pwa(self):
        """Verifica que las plantillas incluyan los meta tags para soporte de app instalable."""
        # Al acceder al login (página pública)
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'name="theme-color"')
        self.assertContains(response, 'name="mobile-web-app-capable"')
        self.assertContains(response, "navigator.serviceWorker.register('/serviceworker.js')")
