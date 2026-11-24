"""
Pruebas automatizadas para el Ticket 20:
Disposición Interna 100% Autoincremental y No Editable.
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.asistencia.models import RegistroAsistencia
from apps.licencias.forms import JustificacionDiferidaForm
from apps.licencias.models import (
    LicenciaOtorgada,
    NumeradorDisposicion,
    RenglonPlanillaMensual,
    TipoLicencia,
)
from apps.personal.models import CargoCatalogo, CargoDocente, Docente

User = get_user_model()


class Ticket20DisposicionNoEditableTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operador_bedelia",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

        self.docente = Docente.objects.create(
            nombre="Roberto",
            apellido="Gómez",
            dni="25111222",
            activo=True,
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="PROF-T20",
            descripcion="Profesor Titular",
            activo=True,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2022, 3, 1),
            horas_lunes=4,
            horas_martes=4,
            activo=True,
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="340-A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            cuadro_mensual="IL-01",
            duracion_maxima=30,
            activo=True,
        )
        self.fecha_prueba = datetime.date(2026, 6, 8)  # Lunes

    def test_justificacion_diferida_form_campo_readonly(self):
        """
        El campo numero_disposicion debe tener atributo readonly y clase deshabilitada.
        """
        form = JustificacionDiferidaForm()
        widget = form.fields["numero_disposicion"].widget
        self.assertIn("readonly", widget.attrs)
        self.assertEqual(widget.attrs["readonly"], "readonly")
        self.assertIn("cursor-not-allowed", widget.attrs["class"])

    def test_justificacion_diferida_asigna_correlativo_automatico_en_save(self):
        """
        Al guardar una JustificacionDiferida con tipo_instrumento='DISPOSICION',
        el sistema genera y reserva automáticamente el siguiente correlativo oficial.
        """
        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=self.fecha_prueba,
            estado="AUSENTE",
            marca_diaria="I",
        )

        form_data = {
            "registro": reg.pk,
            "nueva_marca": "LIC",
            "tipo_licencia": self.tipo_lic.pk,
            "tipo_instrumento": "DISPOSICION",
            "numero_disposicion": "",  # Enviado vacío o ignorado
        }
        form = JustificacionDiferidaForm(data=form_data, registro=reg)
        self.assertTrue(form.is_valid(), form.errors)
        saved_reg = form.save(usuario=self.user)

        self.assertIsNotNone(saved_reg.numero_disposicion)
        self.assertTrue(saved_reg.numero_disposicion.endswith("/2026"))
        self.assertRegex(saved_reg.numero_disposicion, r"^\d{3}/2026$")

        # Verifica que el numerador institucional se haya incrementado
        num_obj = NumeradorDisposicion.objects.get(anio=2026)
        num_entero = int(saved_reg.numero_disposicion.split("/")[0])
        self.assertEqual(num_obj.ultimo_numero, num_entero)

    def test_licencia_otorgada_create_view_fuerza_asignacion_automatica(self):
        """
        Al crear una LicenciaOtorgada por vista con tipo_instrumento='DISPOSICION',
        el backend siempre asigna el siguiente correlativo oficial aunque el usuario
        intente enviar un valor modificado.
        """
        # Fijar numerador previo en 5
        NumeradorDisposicion.objects.update_or_create(
            anio=2026, defaults={"ultimo_numero": 5}
        )

        post_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo.pk,
            "tipo_licencia": self.tipo_lic.pk,
            "fecha_desde": "2026-06-15",
            "fecha_hasta_prevista": "2026-06-16",
            "estado": "SOLICITADA",
            "porcentaje_goce": "100",
            "tipo_instrumento": "DISPOSICION",
            "instrumento_legal": "999/2026",  # Intento de alterar el número
        }
        url = reverse("licencias:licenciaotorgada_create")
        resp = self.client.post(url, data=post_data)
        self.assertEqual(resp.status_code, 302)

        licencia = LicenciaOtorgada.objects.filter(docente=self.docente).latest("pk")
        # No debe ser 999, debe ser el correlativo oficial automático 006/2026
        self.assertEqual(licencia.instrumento_legal, "006/2026")
        num_obj = NumeradorDisposicion.objects.get(anio=2026)
        self.assertEqual(num_obj.ultimo_numero, 6)

    def test_conmutar_instrumento_a_disposicion_autoasigna(self):
        """
        Al conmutar un RenglonPlanillaMensual hacia Disposición Interna, si venía
        de Resolución externa, el sistema auto-asigna de forma atómica la
        siguiente Disposición.
        """
        renglon = RenglonPlanillaMensual.objects.create(
            anio=2026,
            mes=6,
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            cuadro="IL-01",
            desde=datetime.date(2026, 6, 1),
            hasta=datetime.date(2026, 6, 2),
            tipo_instrumento="RESOLUCION",
            numero_instrumento="Res. 500/2026 M.E.C.C.y T.",
        )

        url = reverse("licencias:renglon_actualizar_instrumento", args=[renglon.pk])
        post_data = {
            "tipo_instrumento": "DISPOSICION",
            "numero_instrumento": "",  # No editable por el usuario
        }
        resp = self.client.post(url, data=post_data)
        self.assertEqual(resp.status_code, 302)

        renglon.refresh_from_db()
        self.assertEqual(renglon.tipo_instrumento, "DISPOSICION")
        self.assertTrue(renglon.numero_instrumento.endswith("/2026"))
        self.assertNotEqual(renglon.numero_instrumento, "Res. 500/2026 M.E.C.C.y T.")
        self.assertRegex(renglon.numero_instrumento, r"^\d{3}/2026$")

    def test_conmutar_instrumento_preserva_disposicion_existente(self):
        """
        Al conmutar un renglón que ya tiene una Disposición asignada del año en curso,
        no quema un nuevo número sino que preserva el ya emitido.
        """
        renglon = RenglonPlanillaMensual.objects.create(
            anio=2026,
            mes=6,
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            cuadro="IL-01",
            desde=datetime.date(2026, 6, 1),
            hasta=datetime.date(2026, 6, 2),
            tipo_instrumento="DISPOSICION",
            numero_instrumento="012/2026",
        )

        url = reverse("licencias:renglon_actualizar_instrumento", args=[renglon.pk])
        post_data = {
            "tipo_instrumento": "DISPOSICION",
            "numero_instrumento": "",
        }
        resp = self.client.post(url, data=post_data)
        self.assertEqual(resp.status_code, 302)

        renglon.refresh_from_db()
        self.assertEqual(renglon.numero_instrumento, "012/2026")
