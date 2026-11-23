"""
Tests unitarios para el comando 'poblar_docentes_reales' y la nómina oficial
del IESETyFP (padrón de docentes interinos).
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from apps.personal.models import CargoDocente, Docente


class PoblarDocentesRealesCommandTests(TestCase):
    def test_poblar_docentes_reales_ejecuta_y_es_idempotente(self):
        """
        Verifica que el comando carga los 37 docentes interinos reales del padrón,
        crea sus cargos correspondientes y es completamente idempotente.
        """
        out = StringIO()
        call_command("poblar_docentes_reales", stdout=out)
        output = out.getvalue()

        self.assertIn("Proceso finalizado con éxito", output)
        self.assertEqual(Docente.objects.count(), 37)
        self.assertEqual(CargoDocente.objects.count(), 37)

        # Verificar docentes clave del padrón
        baez = Docente.objects.get(dni="20091846")
        self.assertEqual(baez.apellido, "Baez")
        self.assertEqual(baez.nombre, "Norma Beatriz")
        self.assertEqual(baez.sexo, "F")

        villalba = Docente.objects.get(dni="25973399")
        self.assertEqual(villalba.apellido, "Villalba")
        self.assertEqual(villalba.nombre, "Silvana Valeria")

        benitez = Docente.objects.get(dni="20270281")
        self.assertEqual(benitez.apellido, "Benitez")
        self.assertEqual(benitez.nombre, "Ramon Ventura")

        # Verificar idempotencia en segunda ejecución
        out2 = StringIO()
        call_command("poblar_docentes_reales", stdout=out2)
        output2 = out2.getvalue()

        self.assertIn("Docentes creados: 0", output2)
        self.assertEqual(Docente.objects.count(), 37)
        self.assertEqual(CargoDocente.objects.count(), 37)
