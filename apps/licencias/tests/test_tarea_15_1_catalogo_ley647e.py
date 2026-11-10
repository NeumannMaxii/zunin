"""
Pruebas automatizadas para Tarea 15.1:
Actualización del modelo de Catálogo (TipoLicencia) según Ley 647-E.

Valida:
- Persistencia y aceptación de todos los atributos normativos requeridos:
  * codigo
  * regimen (TIT, INT, SUP)
  * articulo
  * categoria (Ordinaria, Extraordinaria, Permiso)
  * forma_goce (100%, 50%, Sin goce, Escala)
  * duracion_maxima
  * unidad (Corridos, Hábiles, Laborables, Horas)
  * periodo_tope (Año calendario, Año escolar, Decenio, Sin tope, Hecho)
  * antiguedad_minima_meses
- Sincronización y retrocompatibilidad de goce de haberes y forma de pago.
- Filtrado y consultas por atributos normativos.
"""

from django.test import TestCase
from apps.licencias.models import TipoLicencia


class TipoLicenciaLey647ETests(TestCase):
    """
    Suite de pruebas para validar la ampliación del modelo TipoLicencia (Tarea 15.1).
    """

    def test_creacion_tipo_licencia_con_atributos_ley_647e(self):
        """
        Verifica que TipoLicencia acepte y persista todos los campos nuevos
        conforme a las especificaciones técnicas de la Ley 647-E.
        """
        lic = TipoLicencia.objects.create(
            codigo="LIC-647E-01",
            regimen="TIT",
            articulo="340-A",
            descripcion="Afecciones comunes y corto tratamiento",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=30,
            unidad="Corridos",
            periodo_tope="Año calendario",
            antiguedad_minima_meses=0,
            cuadro_mensual="IL-01",
            activo=True,
        )

        lic.refresh_from_db()
        self.assertEqual(lic.codigo, "LIC-647E-01")
        self.assertEqual(lic.regimen, "TIT")
        self.assertEqual(lic.articulo, "340-A")
        self.assertEqual(lic.categoria, "Ordinaria")
        self.assertEqual(lic.forma_goce, "100%")
        self.assertEqual(lic.duracion_maxima, 30)
        self.assertEqual(lic.unidad, "Corridos")
        self.assertEqual(lic.periodo_tope, "Año calendario")
        self.assertEqual(lic.antiguedad_minima_meses, 0)
        self.assertTrue(lic.goce_haberes)
        self.assertEqual(lic.forma_pago, "CON_GOCE")

    def test_variaciones_regimen_y_categoria(self):
        """
        Verifica las opciones de régimen (TIT, INT, SUP) y
        categoría (Ordinaria, Extraordinaria, Permiso).
        """
        lic_int = TipoLicencia.objects.create(
            codigo="LIC-INT-EXTRA",
            regimen="INT",
            articulo="341",
            descripcion="Licencia por maternidad",
            categoria="Extraordinaria",
            forma_goce="100%",
            duracion_maxima=135,
            unidad="Corridos",
            periodo_tope="Hecho",
            antiguedad_minima_meses=6,
        )
        self.assertEqual(lic_int.regimen, "INT")
        self.assertEqual(lic_int.categoria, "Extraordinaria")
        self.assertEqual(lic_int.periodo_tope, "Hecho")
        self.assertEqual(lic_int.antiguedad_minima_meses, 6)

        lic_sup = TipoLicencia.objects.create(
            codigo="LIC-SUP-PERM",
            regimen="SUP",
            articulo="347",
            descripcion="Permiso gremial o especial",
            categoria="Permiso",
            forma_goce="100%",
            duracion_maxima=2,
            unidad="Horas",
            periodo_tope="Año calendario",
            antiguedad_minima_meses=0,
        )
        self.assertEqual(lic_sup.regimen, "SUP")
        self.assertEqual(lic_sup.categoria, "Permiso")
        self.assertEqual(lic_sup.unidad, "Horas")

    def test_formas_de_goce_y_sincronizacion(self):
        """
        Verifica las opciones de forma_goce (100%, 50%, Sin goce, Escala)
        y la consistencia con forma_pago y goce_haberes.
        """
        lic_sin_goce = TipoLicencia.objects.create(
            codigo="LIC-SIN-GOCE",
            regimen="TIT",
            articulo="346",
            descripcion="Razones particulares",
            categoria="Extraordinaria",
            forma_goce="Sin goce",
            duracion_maxima=6,
            unidad="Laborables",
            periodo_tope="Año escolar",
        )
        self.assertEqual(lic_sin_goce.forma_goce, "Sin goce")
        self.assertFalse(lic_sin_goce.goce_haberes)
        self.assertEqual(lic_sin_goce.forma_pago, "SIN_GOCE")

        lic_50 = TipoLicencia.objects.create(
            codigo="LIC-50-GOCE",
            regimen="TIT",
            articulo="340-B",
            descripcion="Largo tratamiento segunda etapa",
            categoria="Extraordinaria",
            forma_goce="50%",
            duracion_maxima=365,
            unidad="Corridos",
            periodo_tope="Decenio",
            antiguedad_minima_meses=12,
        )
        self.assertEqual(lic_50.forma_goce, "50%")
        self.assertTrue(lic_50.goce_haberes)
        self.assertEqual(lic_50.forma_pago, "CINCUENTA_PORCIENTO")

        lic_escala = TipoLicencia.objects.create(
            codigo="LIC-ESCALA",
            regimen="TIT",
            articulo="340-B-ESC",
            descripcion="Afección prolongada según escala",
            categoria="Extraordinaria",
            forma_goce="Escala",
            duracion_maxima=730,
            unidad="Corridos",
            periodo_tope="Decenio",
        )
        self.assertEqual(lic_escala.forma_goce, "Escala")
        self.assertTrue(lic_escala.goce_haberes)

    def test_opciones_periodo_tope_y_unidad(self):
        """
        Verifica las distintas combinaciones de periodo_tope y unidad.
        """
        lic_habiles = TipoLicencia.objects.create(
            codigo="LIC-HABILES",
            regimen="TIT",
            articulo="342",
            descripcion="Paternidad y cuidados familiares",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=15,
            unidad="Hábiles",
            periodo_tope="Hecho",
        )
        self.assertEqual(lic_habiles.unidad, "Hábiles")
        self.assertEqual(lic_habiles.periodo_tope, "Hecho")

        lic_sin_tope = TipoLicencia.objects.create(
            codigo="LIC-SIN-TOPE",
            regimen="TIT",
            articulo="340-C",
            descripcion="Accidente de trabajo y enfermedad profesional",
            categoria="Extraordinaria",
            forma_goce="100%",
            duracion_maxima=None,
            unidad="Corridos",
            periodo_tope="Sin tope",
        )
        self.assertIsNone(lic_sin_tope.duracion_maxima)
        self.assertEqual(lic_sin_tope.periodo_tope, "Sin tope")

    def test_consultas_y_filtrados_por_nuevos_campos(self):
        """
        Verifica que se puedan ejecutar queries eficientes de Django ORM
        filtrando por los atributos agregados.
        """
        TipoLicencia.objects.create(
            codigo="LIC-TIT-ORD",
            regimen="TIT",
            articulo="350",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=10,
            unidad="Hábiles",
            periodo_tope="Año calendario",
        )
        TipoLicencia.objects.create(
            codigo="LIC-INT-EXT",
            regimen="INT",
            articulo="351",
            categoria="Extraordinaria",
            forma_goce="Sin goce",
            duracion_maxima=30,
            unidad="Corridos",
            periodo_tope="Año escolar",
        )

        qs_tit = TipoLicencia.objects.filter(regimen="TIT")
        self.assertTrue(qs_tit.filter(codigo="LIC-TIT-ORD").exists())

        qs_ordinaria = TipoLicencia.objects.filter(categoria="Ordinaria")
        self.assertTrue(qs_ordinaria.filter(codigo="LIC-TIT-ORD").exists())

        qs_sin_goce = TipoLicencia.objects.filter(forma_goce="Sin goce")
        self.assertTrue(qs_sin_goce.filter(codigo="LIC-INT-EXT").exists())

        qs_habiles = TipoLicencia.objects.filter(unidad="Hábiles")
        self.assertTrue(qs_habiles.filter(codigo="LIC-TIT-ORD").exists())
