"""
Pruebas automatizadas para el Ticket 17.4: Control de Saldos y Topes.

Objetivo:
Calcular el saldo disponible restando los días consumidos en el período
correspondiente y bloquear excesos.

Especificaciones Técnicas:
Sumar los días otorgados de esa causal en el período en curso y comparar
con el tope máximo permitido.

Criterio de Aceptación:
Un titular que consumió 45 días de enfermedad común en el año calendario
ve bloqueado el intento de registrar el día 46.
"""

import datetime
from decimal import Decimal
import json
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.licencias.forms import (
    JustificacionDiferidaForm,
    LicenciaOtorgadaForm,
)
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.validaciones import (
    REGIMEN_INT,
    REGIMEN_TIT,
    calcular_saldo_licencia,
    obtener_rango_periodo_tope,
    validar_control_saldos_y_topes,
    validar_solicitud_licencia,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class ControlSaldosTopesTests(TestCase):
    """
    Suite de pruebas para control de saldos y topes estatutarios (Ticket 17.4).
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Roberto",
            apellido="Sosa",
            dni="26111222",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-174",
            nombre="Desarrollo de Software",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="SO-174",
            nombre="Sistemas Operativos",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-174",
            descripcion="Profesor",
            activo=True,
        )

        # Cargo Titular con antigüedad amplia (ingreso en 2020)
        self.cargo_tit = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_TIT,
            fecha_alta=datetime.date(2020, 3, 1),
            activo=True,
        )

        # Tipo de Licencia: Enfermedad Común Titular (Art. 308 - 45 días anuales)
        self.tipo_enf_tit = TipoLicencia.objects.create(
            codigo="TIT-ORD-308",
            articulo="308",
            descripcion="Afecciones comunes titular",
            duracion_maxima=45,
            tope_anual=45,
            periodo_tope="Año calendario",
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable="TIT",
            activo=True,
        )

        # Tipo de Licencia: Licencia por Examen (16 días anuales)
        self.tipo_examen = TipoLicencia.objects.create(
            codigo="GEN-EXAM-335",
            articulo="335",
            descripcion="Rendir exámenes de estudio",
            duracion_maxima=16,
            tope_anual=16,
            periodo_tope="Año calendario",
            goce_haberes=True,
            cuadro_mensual="IL-02",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable="TIT,INT,SUP",
            activo=True,
        )

    # -------------------------------------------------------------------------
    # Tests de Períodos de Cómputo
    # -------------------------------------------------------------------------

    def test_obtener_rango_periodo_tope_anio_calendario(self):
        """Verifica que el año calendario abarque del 1 de enero al 31 de diciembre."""
        ini, fin, desc = obtener_rango_periodo_tope(
            "Año calendario", datetime.date(2026, 6, 15)
        )
        self.assertEqual(ini, datetime.date(2026, 1, 1))
        self.assertEqual(fin, datetime.date(2026, 12, 31))
        self.assertIn("2026", desc)

    def test_obtener_rango_periodo_tope_sin_tope(self):
        """Verifica que las licencias sin tope retornen None en sus límites."""
        ini, fin, desc = obtener_rango_periodo_tope(
            "Sin tope", datetime.date(2026, 6, 15)
        )
        self.assertIsNone(ini)
        self.assertIsNone(fin)
        self.assertEqual(desc, "Sin tope")

    # -------------------------------------------------------------------------
    # Criterio de Aceptación: Titular con 45 días consumidos bloquea el día 46
    # -------------------------------------------------------------------------

    def test_criterio_aceptacion_titular_45_dias_bloquea_dia_46(self):
        """
        Criterio de Aceptación:
        Un titular que consumió 45 días de enfermedad común en el año calendario
        ve bloqueado el intento de registrar el día 46.
        """
        # Otorgamos 30 días en marzo (1 al 30 de marzo = 30 días)
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 3, 30),
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

        # Otorgamos 15 días en junio (1 al 15 de junio = 15 días) -> Total: 45 días
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 6, 1),
            fecha_hasta_prevista=datetime.date(2026, 6, 15),
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

        # Intentamos registrar el día 46 en octubre (1 de octubre = 1 día)
        with self.assertRaises(ValidationError) as ctx:
            validar_control_saldos_y_topes(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=datetime.date(2026, 10, 1),
                fecha_hasta=datetime.date(2026, 10, 1),
            )

        mensaje = str(ctx.exception)
        self.assertIn("consumido 45 días", mensaje)
        self.assertIn("Saldo disponible: 0 días", mensaje)
        self.assertIn("supera el límite", mensaje)
        self.assertIn("46 días", mensaje)

    def test_titular_consumio_40_dias_permite_5_dias_restantes(self):
        """Un titular con 40 días consumidos puede solicitar los 5 días restantes."""
        # 40 días en marzo-abril (1 de marzo al 9 de abril = 40 días)
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 9),
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

        # Solicita 5 días en octubre (1 al 5 de octubre = 5 días) -> Total: 45
        try:
            validar_control_saldos_y_topes(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=datetime.date(2026, 10, 1),
                fecha_hasta=datetime.date(2026, 10, 5),
            )
        except ValidationError:
            self.fail("Debería permitirse solicitar los 5 días restantes del saldo.")

    def test_titular_consumio_40_dias_bloquea_solicitud_de_6_dias(self):
        """Un titular con 40 días consumidos ve bloqueada una solicitud de 6 días."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 9),
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

        # Solicita 6 días en octubre -> Total: 46 > 45
        with self.assertRaises(ValidationError) as ctx:
            validar_control_saldos_y_topes(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=datetime.date(2026, 10, 1),
                fecha_hasta=datetime.date(2026, 10, 6),
            )
        self.assertIn("Saldo disponible: 5 días", str(ctx.exception))

    def test_solicitud_en_nuevo_anio_calendario_reinicia_saldo(self):
        """En el año calendario siguiente (2027) se reinicia el saldo disponible."""
        # Consumió 45 días en 2026
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

        # En marzo de 2027 debe tener sus 45 días completos nuevamente
        res = calcular_saldo_licencia(
            tipo_licencia=self.tipo_enf_tit,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2027, 3, 1),
            fecha_hasta=datetime.date(2027, 3, 10),
        )
        self.assertEqual(res["dias_consumidos"], 0)
        self.assertEqual(res["saldo_disponible"], 45)
        self.assertFalse(res["supera_tope"])

    # -------------------------------------------------------------------------
    # Respeto a Topes Reducidos por Antigüedad (Ticket 17.2 + 17.4)
    # -------------------------------------------------------------------------

    def test_interino_antiguedad_menor_4_meses_tope_reducido_a_10_dias(self):
        """
        Un interino con 2 meses de antigüedad tiene tope reducido a 10 días;
        si ya consumió 8 días, su saldo es de 2 días.
        """
        cargo_int = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_INT,
            fecha_alta=datetime.date(2026, 8, 1),  # 2 meses a octubre
            activo=True,
        )
        tipo_enf_int = TipoLicencia.objects.create(
            codigo="INT-ORD-330",
            articulo="330",
            descripcion="Afecciones comunes interinos",
            duracion_maxima=30,
            tope_anual=30,
            periodo_tope="Año calendario",
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_INT,
            situacion_revista_aplicable="INT",
            activo=True,
        )

        # Consumió 8 días en agosto (10 al 17 de agosto = 8 días)
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=cargo_int,
            tipo_licencia=tipo_enf_int,
            fecha_desde=datetime.date(2026, 8, 10),
            fecha_hasta_prevista=datetime.date(2026, 8, 17),
            estado="OTORGADA",
        )

        # Saldo disponible debe ser 10 - 8 = 2 días
        res = calcular_saldo_licencia(
            tipo_licencia=tipo_enf_int,
            docente=self.docente,
            cargo=cargo_int,
            fecha_desde=datetime.date(2026, 10, 1),
            dias_solicitados=3,
        )
        self.assertEqual(res["tope_maximo"], 10)
        self.assertTrue(res["tope_reducido"])
        self.assertEqual(res["dias_consumidos"], 8)
        self.assertEqual(res["saldo_disponible"], 2)
        self.assertTrue(res["supera_tope"])

    # -------------------------------------------------------------------------
    # Exclusión de Estados Inactivos (CANCELADA / RECHAZADA)
    # -------------------------------------------------------------------------

    def test_licencia_cancelada_no_consume_saldo(self):
        """Licencias canceladas no restan del saldo disponible."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="CANCELADA",
        )
        res = calcular_saldo_licencia(
            tipo_licencia=self.tipo_enf_tit,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2026, 10, 1),
        )
        self.assertEqual(res["dias_consumidos"], 0)
        self.assertEqual(res["saldo_disponible"], 45)

    def test_licencia_rechazada_no_consume_saldo(self):
        """Licencias rechazadas no restan del saldo disponible."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="RECHAZADA",
        )
        res = calcular_saldo_licencia(
            tipo_licencia=self.tipo_enf_tit,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2026, 10, 1),
        )
        self.assertEqual(res["dias_consumidos"], 0)
        self.assertEqual(res["saldo_disponible"], 45)

    # -------------------------------------------------------------------------
    # Edición de Licencia Existente (excluir_id)
    # -------------------------------------------------------------------------

    def test_edicion_licencia_existente_no_se_autoconsume(self):
        """Al modificar una licencia existente, sus días no se suman al saldo."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),  # 45 días
            estado="OTORGADA",
        )

        # Si se valida la misma instancia, no debe autobloquearse
        try:
            validar_control_saldos_y_topes(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=lic.fecha_desde,
                fecha_hasta=lic.fecha_hasta_prevista,
                instancia_actual=lic,
            )
        except ValidationError:
            self.fail("La edición de la misma licencia no debe bloquearse a sí misma.")

    # -------------------------------------------------------------------------
    # Integración con Modelo LicenciaOtorgada
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_model_save_bloquea_dia_46(self):
        """El modelo LicenciaOtorgada ejecuta validación de saldos en clean()/save()."""
        # Consumió 45 días
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
        )

        # Intento de registrar el día 46 en noviembre
        lic_46 = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 11, 1),
            fecha_hasta_prevista=datetime.date(2026, 11, 1),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError) as ctx:
            lic_46.save()

        self.assertIn("consumido 45 días", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Integración con Formularios
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_form_bloquea_dia_46(self):
        """LicenciaOtorgadaForm rechaza solicitudes que superen el saldo disponible."""
        # 45 días otorgados previamente
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
        )

        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_tit.pk,
            "tipo_licencia": self.tipo_enf_tit.pk,
            "fecha_desde": "2026-11-01",
            "fecha_hasta_prevista": "2026-11-01",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("consumido 45 días", str(form.errors["tipo_licencia"]))

    def test_justificacion_diferida_form_bloquea_exceso_de_tope(self):
        """JustificacionDiferidaForm rechaza justificaciones que excedan el tope."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
        )

        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_tit.pk,
            "tipo_licencia": self.tipo_enf_tit.pk,
            "fecha_desde": "2026-11-01",
            "fecha_hasta": "2026-11-01",
            "nueva_marca": "LIC",
            "observaciones": "Intento de justificar día 46",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("consumido 45 días", str(form.errors["tipo_licencia"]))

    # -------------------------------------------------------------------------
    # Integración con Función Orquestadora
    # -------------------------------------------------------------------------

    def test_validar_solicitud_licencia_orquestador_bloquea_dia_46(self):
        """validar_solicitud_licencia bloquea integralmente ante saldo agotado."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError) as ctx:
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=datetime.date(2026, 11, 1),
                fecha_hasta=datetime.date(2026, 11, 1),
            )
        self.assertIn("consumido 45 días", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Endpoint API: Validar Saldos y Topes
    # -------------------------------------------------------------------------

    def test_api_validar_saldos_get_bloquea_dia_46(self):
        """Endpoint API responde status 200 con valido=False y saldo_disponible=0."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_enf_tit,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 14),
            estado="OTORGADA",
        )

        url = reverse("licencias:validar_saldos")
        response = self.client.get(
            url,
            {
                "tipo_licencia": self.tipo_enf_tit.pk,
                "docente": self.docente.pk,
                "cargo": self.cargo_tit.pk,
                "fecha_desde": "2026-11-01",
                "fecha_hasta": "2026-11-01",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["valido"])
        self.assertTrue(data["supera_tope"])
        self.assertEqual(data["dias_consumidos"], 45)
        self.assertEqual(data["saldo_disponible"], 0)
        self.assertEqual(data["tope_maximo"], 45)

    def test_api_validar_saldos_get_permite_dentro_del_saldo(self):
        """Endpoint API responde valido=True si la solicitud no supera el saldo."""
        url = reverse("licencias:validar_saldos")
        response = self.client.get(
            url,
            {
                "tipo_licencia": self.tipo_enf_tit.pk,
                "docente": self.docente.pk,
                "cargo": self.cargo_tit.pk,
                "fecha_desde": "2026-11-01",
                "fecha_hasta": "2026-11-10",  # 10 días de 45 disponibles
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valido"])
        self.assertFalse(data["supera_tope"])
        self.assertEqual(data["saldo_disponible"], 45)
        self.assertEqual(data["dias_consumidos"], 0)

    def test_api_validar_saldos_post_json(self):
        """Endpoint API acepta payload JSON por POST."""
        url = reverse("licencias:validar_saldos")
        payload = {
            "codigo": self.tipo_enf_tit.codigo,
            "docente_id": self.docente.pk,
            "cargo_id": self.cargo_tit.pk,
            "fecha_desde": "2026-11-01",
            "dias": 10,
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valido"])
        self.assertEqual(data["dias_solicitados"], 10)
