"""
Pruebas automatizadas para el Ticket 12.7:
UniqueConstraint de Idempotencia en BD para RenglonPlanillaMensual.

Especificación Técnica:
- Restricción de unicidad UniqueConstraint en RenglonPlanillaMensual.Meta
  para los campos: docente, cargo, mes, anio, desde y hasta.
- Migración aplicada a nivel de base de datos.

Criterios de Aceptación:
- Intentar registrar un renglón duplicado directamente por código lanza
  IntegrityError.
"""

import datetime
from django.db import IntegrityError
from django.test import TestCase

from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import (
    CargoDocente,
    Docente,
    EspacioCurricular,
)


class Ticket127UniqueConstraintIdempotenciaTests(TestCase):
    """
    Suite de pruebas para verificar la restricción de unicidad e idempotencia
    en RenglonPlanillaMensual (Ticket 12.7).
    """

    def setUp(self):
        # Crear docente
        self.docente = Docente.objects.create(
            dni="20111222",
            apellido="GOMEZ",
            nombre="Laura",
            sexo="F",
            activo=True,
        )

        # Crear materia y cargos
        self.materia_1 = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática I",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.materia_2 = EspacioCurricular.objects.create(
            codigo="FIS-101",
            nombre="Física I",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.cargo_1 = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia_1,
            horas_lunes=4,
            situacion_revista="TIT",
            activo=True,
        )
        self.cargo_2 = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia_2,
            horas_martes=3,
            situacion_revista="SUT",
            activo=True,
        )

        # Tipo de Licencia
        self.tipo_licencia = TipoLicencia.objects.create(
            codigo="LIC-TEST",
            articulo="Art. 340",
            descripcion="Licencia Médica",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
        )

        self.mes = 5
        self.anio = 2026
        self.desde = datetime.date(2026, 5, 4)
        self.hasta = datetime.date(2026, 5, 8)

    def test_criterio_aceptacion_registrar_renglon_duplicado_lanza_integrity_error(
        self,
    ):
        """
        Criterio de Aceptación:
        Intentar registrar un renglón duplicado directamente por código
        lanza IntegrityError.
        Campos evaluados: docente, cargo, mes, anio, desde, hasta.
        """
        # Creación del primer renglón
        renglon_original = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_1,
            tipo_licencia=self.tipo_licencia,
            cuadro="IL-01",
            mes=self.mes,
            anio=self.anio,
            desde=self.desde,
            hasta=self.hasta,
            horas_afectadas=4,
            numero_instrumento="DISP-2026-001",
        )
        self.assertIsNotNone(renglon_original.pk)

        # Intentar crear un segundo renglón con los mismos campos de la restricción
        with self.assertRaises(IntegrityError):
            RenglonPlanillaMensual.objects.create(
                docente=self.docente,
                cargo=self.cargo_1,
                tipo_licencia=self.tipo_licencia,
                cuadro="IL-01",
                mes=self.mes,
                anio=self.anio,
                desde=self.desde,
                hasta=self.hasta,
                horas_afectadas=4,
                numero_instrumento="DISP-2026-002",
            )

    def test_renglones_con_diferentes_fechas_o_cargos_son_permitidos(self):
        """
        Verifica que la restricción permita renglones del mismo docente si
        difieren en cargo o rango de fechas (desde/hasta).
        """
        # Primer renglón para cargo_1
        r1 = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_1,
            mes=self.mes,
            anio=self.anio,
            desde=self.desde,
            hasta=self.hasta,
            horas_afectadas=4,
        )
        self.assertIsNotNone(r1.pk)

        # Segundo renglón para cargo_2 (mismo período, distinto cargo) -> Permitido
        r2 = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_2,
            mes=self.mes,
            anio=self.anio,
            desde=self.desde,
            hasta=self.hasta,
            horas_afectadas=3,
        )
        self.assertIsNotNone(r2.pk)

        # Tercer renglón para cargo_1 en fecha distinta -> Permitido
        r3 = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_1,
            mes=self.mes,
            anio=self.anio,
            desde=datetime.date(2026, 5, 18),
            hasta=datetime.date(2026, 5, 22),
            horas_afectadas=4,
        )
        self.assertIsNotNone(r3.pk)

        self.assertEqual(RenglonPlanillaMensual.objects.count(), 3)
