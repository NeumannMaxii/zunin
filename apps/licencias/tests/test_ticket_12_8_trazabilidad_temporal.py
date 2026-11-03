"""
Pruebas para el Ticket 12.8: Trazabilidad Temporal en Modelos.

Valida:
1. Criterio de Aceptación: Al instanciar y guardar un CargoDocente o TipoLicencia,
   el atributo creado_en se puebla automáticamente con la marca de tiempo actual.
2. Al actualizar una instancia existente, actualizado_en se modifica
   mientras creado_en se preserva inmutable.
3. Compatibilidad de propiedades accesorias creado_el y modificado_el.
"""

import datetime
import time
from django.test import TestCase
from django.utils import timezone
from apps.licencias.models import TipoLicencia
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class TrazabilidadTemporalModelosTests(TestCase):
    """Pruebas de campos de auditoría temporal creado_en y actualizado_en."""

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="25999888",
            apellido="Romero",
            nombre="Esteban",
            sexo="M",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PROG-1",
            nombre="Programación I",
            carrera="Desarrollo de Software",
            anio=1,
        )

    def test_criterio_cargo_docente_creado_en_se_puebla_automaticamente(self):
        """
        Criterio de Aceptación:
        Al instanciar y guardar un cargo, el campo creado_en
        se puebla automáticamente.
        """
        antes = timezone.now()
        cargo = CargoDocente(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
            activo=True,
        )
        self.assertIsNone(cargo.creado_en)
        self.assertIsNone(cargo.actualizado_en)

        cargo.save()
        despues = timezone.now()

        # Validar que creado_en se pobló automáticamente
        self.assertIsNotNone(cargo.creado_en)
        self.assertIsInstance(cargo.creado_en, datetime.datetime)
        self.assertGreaterEqual(cargo.creado_en, antes)
        self.assertLessEqual(cargo.creado_en, despues)

        # Validar que actualizado_en también se pobló
        self.assertIsNotNone(cargo.actualizado_en)
        self.assertIsInstance(cargo.actualizado_en, datetime.datetime)
        self.assertGreaterEqual(cargo.actualizado_en, antes)
        self.assertLessEqual(cargo.actualizado_en, despues)

    def test_criterio_tipo_licencia_creado_en_se_puebla_automaticamente(self):
        """
        Criterio de Aceptación:
        Al instanciar y guardar una licencia, el campo creado_en
        se puebla automáticamente.
        """
        antes = timezone.now()
        lic = TipoLicencia(
            codigo="LIC-TEST-128",
            descripcion="Licencia Extraordinaria de Capacitación",
            categoria="LICENCIA",
            cuadro_mensual="IL-02",
        )
        self.assertIsNone(lic.creado_en)
        self.assertIsNone(lic.actualizado_en)

        lic.save()
        despues = timezone.now()

        # Validar que creado_en se pobló automáticamente
        self.assertIsNotNone(lic.creado_en)
        self.assertIsInstance(lic.creado_en, datetime.datetime)
        self.assertGreaterEqual(lic.creado_en, antes)
        self.assertLessEqual(lic.creado_en, despues)

        # Validar que actualizado_en también se pobló
        self.assertIsNotNone(lic.actualizado_en)
        self.assertIsInstance(lic.actualizado_en, datetime.datetime)
        self.assertGreaterEqual(lic.actualizado_en, antes)
        self.assertLessEqual(lic.actualizado_en, despues)

    def test_actualizacion_modifica_actualizado_en_y_preserva_creado_en(self):
        """
        Valida que al modificar un registro ya persistido, actualizado_en
        cambia de valor mientras creado_en permanece inalterado.
        """
        cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
        )
        creado_original = cargo.creado_en
        actualizado_original = cargo.actualizado_en

        time.sleep(0.01)
        cargo.situacion_revista = "INT"
        cargo.save()
        cargo.refresh_from_db()

        self.assertEqual(cargo.creado_en, creado_original)
        self.assertGreater(cargo.actualizado_en, actualizado_original)

    def test_propiedades_compatibilidad_creado_el_y_modificado_el(self):
        """
        Valida que las properties creado_el y modificado_el apunten a los campos
        creado_en y actualizado_en respectivamente.
        """
        cargo = CargoDocente.objects.create(
            docente=self.docente,
            situacion_revista="TIT",
        )
        self.assertEqual(cargo.creado_el, cargo.creado_en)
        self.assertEqual(cargo.modificado_el, cargo.actualizado_en)

        lic = TipoLicencia.objects.create(
            codigo="LIC-PROP-128",
            descripcion="Licencia para test de properties",
        )
        self.assertEqual(lic.creado_el, lic.creado_en)
        self.assertEqual(lic.modificado_el, lic.actualizado_en)
