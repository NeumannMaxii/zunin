"""
Tests unitarios para el comando 'poblar_oferta_academica' y el catálogo oficial
de carreras, planes de estudio y espacios curriculares del IESETyFP.
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from apps.personal.models import Carrera, PlanEstudio, EspacioCurricular


class PoblarOfertaAcademicaCommandTests(TestCase):
    def test_poblar_oferta_academica_ejecuta_y_es_idempotente(self):
        """Verifica que el comando puebla carreras oficiales y es idempotente."""
        out = StringIO()
        call_command("poblar_oferta_academica", stdout=out)
        output = out.getvalue()

        self.assertIn("Oferta Académica cargada exitosamente", output)

        # Verificar carreras oficiales creadas
        codigos_esperados = [
            "TSDS",
            "TSIA",
            "TSSI",
            "TSSHyMAT",
            "TSGA",
            "PROF-TEC",
            "PROF-FIS",
            "PROF-TP",
            "PROF-INF",
        ]
        for codigo in codigos_esperados:
            self.assertTrue(
                Carrera.objects.filter(codigo=codigo).exists(),
                f"Falta la carrera oficial con código {codigo}",
            )
            carrera = Carrera.objects.get(codigo=codigo)
            if codigo == "PROF-INF":
                self.assertFalse(carrera.activo)
            else:
                self.assertTrue(carrera.activo)
                self.assertTrue(
                    carrera.planes_estudio.filter(activo=True).exists(),
                    f"La carrera {codigo} no tiene un plan activo asignado",
                )

        total_carreras = Carrera.objects.count()
        total_planes = PlanEstudio.objects.count()
        total_materias = EspacioCurricular.objects.count()

        self.assertGreaterEqual(total_carreras, 9)
        self.assertGreaterEqual(total_planes, 9)
        self.assertGreater(total_materias, 200)

        # Verificar integridad de espacios curriculares
        for espacio in EspacioCurricular.objects.all():
            self.assertIsNotNone(espacio.carrera)
            self.assertIsNotNone(espacio.plan_estudio_ref)
            self.assertIn(espacio.anio, [1, 2, 3, 4, 5])
            self.assertIn(espacio.regimen, ["ANUAL", "CUAT_1", "CUAT_2"])
            self.assertIn(espacio.turno, ["MANANA", "TARDE", "NOCHE"])

        # Verificar idempotencia: segunda ejecución sin duplicados
        out_segunda = StringIO()
        call_command("poblar_oferta_academica", stdout=out_segunda)
        out_segunda_val = out_segunda.getvalue()

        self.assertIn("0 creadas", out_segunda_val)
        self.assertEqual(Carrera.objects.count(), total_carreras)
        self.assertEqual(PlanEstudio.objects.count(), total_planes)
        self.assertEqual(EspacioCurricular.objects.count(), total_materias)
