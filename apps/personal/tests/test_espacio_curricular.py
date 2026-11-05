"""
Pruebas automatizadas para el modelo EspacioCurricular y sus relaciones.
Valida la normalización relacional de la clave foránea hacia Carrera
y las restricciones de integridad referencial (on_delete=models.PROTECT).
"""

from django.db.models import ProtectedError
from django.test import TestCase

from apps.personal.models import Carrera, EspacioCurricular


class EspacioCurricularRelacionesTests(TestCase):
    """
    Suite de pruebas para validar la clave foránea entre EspacioCurricular y Carrera.
    """

    def setUp(self):
        self.carrera, _ = Carrera.objects.get_or_create(
            codigo="TSDS",
            defaults={
                "nombre": "Tecnicatura Superior en Desarrollo de Software",
                "activo": True,
            },
        )

    def test_criterio_aceptacion_espacio_curricular_resuelve_fk_carrera(self):
        """
        Criterio de Aceptación:
        Las instancias de EspacioCurricular resuelven correctamente su
        relación de clave foránea apuntando a Carrera.
        """
        espacio = EspacioCurricular.objects.create(
            codigo="DS-101",
            nombre="Programación I",
            carrera=self.carrera,
            anio=1,
            comision="UNICA",
            turno="NOCHE",
            regimen="ANUAL",
        )

        espacio.refresh_from_db()

        # 1. Resolver FK directa
        self.assertIsInstance(espacio.carrera, Carrera)
        self.assertEqual(espacio.carrera.pk, self.carrera.pk)
        self.assertEqual(espacio.carrera.codigo, "TSDS")
        self.assertEqual(
            espacio.carrera.nombre,
            "Tecnicatura Superior en Desarrollo de Software",
        )

        # 2. Resolver relación inversa (related_name="espacios_curriculares")
        espacios_de_carrera = self.carrera.espacios_curriculares.all()
        self.assertIn(espacio, espacios_de_carrera)
        self.assertEqual(espacios_de_carrera.count(), 1)

    def test_on_delete_protect_impide_eliminar_carrera_con_espacios_asociados(
        self,
    ):
        """
        Verifica que on_delete=models.PROTECT impida la eliminación física
        de una Carrera si tiene Espacios Curriculares asociados, arrojando
        ProtectedError.
        """
        EspacioCurricular.objects.create(
            codigo="DS-201",
            nombre="Programación II",
            carrera=self.carrera,
            anio=2,
        )

        with self.assertRaises(ProtectedError):
            self.carrera.delete()

    def test_creacion_con_string_resuelve_automaticamente_a_entidad_carrera(
        self,
    ):
        """
        Verifica que al instanciar EspacioCurricular pasando el nombre de
        carrera en texto (por compatibilidad o scripts legacy), se resuelva
        o cree la entidad Carrera correspondiente sin error.
        """
        espacio = EspacioCurricular.objects.create(
            codigo="IA-101",
            nombre="Inteligencia Artificial I",
            carrera="Tecnicatura Superior en Inteligencia Artificial",
            anio=1,
        )

        espacio.refresh_from_db()
        self.assertIsInstance(espacio.carrera, Carrera)
        self.assertEqual(
            espacio.carrera.nombre,
            "Tecnicatura Superior en Inteligencia Artificial",
        )
        self.assertTrue(espacio.carrera.activo)

    def test_representacion_str_espacio_curricular_incluye_nombre_carrera(self):
        """
        Verifica que __str__ en EspacioCurricular utilice correctamente el
        nombre de la carrera asociada.
        """
        espacio = EspacioCurricular.objects.create(
            codigo="DS-301",
            nombre="Práctica Profesionalizante III",
            carrera=self.carrera,
            anio=3,
        )

        expected_str = (
            "DS-301 - Práctica Profesionalizante III "
            "(Tecnicatura Superior en Desarrollo de Software - 3° Año)"
        )
        self.assertEqual(str(espacio), expected_str)


# Alias para retrocompatibilidad
Ticket129NormalizacionRelacionalEspacioCurricularTests = (
    EspacioCurricularRelacionesTests
)
