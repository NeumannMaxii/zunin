"""
Pruebas automatizadas para los endpoints y configuración de la PWA.
"""

from django.test import SimpleTestCase


class PWATests(SimpleTestCase):
    def test_manifest_endpoint_retorna_json_correcto(self):
        """Verifica que /manifest.json esté disponible con content-type json."""
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get("Content-Type", "")
        self.assertIn("application/manifest+json", content_type)
        self.assertContains(response, "IESETyFP - Sistema Zunin")
        self.assertContains(response, "standalone")
        self.assertContains(response, "icon-192.png")
        self.assertContains(response, "icon-512.png")

    def test_serviceworker_endpoint_retorna_javascript_correcto(self):
        """Verifica que /serviceworker.js esté disponible con content-type js."""
        response = self.client.get("/serviceworker.js")
        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get("Content-Type", "")
        self.assertIn("application/javascript", content_type)
        self.assertContains(response, "zunin-pwa-v1")
        self.assertContains(response, "addEventListener('fetch'")

    def test_base_template_incluye_tags_pwa(self):
        """Verifica meta tags de soporte PWA en la plantilla base."""
        # Al acceder al login (página pública)
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'name="theme-color"')
        self.assertContains(response, 'name="mobile-web-app-capable"')
        sw_reg = "navigator.serviceWorker.register('/serviceworker.js')"
        self.assertContains(response, sw_reg)
