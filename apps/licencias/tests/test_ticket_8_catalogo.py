"""
Pruebas automatizadas para Ticket 8: Pantalla 2 — Catálogo Licencias.
Valida:
- Vista de solo lectura (TipoLicenciaListView) con autenticación obligatoria.
- Filtros GET por cuadro (?cuadro=IL-01 o ?cuadro=IL-02).
- Búsqueda por texto (?q=) en código, artículo o descripción.
- Combinación de filtros y preservación de parámetros en paginación.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.licencias.models import TipoLicencia


class CatalogoLicenciasTicket8Tests(TestCase):
    """
    Suite de pruebas para validar los criterios de aceptación del Ticket 8:
    1. Vista de solo lectura.
    2. Filtros GET por cuadro (?cuadro=IL-01 o ?cuadro=IL-02).
    3. Barra de búsqueda por texto (?q=).
    4. Aplicación precisa y combinada de filtros.
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="bedelia_user",
            password="password123",
        )
        self.client.login(username="bedelia_user", password="password123")
        self.url = reverse("licencias:tipolicencia_list")

        # Licencias de prueba para Cuadro IL-01 (Salud y Enfermedad)
        self.lic_340a = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            hoja_pdf="1-2",
            tope_anual=30,
            activo=True,
        )
        self.lic_340d = TipoLicencia.objects.create(
            codigo="LIC-340D",
            articulo="340-D",
            descripcion="Atención Familiar Enfermo",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            hoja_pdf="1-2",
            tope_anual=20,
            activo=True,
        )

        # Licencias de prueba para Cuadro IL-02 (Especiales e Inasistencias)
        self.lic_341 = TipoLicencia.objects.create(
            codigo="LIC-341",
            articulo="341",
            descripcion="Licencia por Maternidad",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-02",
            hoja_pdf="3-6",
            tope_anual=135,
            activo=True,
        )
        self.lic_344 = TipoLicencia.objects.create(
            codigo="LIC-344",
            articulo="344",
            descripcion="Duelo Familiar",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-02",
            hoja_pdf="3-6",
            tope_anual=5,
            activo=True,
        )
        self.lic_346 = TipoLicencia.objects.create(
            codigo="LIC-346",
            articulo="346",
            descripcion="Razones Particulares",
            categoria="PERMISO",
            forma_pago="SIN_GOCE",
            cuadro_mensual="IL-02",
            hoja_pdf="3-6",
            tope_anual=6,
            activo=True,
        )

    def test_catalogo_requiere_autenticacion(self):
        """Verifica que usuarios anónimos sean redirigidos al login."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_catalogo_acceso_exitoso_autenticado(self):
        """Verifica que un usuario autenticado acceda al catálogo con código 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "licencias/tipolicencia_list.html")
        self.assertContains(response, "Catálogo de Licencias Estatutarias")
        self.assertContains(response, "Pantalla 2")
        self.assertContains(response, "Solo Lectura")

    def test_catalogo_muestra_todos_sin_filtro(self):
        """Sin filtros GET retorna el catálogo completo de licencias."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        licencias = response.context["tipo_licencias"]
        self.assertEqual(licencias.count(), 5)
        self.assertContains(response, "LIC-340A")
        self.assertContains(response, "LIC-340D")
        self.assertContains(response, "LIC-341")
        self.assertContains(response, "LIC-344")
        self.assertContains(response, "LIC-346")

    def test_filtro_por_cuadro_il01(self):
        """
        Ticket 8: Filtro ?cuadro=IL-01 muestra solo licencias del cuadro IL-01.
        """
        response = self.client.get(self.url, {"cuadro": "IL-01"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        codigos = [lic.codigo for lic in licencias]
        self.assertIn("LIC-340A", codigos)
        self.assertIn("LIC-340D", codigos)
        self.assertNotIn("LIC-341", codigos)
        self.assertNotIn("LIC-344", codigos)
        self.assertNotIn("LIC-346", codigos)
        self.assertEqual(response.context["cuadro"], "IL-01")

    def test_filtro_por_cuadro_il02(self):
        """
        Ticket 8: Filtro ?cuadro=IL-02 muestra solo licencias del cuadro IL-02.
        """
        response = self.client.get(self.url, {"cuadro": "IL-02"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        codigos = [lic.codigo for lic in licencias]
        self.assertNotIn("LIC-340A", codigos)
        self.assertNotIn("LIC-340D", codigos)
        self.assertIn("LIC-341", codigos)
        self.assertIn("LIC-344", codigos)
        self.assertIn("LIC-346", codigos)
        self.assertEqual(response.context["cuadro"], "IL-02")

    def test_filtro_cuadro_case_insensitive(self):
        """El parámetro cuadro normaliza mayúsculas/minúsculas (?cuadro=il-01)."""
        response = self.client.get(self.url, {"cuadro": "il-01"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 2)
        codigos = [lic.codigo for lic in licencias]
        self.assertIn("LIC-340A", codigos)
        self.assertIn("LIC-340D", codigos)

    def test_busqueda_por_codigo_q(self):
        """Ticket 8: Búsqueda ?q= por código exacto o parcial."""
        response = self.client.get(self.url, {"q": "340D"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0].codigo, "LIC-340D")

    def test_busqueda_por_articulo_q(self):
        """Ticket 8: Búsqueda ?q= por número o texto de artículo legal."""
        response = self.client.get(self.url, {"q": "340-A"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0].codigo, "LIC-340A")

    def test_busqueda_por_descripcion_q(self):
        """Ticket 8: Búsqueda ?q= por palabra en la descripción estatutaria."""
        response = self.client.get(self.url, {"q": "Maternidad"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0].codigo, "LIC-341")

    def test_filtros_combinados_cuadro_y_q(self):
        """
        Ticket 8: Búsqueda combinada de cuadro y texto (?cuadro=IL-02&q=Duelo).
        """
        response = self.client.get(self.url, {"cuadro": "IL-02", "q": "Duelo"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 1)
        self.assertEqual(licencias[0].codigo, "LIC-344")

    def test_busqueda_sin_resultados_muestra_estado_vacio(self):
        """Búsqueda sin coincidencias muestra mensaje descriptivo en el template."""
        response = self.client.get(self.url, {"q": "TextoInexistenteZunin999"})
        self.assertEqual(response.status_code, 200)
        licencias = list(response.context["tipo_licencias"])
        self.assertEqual(len(licencias), 0)
        self.assertContains(response, "No se encontraron licencias")
        self.assertContains(response, "Ver catálogo completo")

    def test_vista_es_solo_lectura_rechaza_post(self):
        """
        Verifica que la vista sea de solo lectura: peticiones POST no permitidas (405).
        """
        response = self.client.post(self.url, {"codigo": "HACK-999"})
        self.assertEqual(response.status_code, 405)

    def test_paginacion_preserva_parametros_get(self):
        """
        Verifica que la paginación preserve ?cuadro=IL-01 y ?q= al navegar páginas.
        """
        for i in range(1, 30):
            TipoLicencia.objects.create(
                codigo=f"LIC-EXTRA-{i:03d}",
                articulo=f"Art. {400 + i}",
                descripcion=f"Licencia adicional {i}",
                categoria="LICENCIA",
                forma_pago="CON_GOCE",
                cuadro_mensual="IL-01",
                activo=True,
            )

        response = self.client.get(self.url, {"cuadro": "IL-01"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        # Verifica que el link a la página 2 incluya el filtro de cuadro
        self.assertContains(response, "page=2")
        self.assertContains(response, "cuadro=IL-01")
