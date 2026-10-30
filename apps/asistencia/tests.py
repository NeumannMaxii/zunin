"""
Pruebas automatizadas para los formularios del módulo de Asistencia (apps.asistencia.forms).
"""

import datetime
from django.test import TestCase
from apps.asistencia.forms import DiaNoLaborableForm, RegistroAsistenciaForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.licencias.models import TipoLicencia
from apps.personal.models import Docente


class AsistenciaFormsTests(TestCase):
    def setUp(self):
        self.docente = Docente.objects.create(
            dni="20123456",
            apellido="Álvarez",
            nombre="Laura",
            sexo="F",
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            cuadro_mensual="IL-01",
        )
        self.tipo_inasistencia = TipoLicencia.objects.create(
            codigo="INA-INJ",
            articulo="348",
            descripcion="Inasistencia Injustificada",
            categoria="INASISTENCIA",
            cuadro_mensual="IL-02",
        )

    # --- Pruebas DiaNoLaborableForm ---

    def test_dia_no_laborable_form_valido(self):
        """Valida alta exitosa de un día no laborable."""
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "FERIADO",
                "descripcion": "Día de la Revolución de Mayo",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.descripcion, "Día de la Revolución de Mayo")

    def test_dia_no_laborable_form_descripcion_vacia_rechazada(self):
        """Rechaza descripción en blanco o con espacios únicamente."""
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "FERIADO",
                "descripcion": "   ",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("descripcion", form.errors)

    def test_dia_no_laborable_form_fecha_duplicada_rechazada(self):
        """Rechaza fechas de días no laborables repetidas."""
        DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 5, 25),
            tipo="FERIADO",
            descripcion="Feriado Preexistente",
        )
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "ASUETO",
                "descripcion": "Asueto Duplicado",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha", form.errors)
        self.assertIn("Ya existe un día no laborable", form.errors["fecha"][0])

    # --- Pruebas RegistroAsistenciaForm ---

    def test_registro_asistencia_form_presente_valido(self):
        """Valida registro normal en estado PRESENTE."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "PRESENTE",
                "marca_diaria": "PR",
                "oficina": "1452",
                "anio_planilla": 2026,
                "justifica": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        registro = form.save()
        self.assertEqual(registro.estado, "PRESENTE")

    def test_registro_asistencia_form_licencia_sin_tipo_rechazado(self):
        """Rechaza estado LICENCIA si no se indica el Tipo de Licencia."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("Debe especificar el Tipo de Licencia", form.errors["tipo_licencia"][0])

    def test_registro_asistencia_form_presente_con_tipo_licencia_rechazado(self):
        """Rechaza estado PRESENTE si se le adjudica un Tipo de Licencia."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "PRESENTE",
                "marca_diaria": "PR",
                "tipo_licencia": self.tipo_lic.pk,
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("No debe asignar un Tipo de Licencia", form.errors["tipo_licencia"][0])

    def test_registro_asistencia_form_inasistencia_multidia_rechazada_rn06(self):
        """RN-06: Las inasistencias solamente pueden ser por un día."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "fecha_hasta": "2026-04-12",
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_hasta", form.errors)
        self.assertIn("RN-06", form.errors["fecha_hasta"][0])

    def test_registro_asistencia_form_fecha_hasta_anterior_a_fecha(self):
        """Rechaza fecha_hasta anterior a la fecha de inicio."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "fecha_hasta": "2026-04-05",
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "tipo_licencia": self.tipo_lic.pk,
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_hasta", form.errors)

    def test_registro_asistencia_form_docente_fecha_duplicado(self):
        """Rechaza duplicar la asistencia del mismo docente en la misma fecha."""
        RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 10),
            estado="PRESENTE",
        )
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha", form.errors)
        self.assertIn("Ya existe un registro", form.errors["fecha"][0])
