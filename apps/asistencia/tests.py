"""
Pruebas automatizadas para apps.asistencia:
- Formularios del módulo de Asistencia (Ticket 3).
- Transaccionalidad Atómica en Carga Masiva (Ticket 5) y Justificaciones (Ticket 7).
- Criterio: Fallo en registro 3 de 5 revierte todo (0 asistencias guardadas).
- Notificación al usuario mediante django.contrib.messages.error().
- Paginación obligatoria en RegistroAsistenciaListView (paginate_by = 25).
"""

import datetime
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from apps.asistencia.forms import DiaNoLaborableForm, RegistroAsistenciaForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import (
    guardar_asistencia_diaria_masiva,
    justificar_lote_asistencias,
)
from apps.asistencia.views import RegistroAsistenciaListView
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
        self.assertIn(
            "Debe especificar el Tipo de Licencia", form.errors["tipo_licencia"][0]
        )

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
        self.assertIn(
            "No debe asignar un Tipo de Licencia", form.errors["tipo_licencia"][0]
        )

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


class AtomicidadAsistenciaTests(TestCase):
    """
    Criterio de Aceptación Ticket 3.8:
    Test Atomicidad: Simular un fallo en el registro 3 de un lote de 5 asistencias
    y verificar mediante assert que el sistema revirtió la operación completa
    (0 asistencias guardadas).
    """

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="28444555",
            apellido="Valenzuela",
            nombre="Roberto",
            sexo="M",
        )
        self.factory = RequestFactory()

    def test_atomicidad_fallo_registro_3_revierte_operacion_completa(self):
        """
        Simula un lote de 5 asistencias donde el registro 3 contiene un dato
        inválido que genera ValidationError. Se verifica con assert que el rollback
        fue total y quedaron 0 asistencias guardadas en la base de datos.
        """
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

        # Lote de 5 registros (registro 1 y 2 válidos, 3 inválido, 4 y 5 válidos)
        lote_5 = [
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 1),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 2),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 3),
                estado="ESTADO_INVALIDO",  # Registro 3 fallará en full_clean()
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 4),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 5),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
        ]

        with self.assertRaises(ValidationError):
            guardar_asistencia_diaria_masiva(lote_5)

        # Aserción obligatoria del criterio de aceptación: 0 asistencias guardadas
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

    def test_atomicidad_notifica_error_con_messages_al_usuario(self):
        """
        Verifica que ante un fallo en el lote, si se provee el objeto request,
        se agregue un mensaje con nivel ERROR mediante django.contrib.messages.error().
        """
        request = self.factory.post("/asistencia/carga-masiva/")
        setattr(request, "session", "session")
        messages_storage = FallbackStorage(request)
        setattr(request, "_messages", messages_storage)

        lote_invalido = [
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 10),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 11),
                "estado": "ESTADO_NO_EXISTENTE",  # Inválido
                "marca_diaria": "PR",
            },
        ]

        with self.assertRaises(ValidationError):
            guardar_asistencia_diaria_masiva(lote_invalido, request=request)

        # 0 registros persistidos
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

        # Verificación del mensaje registrado
        lista_mensajes = list(get_messages(request))
        self.assertTrue(len(lista_mensajes) > 0)
        self.assertEqual(lista_mensajes[0].level_tag, "error")
        self.assertIn("Error al procesar la carga masiva", str(lista_mensajes[0]))

    def test_atomicidad_lote_valido_guarda_todos_los_registros(self):
        """
        Verifica que cuando todas las filas son válidas, se guarden íntegramente
        todos los registros del lote.
        """
        lote_valido = [
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 20),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 21),
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "justifica": False,
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 22),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
        ]

        guardados = guardar_asistencia_diaria_masiva(lote_valido)
        self.assertEqual(len(guardados), 3)
        self.assertEqual(RegistroAsistencia.objects.count(), 3)

    def test_atomicidad_justificaciones_por_lote_revierte_ante_fallo(self):
        """
        Verifica que si en un lote de justificaciones falla un registro
        (ej: intentar justificar un registro ya presente), se revierta todo el lote.
        """
        licencia = TipoLicencia.objects.create(
            codigo="LIC_MED_AT",
            descripcion="Licencia Médica",
            categoria="LICENCIA",
        )
        asist1 = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 1),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        asist2 = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 2),
            estado="PRESENTE",  # No se puede justificar un 'PRESENTE'
            marca_diaria="PR",
            justifica=True,
        )

        lote = [
            {"asistencia": asist1, "nueva_marca": "LIC", "tipo_licencia": licencia},
            {"asistencia": asist2, "nueva_marca": "LIC", "tipo_licencia": licencia},
        ]

        with self.assertRaises(ValidationError):
            justificar_lote_asistencias(lote)

        # asist1 debe haber mantenido su estado previo sin modificar (rollback)
        asist1.refresh_from_db()
        self.assertEqual(asist1.estado, "AUSENTE")
        self.assertEqual(asist1.marca_diaria, "I")
        self.assertFalse(asist1.justifica)

    def test_asistencia_listview_paginate_by_25(self):
        """Verifica que RegistroAsistenciaListView tenga paginate_by = 25."""
        self.assertEqual(RegistroAsistenciaListView.paginate_by, 25)
