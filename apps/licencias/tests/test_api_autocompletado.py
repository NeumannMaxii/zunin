"""
Pruebas automatizadas para la API de autocompletado de licencias (Ticket 10).
Valida:
- HTTP 400 Bad Request si falta el parámetro 'articulo' o está vacío.
- HTTP 200 con array vacío [] si no hay coincidencias.
- HTTP 200 con array [...] si encuentra coincidencias en BD o catálogo.
- Mapeo de rutas en /api/autocompletar/, /api/licencias/autocompletar/ y licencias.
"""

from django.test import TestCase
from django.urls import reverse
from apps.licencias.models import TipoLicencia


class APIAutocompletarLicenciaTests(TestCase):
    """
    Casos de prueba para el endpoint GET /api/.../autocompletar/?articulo=<codigo>.
    """

    def setUp(self):
        self.licencia = TipoLicencia.objects.create(
            codigo="LIC-999Z",
            articulo="Art. 999-Z",
            descripcion="Licencia Extraordinaria de Prueba",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            goce_haberes=True,
            cuadro_mensual="IL-01",
        )

    def test_sin_parametro_articulo_devuelve_400(self):
        """Verifica que omitir el parámetro ?articulo= retorne HTTP 400 Bad Request."""
        rutas = [
            "/api/autocompletar/",
            "/api/licencias/autocompletar/",
            "/licencias/api/autocompletar/",
            "/licencias/autocompletar/",
            reverse("api_licencias:autocompletar"),
            reverse("api_licencias:licencias_autocompletar"),
            reverse("licencias:api_autocompletar"),
            reverse("licencias:autocompletar"),
        ]
        for url in set(rutas):
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code,
                400,
                f"La ruta {url} no retornó 400 ante omisión de parámetro",
            )
            data = resp.json()
            self.assertIn("error", data)

    def test_parametro_articulo_vacio_devuelve_400(self):
        """Verifica que ?articulo= con string vacío o espacios retorne HTTP 400."""
        resp_vacio = self.client.get("/api/autocompletar/?articulo=")
        self.assertEqual(resp_vacio.status_code, 400)
        self.assertIn("error", resp_vacio.json())

        resp_espacios = self.client.get("/api/autocompletar/?articulo=%20%20%20")
        self.assertEqual(resp_espacios.status_code, 400)
        self.assertIn("error", resp_espacios.json())

    def test_articulo_sin_coincidencia_devuelve_200_array_vacio(self):
        """Verifica que una búsqueda sin resultados retorne HTTP 200 con []."""
        resp = self.client.get(
            "/api/autocompletar/?articulo=inexistente_totalmente_99999"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertEqual(data, [])

    def test_articulo_con_coincidencia_en_db_devuelve_200_con_datos(self):
        """
        Verifica coincidencia exitosa en base de datos retornando
        HTTP 200 con [...].
        """
        resp = self.client.get("/api/autocompletar/?articulo=999-Z")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

        item = data[0]
        self.assertEqual(item["codigo"], "LIC-999Z")
        self.assertEqual(item["articulo"], "Art. 999-Z")
        self.assertEqual(item["descripcion"], "Licencia Extraordinaria de Prueba")
        self.assertEqual(item["cuadro"], "IL-01")

    def test_articulo_con_coincidencia_parcial_en_db(self):
        """Valida que una búsqueda parcial (ej: '999') encuentre el registro."""
        resp = self.client.get("/api/autocompletar/?articulo=999")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(it["codigo"] == "LIC-999Z" for it in data))

    def test_articulo_catalogo_estatutario_estandar(self):
        """Valida que artículos del estatuto docente (ej: '340-A') se autocompleten."""
        resp = self.client.get("/api/autocompletar/?articulo=340-A")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(any(it["codigo"] == "LIC-340A" for it in data))

    def test_articulo_con_prefijo_art_o_espacios(self):
        """Valida tolerancia a prefijos 'Art. ' o 'Art' en la búsqueda."""
        resp = self.client.get("/api/autocompletar/?articulo=Art.%20340-A")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(it["codigo"] == "LIC-340A" for it in data))
