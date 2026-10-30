"""
Pruebas unitarias para el seeder de base y demo de Octubre 2026 (Ticket 3).
"""

import datetime
from django.core.management import call_command
from django.test import TestCase
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.core.seeder import poblar_datos_demo
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import generar_planilla_mes
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    TipoAutorizacion,
)


class SeederDemoTests(TestCase):
    """Suite de validación para el seeder de catálogos y mes demo de asistencia."""

    def test_seeder_crea_catalogos_base_necesarios(self):
        """
        Verifica que el seeder cree carreras, cargos de catálogo, tipos de
        autorización, tipos de licencia y días no laborables oficiales.
        """
        resumen = poblar_datos_demo()

        self.assertGreater(resumen["carreras"], 0)
        self.assertGreater(resumen["cargos_catalogo"], 0)
        self.assertGreater(resumen["tipos_autorizacion"], 0)
        self.assertGreater(resumen["tipos_licencia"], 0)
        self.assertGreater(resumen["dias_no_laborables"], 0)

        # Verificar existencia específica de catálogos
        self.assertTrue(Carrera.objects.filter(codigo="TSDS").exists())
        self.assertTrue(CargoCatalogo.objects.filter(codigo="PROF-TIT").exists())
        self.assertTrue(TipoAutorizacion.objects.filter(nombre="RESOLUCIÓN").exists())
        self.assertTrue(TipoLicencia.objects.filter(codigo="LIC-340A").exists())
        self.assertTrue(TipoLicencia.objects.filter(codigo="LIC-344").exists())
        self.assertTrue(
            DiaNoLaborable.objects.filter(
                fecha=datetime.date(2026, 10, 12)
            ).exists()
        )

    def test_seeder_puebla_mes_completo_octubre_2026_con_marcas_requeridas(self):
        """
        Verifica que se generen registros diarios de asistencia para todo
        Octubre 2026 conteniendo marcas 'P', 'I' y 'LIC'.
        """
        poblar_datos_demo()

        asistencias_octubre = RegistroAsistencia.objects.filter(
            fecha__year=2026, fecha__month=10
        )
        self.assertGreater(asistencias_octubre.count(), 0)

        # Debe contener marcas diarias de Presente ('P'),
        # Inasistencia ('I') y Licencia ('LIC')
        marcas_existentes = set(
            asistencias_octubre.values_list("marca_diaria", flat=True)
        )
        self.assertIn("P", marcas_existentes)
        self.assertIn("I", marcas_existentes)
        self.assertIn("LIC", marcas_existentes)

        # Debe haber registros para los 5 docentes de prueba
        docentes_con_asistencia = set(
            asistencias_octubre.values_list("docente__dni", flat=True)
        )
        self.assertEqual(len(docentes_con_asistencia), 5)

        # Validar que registros con estado 'LICENCIA' tengan su TipoLicencia
        licencias = asistencias_octubre.filter(estado="LICENCIA")
        self.assertTrue(licencias.exists())
        for lic in licencias:
            self.assertIsNotNone(lic.tipo_licencia)

        # Validar que los feriados no tengan asistencias registradas
        self.assertFalse(
            asistencias_octubre.filter(
                fecha=datetime.date(2026, 10, 12)
            ).exists()
        )

    def test_seeder_idempotencia_dos_ejecuciones_no_duplican(self):
        """
        Verifica que ejecutar el seeder dos veces seguidas no duplique
        catálogos, docentes, cargos ni asistencias diarias.
        """
        # Primera ejecución
        poblar_datos_demo()
        c_carreras_1 = Carrera.objects.count()
        c_docentes_1 = Docente.objects.count()
        c_cargos_1 = CargoDocente.objects.count()
        c_espacios_1 = EspacioCurricular.objects.count()
        c_licencias_1 = TipoLicencia.objects.count()
        c_asistencias_1 = RegistroAsistencia.objects.filter(
            fecha__year=2026, fecha__month=10
        ).count()

        # Segunda ejecución
        resumen_2 = poblar_datos_demo()
        c_carreras_2 = Carrera.objects.count()
        c_docentes_2 = Docente.objects.count()
        c_cargos_2 = CargoDocente.objects.count()
        c_espacios_2 = EspacioCurricular.objects.count()
        c_licencias_2 = TipoLicencia.objects.count()
        c_asistencias_2 = RegistroAsistencia.objects.filter(
            fecha__year=2026, fecha__month=10
        ).count()

        self.assertEqual(c_carreras_1, c_carreras_2)
        self.assertEqual(c_docentes_1, c_docentes_2)
        self.assertEqual(c_cargos_1, c_cargos_2)
        self.assertEqual(c_espacios_1, c_espacios_2)
        self.assertEqual(c_licencias_1, c_licencias_2)
        self.assertEqual(c_asistencias_1, c_asistencias_2)
        self.assertEqual(resumen_2["asistencias_creadas"], 0)

    def test_seeder_permite_procesar_motor_mensual_octubre_2026(self):
        """
        Verifica que el mes de prueba generado sea consumible por el motor
        mensual ('generar_planilla_mes') generando renglones consolidados reales.
        """
        poblar_datos_demo()

        # Ejecución del motor mensual para Octubre 2026
        renglones = generar_planilla_mes(mes=10, anio=2026)

        self.assertGreater(len(renglones), 0)
        self.assertEqual(
            RenglonPlanillaMensual.objects.filter(
                mes=10, anio=2026
            ).count(),
            len(renglones),
        )

        # Verificar que se desglosen renglones con cuadros IL-01 e IL-02
        cuadros = set(r.cuadro for r in renglones)
        self.assertIn("IL-01", cuadros)
        self.assertIn("IL-02", cuadros)

        # Verificar que los instrumentos correlativos tengan formato 'XXX/2026'
        for r in renglones:
            self.assertTrue(r.numero_instrumento.endswith("/2026"))

    def test_comando_management_poblar_datos_call_command(self):
        """
        Valida la ejecución del comando management 'poblar_datos' con sus opciones.
        """
        call_command("poblar_datos", reset=True, generar_planilla=True)

        self.assertTrue(
            RegistroAsistencia.objects.filter(
                fecha__year=2026, fecha__month=10
            ).exists()
        )
        self.assertTrue(
            RenglonPlanillaMensual.objects.filter(
                mes=10, anio=2026
            ).exists()
        )
