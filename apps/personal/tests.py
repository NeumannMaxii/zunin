"""
Pruebas automatizadas para el Ticket 0.2:
- Saneamiento de Modelos, Baja Lógica e Integridad Referencial.
"""

import datetime
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from apps.asistencia.models import RegistroAsistencia
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class SaneamientoModelosIntegridadTests(TestCase):
    """
    Validaciones de candados de borrado físico, vigencia por fecha de baja
    y normalización de situación de revista (Ticket 0.2).
    """

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="30111222",
            apellido="Gómez",
            nombre="Martín",
            sexo="M",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PR-301",
            nombre="Programación Avanzada",
            carrera="Tecnicatura Superior en Desarrollo de Software",
            anio=3,
        )

    def test_eliminar_docente_con_asistencia_levanta_protected_error(self):
        """
        1. Verificar que intentar eliminar físicamente un Docente con registros
        de asistencia asociados levante django.db.models.ProtectedError.
        """
        RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 20),
            estado="PRESENTE",
        )
        with self.assertRaises(ProtectedError):
            self.docente.delete()

    def test_es_designacion_vigente_falso_si_fecha_baja_pasada(self):
        """
        2. Verificar que es_designacion_vigente devuelva False si fecha_baja ya
        pasó, aunque hasta_texto contenga 'SIN TERMINO'.
        """
        hoy = timezone.now().date()
        fecha_baja_pasada = hoy - datetime.timedelta(days=5)

        cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
            activo=True,
            hasta_texto="SIN TERMINO",
            fecha_baja=fecha_baja_pasada,
        )

        self.assertFalse(cargo.es_designacion_vigente(fecha_referencia=hoy))

    def test_guardar_cargo_titular_normaliza_a_tit(self):
        """
        3. Verificar que al guardar un cargo con situacion_revista='TITULAR',
        quede guardado y persistido normalizado como 'TIT'.
        """
        cargo = CargoDocente(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TITULAR",
            horas_lunes=4,
        )
        cargo.save()
        cargo.refresh_from_db()

        self.assertEqual(cargo.situacion_revista, "TIT")
