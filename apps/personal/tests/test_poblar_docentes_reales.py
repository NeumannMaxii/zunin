"""
Tests unitarios para el comando 'poblar_docentes_reales', la nómina oficial
del IESETyFP (padrón de docentes interinos) y la grilla horaria de 3° año TSDS.
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from apps.personal.models import CargoDocente, Docente


class PoblarDocentesRealesCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        call_command("poblar_oferta_academica")

    def test_poblar_docentes_reales_ejecuta_y_es_idempotente(self):
        """
        Verifica que el comando carga los 37 docentes interinos del padrón,
        los 5 docentes de 3° año TSDS, configura las 29 hs cátedra semanales
        con sus suplencias DP-01, y es completamente idempotente.
        """
        out = StringIO()
        call_command("poblar_docentes_reales", stdout=out)
        output = out.getvalue()

        self.assertIn("Proceso finalizado con éxito", output)
        self.assertEqual(Docente.objects.count(), 42)  # 37 padrón + 5 nuevos
        self.assertEqual(CargoDocente.objects.count(), 42)

        # Verificar docentes clave del padrón
        baez = Docente.objects.get(dni="20091846")
        self.assertEqual(baez.apellido, "Baez")
        self.assertEqual(baez.nombre, "Norma Beatriz")
        self.assertEqual(baez.sexo, "F")

        # Verificar materias y suplencias de 3° año TSDS
        # 1. Práctica Profesionalizante III: Montiel suplente de Escalante (6 hs)
        cargo_pp3 = CargoDocente.objects.get(codigo_cargo="CARGO-31234567-DS301-SUP")
        self.assertEqual(cargo_pp3.docente.apellido, "Montiel")
        self.assertEqual(cargo_pp3.materia.codigo, "DS-301")
        self.assertEqual(cargo_pp3.situacion_revista, "SUP")
        self.assertEqual(cargo_pp3.docente_reemplazado.apellido, "Escalante")
        self.assertEqual(cargo_pp3.total_horas_semanales, 6)

        # 2. Dirección y Gestión: Miranda Romina suplente de Miranda Christian (3 hs)
        cargo_dg = CargoDocente.objects.get(codigo_cargo="CARGO-29934139-DS304-SUP")
        self.assertEqual(cargo_dg.docente.apellido, "Miranda")
        self.assertEqual(cargo_dg.docente.nombre, "Romina Noelia")
        self.assertEqual(cargo_dg.situacion_revista, "SUP")
        self.assertEqual(cargo_dg.docente_reemplazado.apellido, "Miranda")
        self.assertEqual(cargo_dg.docente_reemplazado.nombre, "Christian")
        self.assertEqual(cargo_dg.total_horas_semanales, 3)

        # 3. El Emprendedor Digital: Mujica Cynthia (3 hs)
        cargo_ed = CargoDocente.objects.get(codigo_cargo="CARGO-25699824-DS308")
        self.assertEqual(cargo_ed.docente.apellido, "Mujica")
        self.assertEqual(cargo_ed.total_horas_semanales, 3)

        # 4. Fundamentos de Ing. de Software II: Villafañe Victor (3 hs)
        cargo_fis2 = CargoDocente.objects.get(codigo_cargo="CARGO-23269473-DS306")
        self.assertEqual(cargo_fis2.docente.apellido, "Villafañe")
        self.assertEqual(cargo_fis2.total_horas_semanales, 3)

        # Verificar idempotencia en segunda ejecución
        out2 = StringIO()
        call_command("poblar_docentes_reales", stdout=out2)
        output2 = out2.getvalue()

        self.assertIn("Docentes creados/actualizados: 42", output2)
        self.assertEqual(Docente.objects.count(), 42)
        self.assertEqual(CargoDocente.objects.count(), 42)
