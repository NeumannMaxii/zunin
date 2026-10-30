"""
Pruebas automatizadas para el Ticket 0.2:
- Saneamiento de Modelos, Baja Lógica e Integridad Referencial.
"""

import datetime
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from apps.asistencia.models import RegistroAsistencia
from apps.personal.forms import CargoDocenteForm, DocenteForm
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


class PersonalFormsTests(TestCase):
    """Pruebas unitarias para DocenteForm y CargoDocenteForm."""

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="22333444",
            apellido="BENÍTEZ",
            nombre="Carlos",
            sexo="M",
        )
        self.docente_suplente = Docente.objects.create(
            dni="25666777",
            apellido="FERNÁNDEZ",
            nombre="Mariana",
            sexo="F",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="BD-101",
            nombre="Bases de Datos I",
            carrera="Software",
            anio=1,
        )

    def test_docente_form_valido(self):
        """Valida alta de docente con limpieza de DNI y nombres."""
        form = DocenteForm(
            data={
                "dni": "35.888.999",
                "tipo_documento": "DNI",
                "apellido": "sánchez",
                "nombre": "rodrigo manuel",
                "sexo": "M",
                "nacionalidad": "Argentina",
                "activo": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        docente = form.save()
        self.assertEqual(docente.dni, "35888999")
        self.assertEqual(docente.apellido, "SÁNCHEZ")
        self.assertEqual(docente.nombre, "Rodrigo Manuel")

    def test_docente_form_dni_duplicado_rechazado(self):
        """Rechaza DNI existente en otro registro."""
        form = DocenteForm(
            data={
                "dni": "22333444",
                "apellido": "OTRO",
                "nombre": "Persona",
                "sexo": "F",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)
        self.assertIn("Ya existe un docente", form.errors["dni"][0])

    def test_docente_form_fecha_nacimiento_futura_rechazada(self):
        """Rechaza fechas de nacimiento en el futuro."""
        futuro = datetime.date.today() + datetime.timedelta(days=10)
        form = DocenteForm(
            data={
                "dni": "40111222",
                "apellido": "LÓPEZ",
                "nombre": "Ana",
                "sexo": "F",
                "fecha_nacimiento": futuro.strftime("%Y-%m-%d"),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.errors)

    def test_cargo_docente_form_valido(self):
        """Valida creación exitosa de un cargo titular."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "tipo_cargo": "HORAS_CATEDRA",
                "situacion_revista": "TIT",
                "horas_lunes": 3,
                "horas_martes": 2,
                "activo": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        cargo = form.save()
        self.assertEqual(cargo.total_horas_semanales, 5)

    def test_cargo_docente_form_suplente_sin_reemplazado_rechazado_dp01(self):
        """RF-04: Exige docente reemplazado según formulario DP-01 para suplentes."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente_suplente.pk,
                "materia": self.espacio.pk,
                "tipo_cargo": "HORAS_CATEDRA",
                "situacion_revista": "SUPLENTE",
                "horas_lunes": 4,
                "activo": True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("docente_reemplazado", form.errors)
        self.assertIn("DP-01", form.errors["docente_reemplazado"][0])

    def test_cargo_docente_form_fecha_baja_anterior_a_alta_rechazada(self):
        """Rechaza fecha_baja menor que fecha_alta."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "situacion_revista": "INT",
                "fecha_alta": "2026-06-01",
                "fecha_baja": "2026-05-15",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_baja", form.errors)

    def test_cargo_docente_form_horas_negativas_rechazadas(self):
        """Rechaza horas cátedra menores a cero."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "situacion_revista": "INT",
                "horas_lunes": -2,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("horas_lunes", form.errors)

