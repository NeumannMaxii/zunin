"""
Pruebas automatizadas para el Ticket 18.4:
Ingesta del Catálogo Maestro Oficial de Licencias (155 Artículos Ley 647-E).

Valida:
1. Ejecución del comando `python manage.py poblar_catalogo_licencias`.
2. Ingesta de al menos 100 registros (155 códigos oficiales).
3. Clasificación oficial de cuadro:
   - Razones de Salud (códigos '01.*' o '1.*') imputan a 'IL-01' (Hojas 1-2).
   - Otras causales, permisos y exámenes imputan a 'IL-02' (Hojas 3-6).
4. Idempotencia total: reejecutar el comando no genera duplicados.
5. Funcionamiento de `autocompletar_por_articulo` priorizando registros en BD.
6. Soporte para parámetro opcional `--archivo`.
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from apps.licencias.models import TipoLicencia


class PoblarCatalogoLicenciasTicket18_4Tests(TestCase):
    """Pruebas unitarias para el comando poblar_catalogo_licencias e idempotencia."""

    def test_ejecucion_comando_poblar_catalogo_licencias(self):
        """
        Valida que el comando inserte los 155 códigos oficiales de licencia
        y reporte el resumen en stdout.
        """
        out = StringIO()
        call_command("poblar_catalogo_licencias", stdout=out)
        salida = out.getvalue()

        self.assertIn("Ingesta de Catálogo Maestro finalizada exitosamente", salida)
        self.assertIn("Total códigos procesados: 155", salida)

        # Validar existencia de al menos 100 registros (Criterio del Ticket 18.4)
        total_bd = TipoLicencia.objects.count()
        self.assertGreaterEqual(total_bd, 100)
        self.assertGreaterEqual(total_bd, 155)

    def test_clasificacion_automatica_cuadro_salud_e_inasistencias(self):
        """
        Valida la Regla Oficial de Cuadro:
        - Códigos que inician con '01.' o '1.' van a 'IL-01' (hoja '1-2').
        - Códigos que inician con '02.' a '05.' van a 'IL-02' (hoja '3-6').
        """
        call_command("poblar_catalogo_licencias")

        # Códigos de Salud (01.*)
        salud_01_01 = TipoLicencia.objects.get(codigo="01.01.04")
        self.assertEqual(salud_01_01.cuadro_mensual, "IL-01")
        self.assertEqual(salud_01_01.hoja_pdf, "1-2")

        salud_largo_trat = TipoLicencia.objects.get(codigo="01.02.01")
        self.assertEqual(salud_largo_trat.cuadro_mensual, "IL-01")
        self.assertEqual(salud_largo_trat.hoja_pdf, "1-2")

        # Códigos de Permisos, Exámenes o Razones Especiales
        donacion_sangre = TipoLicencia.objects.get(codigo="3.8.1")
        self.assertEqual(donacion_sangre.cuadro_mensual, "IL-02")
        self.assertEqual(donacion_sangre.hoja_pdf, "3-6")

        violencia_genero = TipoLicencia.objects.get(codigo="2.20.1")
        self.assertEqual(violencia_genero.cuadro_mensual, "IL-02")
        self.assertEqual(violencia_genero.hoja_pdf, "3-6")

    def test_idempotencia_comando_no_genera_duplicados(self):
        """
        Verifica que reejecutar el comando no aumente el conteo de registros en BD.
        """
        # Primera ejecución
        call_command("poblar_catalogo_licencias")
        total_inicial = TipoLicencia.objects.count()

        # Segunda ejecución
        out2 = StringIO()
        call_command("poblar_catalogo_licencias", stdout=out2)
        total_segunda = TipoLicencia.objects.count()

        self.assertEqual(total_inicial, total_segunda)
        salida2 = out2.getvalue()
        self.assertIn("Creados: 0", salida2)

    def test_autocompletar_por_articulo_utiliza_registros_bd(self):
        """
        Verifica que autocompletar_por_articulo consulte y encuentre
        artículos persistidos en la base de datos por el catálogo oficial.
        """
        call_command("poblar_catalogo_licencias")

        # Búsqueda por artículo de salud (340-A)
        res_salud = TipoLicencia.autocompletar_por_articulo("340-A")
        self.assertTrue(bool(res_salud["codigo"]))
        self.assertEqual(res_salud["cuadro"], "IL-01")

        # Búsqueda por código oficial
        res_codigo = TipoLicencia.autocompletar_por_articulo("01.02.01")
        self.assertEqual(res_codigo["codigo"], "01.02.01")
        self.assertEqual(res_codigo["cuadro"], "IL-01")

        # Búsqueda por artículo de permisos (320-C Donación de Sangre)
        res_permiso = TipoLicencia.autocompletar_por_articulo("320-C")
        self.assertEqual(res_permiso["codigo"], "3.8.1")
        self.assertEqual(res_permiso["cuadro"], "IL-02")

    def test_parametro_archivo_opcional_y_fallback_dataset(self):
        """
        Valida que el comando soporte el parámetro --archivo y que si el archivo
        no existe, use transparentemente el dataset oficial integrado.
        """
        out = StringIO()
        call_command(
            "poblar_catalogo_licencias",
            archivo="ruta/inexistente/catalogo.xlsx",
            stdout=out,
        )
        salida = out.getvalue()
        self.assertIn("dataset oficial integrado", salida)
        self.assertGreaterEqual(TipoLicencia.objects.count(), 100)
