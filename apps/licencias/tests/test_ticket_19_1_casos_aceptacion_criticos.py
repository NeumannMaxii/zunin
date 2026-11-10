"""
Ticket 19 / Tarea 19.1: Automatización de Casos de Aceptación críticos.

Objetivo:
Asegurar mediante pruebas automatizadas integrales los escenarios fundamentales
exigidos por la normativa de la Ley 647-E sobre el catálogo oficial poblado.

Casos cubiertos:
- CA-01: Tope anual de 45 días en enfermedad común de personal Titular
  (Art. 308 - TIT-ORD-308), bloqueo del día 46, liberación por anulación,
  reinicio en nuevo año calendario y separación respecto a largo tratamiento.
- CA-02: Recorte de tope a 10 días para personal Interino con antigüedad menor
  a 4 meses en enfermedad común (Art. 330 - INT-ORD-330-MEN / INT-ORD-330-MAY)
  y desbloqueo del tope de 30 días al cumplir exactamente 4 meses.
- CA-03: Recorte de tope a 5 días para personal Suplente con antigüedad menor
  a 4 meses en enfermedad común (Art. 339 - SUP-ORD-339-MEN / SUP-ORD-339-MAY)
  y desbloqueo del tope de 15 días al cumplir exactamente 4 meses.
- CA-12: Cálculo automático de días hábiles omitiendo fines de semana
  (sábados y domingos) y feriados/asuetos registrados en DiaNoLaborable, tanto
  en el motor de cálculo como en API y sincronización/justificación diaria.
"""

import datetime
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.core.seeder import poblar_catalogo_normativo_ley647e
from apps.licencias.calculador import (
    UNIDAD_HABILES,
    calcular_fechas_licencia,
    contar_dias_habiles,
)
from apps.licencias.forms import LicenciaOtorgadaForm
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.services import procesar_justificacion_rango
from apps.licencias.validaciones import (
    REGIMEN_INT,
    REGIMEN_SUP,
    REGIMEN_TIT,
    calcular_saldo_licencia,
    obtener_tope_efectivo_licencia,
    validar_solicitud_licencia,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)

User = get_user_model()


class BaseCasosAceptacionLey647ETestCase(TestCase):
    """
    Fixture común con el catálogo normativo oficial de Ley 647-E poblado,
    estructura curricular y usuario operador autenticado.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        poblar_catalogo_normativo_ley647e()

        cls.user = User.objects.create_superuser(
            username="bedelia_ca_test",
            password="test_password_ca_19_1",
            email="bedelia.ca@example.com",
        )
        cls.carrera = Carrera.objects.create(
            codigo="TSDS-CA19",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        cls.espacio = EspacioCurricular.objects.create(
            codigo="PRG-CA19",
            nombre="Programación IV",
            carrera=cls.carrera,
            anio=2,
            turno="NOCHE",
        )
        cls.cargo_cat = CargoCatalogo.objects.create(
            codigo="PROF-CA19",
            descripcion="Profesor de Nivel Superior",
            activo=True,
        )

        # Tipos oficiales poblados por el seeder de la Ley 647-E
        cls.tipo_tit_308 = TipoLicencia.objects.get(codigo="TIT-ORD-308")
        cls.tipo_tit_309 = TipoLicencia.objects.get(codigo="TIT-ORD-309-100")
        cls.tipo_int_330_men = TipoLicencia.objects.get(codigo="INT-ORD-330-MEN")
        cls.tipo_int_330_may = TipoLicencia.objects.get(codigo="INT-ORD-330-MAY")
        cls.tipo_sup_339_men = TipoLicencia.objects.get(codigo="SUP-ORD-339-MEN")
        cls.tipo_sup_339_may = TipoLicencia.objects.get(codigo="SUP-ORD-339-MAY")
        cls.tipo_tit_matrimonio = TipoLicencia.objects.get(codigo="TIT-EXT-318-G")
        cls.tipo_int_matrimonio = TipoLicencia.objects.get(codigo="INT-EXT-335-MATR")
        cls.tipo_sup_matrimonio = TipoLicencia.objects.get(codigo="SUP-EXT-344-MATR")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def _crear_cargo(
        self,
        docente,
        regimen,
        fecha_alta,
        con_carga_horaria=True,
    ):
        horas = 2 if con_carga_horaria else 0
        return CargoDocente.objects.create(
            docente=docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=regimen,
            fecha_alta=fecha_alta,
            horas_lunes=horas,
            horas_martes=horas,
            horas_miercoles=horas,
            horas_jueves=horas,
            horas_viernes=horas,
            activo=True,
        )


class TestCA01TopeEnfermedadComunTitular(BaseCasosAceptacionLey647ETestCase):
    """
    CA-01: Tope anual de 45 días en enfermedad común de personal Titular (Art. 308).
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Elena",
            apellido="Gutiérrez",
            dni="27100201",
            activo=True,
        )
        self.cargo_tit = self._crear_cargo(
            docente=self.docente,
            regimen=REGIMEN_TIT,
            fecha_alta=datetime.date(2019, 3, 1),
        )

    def test_ca01_titular_consume_45_dias_discontinuos_y_bloquea_dia_46(self):
        """
        CA-01: Un docente titular puede tomar hasta 45 días continuos o
        discontinuos en el año calendario y el día 46 queda bloqueado en modelo,
        formulario, vista HTTP y API de saldos.
        """
        # Tramo 1: 20 días (01/03 al 20/03/2026)
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 3, 20),
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        # Tramo 2: 15 días (10/05 al 24/05/2026) -> acumulado: 35 días
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 5, 10),
            fecha_hasta_prevista=datetime.date(2026, 5, 24),
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        # Tramo 3: últimos 10 días permitidos (01/08 al 10/08/2026) -> total: 45 días
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 8, 1),
            fecha_hasta_prevista=datetime.date(2026, 8, 10),
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        saldo = calcular_saldo_licencia(
            tipo_licencia=self.tipo_tit_308,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2026, 10, 5),
        )
        self.assertEqual(saldo["tope_maximo"], 45)
        self.assertEqual(saldo["dias_consumidos"], 45)
        self.assertEqual(saldo["saldo_disponible"], 0)
        self.assertFalse(saldo["tope_reducido"])

        # 1. Bloqueo directo en modelo (.save() / .clean()) para el día 46
        lic_dia_46 = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 10, 5),
            fecha_hasta_prevista=datetime.date(2026, 10, 5),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError) as ctx_mod:
            lic_dia_46.save()
        self.assertIn("45 días", str(ctx_mod.exception))

        # 2. Bloqueo en LicenciaOtorgadaForm
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_tit.pk,
            "tipo_licencia": self.tipo_tit_308.pk,
            "fecha_desde": "2026-10-05",
            "fecha_hasta_prevista": "2026-10-05",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)

        # 3. Bloqueo en vista HTTP POST de creación de solicitud
        total_previo = LicenciaOtorgada.objects.count()
        url_create = reverse("licencias:licenciaotorgada_create")
        resp_post = self.client.post(url_create, data=form_data)
        self.assertEqual(resp_post.status_code, 200)
        self.assertEqual(LicenciaOtorgada.objects.count(), total_previo)

        # 4. Bloqueo en API /api/licencias/validar-saldos/
        url_api = reverse("licencias:validar_saldos")
        resp_api = self.client.get(
            url_api,
            {
                "codigo": "TIT-ORD-308",
                "docente": self.docente.pk,
                "cargo": self.cargo_tit.pk,
                "fecha_desde": "2026-10-05",
                "fecha_hasta": "2026-10-05",
            },
        )
        self.assertEqual(resp_api.status_code, 200)
        data_api = resp_api.json()
        self.assertFalse(data_api["valido"])
        self.assertTrue(data_api["supera_tope"])
        self.assertEqual(data_api["dias_consumidos"], 45)
        self.assertEqual(data_api["saldo_disponible"], 0)
        self.assertEqual(data_api["dias_restantes"], 0)

    def test_ca01_titular_bloquea_solicitud_unica_de_46_dias(self):
        """
        CA-01: Una única solicitud continua de 46 días de enfermedad común
        debe ser rechazada desde el inicio por exceder el tope de 45 días.
        """
        with self.assertRaises(ValidationError) as ctx:
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_tit_308,
                docente=self.docente,
                cargo=self.cargo_tit,
                fecha_desde=datetime.date(2026, 4, 1),
                fecha_hasta=datetime.date(2026, 5, 16),  # 46 días corridos
            )
        self.assertIn("45", str(ctx.exception))

    def test_ca01_titular_anulacion_libera_saldo_y_reinicio_anual(self):
        """
        CA-01: Anular una licencia libera esos días del saldo anual y el nuevo
        año calendario reinicia el cupo completo de 45 días.
        """
        lic_a = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 3, 30),  # 30 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        lic_b = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 6, 1),
            fecha_hasta_prevista=datetime.date(2026, 6, 15),  # 15 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        # Anulamos lic_b (15 días) -> saldo disponible vuelve a 15 días
        lic_b.anular(usuario=self.user, motivo="Rectificación médica")
        lic_reemplazo = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 9, 1),
            fecha_hasta_prevista=datetime.date(2026, 9, 15),  # 15 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        self.assertIsNotNone(lic_reemplazo.pk)

        # Al iniciar el año calendario 2027, vuelve a disponer de 45 días completos
        saldo_2027 = calcular_saldo_licencia(
            tipo_licencia=self.tipo_tit_308,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2027, 2, 1),
            fecha_hasta=datetime.date(2027, 3, 17),  # 45 días exactos
        )
        self.assertEqual(lic_a.dias_duracion_prevista, 30)
        self.assertEqual(saldo_2027["dias_consumidos"], 0)
        self.assertEqual(saldo_2027["saldo_disponible"], 45)
        self.assertFalse(saldo_2027["supera_tope"])

    def test_ca01_largo_tratamiento_no_consume_saldo_enfermedad_comun(self):
        """
        CA-01: El uso de Art. 309 (Largo Tratamiento) es independiente de los
        45 días anuales de Art. 308 (Enfermedad Común).
        """
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_309,
            fecha_desde=datetime.date(2026, 2, 1),
            fecha_hasta_prevista=datetime.date(2026, 3, 22),  # 50 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        saldo_comun = calcular_saldo_licencia(
            tipo_licencia=self.tipo_tit_308,
            docente=self.docente,
            cargo=self.cargo_tit,
            fecha_desde=datetime.date(2026, 5, 1),
            fecha_hasta=datetime.date(2026, 5, 10),
        )
        self.assertEqual(saldo_comun["dias_consumidos"], 0)
        self.assertEqual(saldo_comun["saldo_disponible"], 45)
        self.assertFalse(saldo_comun["supera_tope"])


class TestCA02CA03AntiguedadInterinosYSuplentes(BaseCasosAceptacionLey647ETestCase):
    """
    CA-02 / CA-03: Topes reducidos por antigüedad menor a 4 meses para
    personal Interino (Art. 330 -> 10 días) y Suplente (Art. 339 -> 5 días).
    """

    def setUp(self):
        super().setUp()
        self.docente_int = Docente.objects.create(
            nombre="Carlos",
            apellido="Méndez",
            dni="33100202",
            activo=True,
        )
        self.docente_sup = Docente.objects.create(
            nombre="Lucía",
            apellido="Fernández",
            dni="34100203",
            activo=True,
        )

    def test_ca02_interino_menor_4_meses_tope_10_dias_y_bloqueo_dia_11(self):
        """
        CA-02: Interino con < 4 meses de antigüedad (Art. 330) tiene su tope
        recortado a 10 días corridos, tanto por consumo único como acumulado,
        validado en motor, modelo, formulario HTTP y APIs.
        """
        cargo_int = self._crear_cargo(
            docente=self.docente_int,
            regimen=REGIMEN_INT,
            fecha_alta=datetime.date(2026, 7, 1),  # 3 meses al 01/10/2026
        )

        # Incluso consultando INT-ORD-330-MAY (30d), el motor recorta a 10 días
        info = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_int_330_may,
            cargo=cargo_int,
            docente=self.docente_int,
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(info["antiguedad_meses"], 3)
        self.assertEqual(info["tope_dias"], 10)
        self.assertTrue(info["tope_reducido"])

        # Solicitud de 11 días seguidos bloqueada
        with self.assertRaises(ValidationError) as ctx_directo:
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_int_330_men,
                docente=self.docente_int,
                cargo=cargo_int,
                fecha_desde=datetime.date(2026, 10, 1),
                fecha_hasta=datetime.date(2026, 10, 11),  # 11 días
            )
        self.assertIn("10 días", str(ctx_directo.exception))

        # Consumo discontinuo dentro del tope reducido: 6 + 4 = 10 días
        LicenciaOtorgada.objects.create(
            docente=self.docente_int,
            cargo=cargo_int,
            tipo_licencia=self.tipo_int_330_men,
            fecha_desde=datetime.date(2026, 9, 1),
            fecha_hasta_prevista=datetime.date(2026, 9, 6),  # 6 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        LicenciaOtorgada.objects.create(
            docente=self.docente_int,
            cargo=cargo_int,
            tipo_licencia=self.tipo_int_330_men,
            fecha_desde=datetime.date(2026, 10, 1),
            fecha_hasta_prevista=datetime.date(2026, 10, 4),  # 4 días -> total 10
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        # Intento de día 11 debe bloquearse en modelo, vista POST y APIs
        lic_11 = LicenciaOtorgada(
            docente=self.docente_int,
            cargo=cargo_int,
            tipo_licencia=self.tipo_int_330_men,
            fecha_desde=datetime.date(2026, 10, 10),
            fecha_hasta_prevista=datetime.date(2026, 10, 10),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError):
            lic_11.save()

        form_data = {
            "docente": self.docente_int.pk,
            "cargo": cargo_int.pk,
            "tipo_licencia": self.tipo_int_330_men.pk,
            "fecha_desde": "2026-10-10",
            "fecha_hasta_prevista": "2026-10-10",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        total_antes = LicenciaOtorgada.objects.count()
        resp_form = self.client.post(
            reverse("licencias:licenciaotorgada_create"), data=form_data
        )
        self.assertEqual(resp_form.status_code, 200)
        self.assertEqual(LicenciaOtorgada.objects.count(), total_antes)

        resp_saldos = self.client.get(
            reverse("licencias:validar_saldos"),
            {
                "codigo": "INT-ORD-330-MEN",
                "docente": self.docente_int.pk,
                "cargo": cargo_int.pk,
                "fecha_desde": "2026-10-10",
                "fecha_hasta": "2026-10-10",
            },
        )
        self.assertEqual(resp_saldos.status_code, 200)
        data_saldos = resp_saldos.json()
        self.assertFalse(data_saldos["valido"])
        self.assertEqual(data_saldos["tope_maximo"], 10)
        self.assertTrue(data_saldos["tope_reducido"])
        self.assertEqual(data_saldos["dias_consumidos"], 10)

        resp_antig = self.client.get(
            reverse("licencias:validar_antiguedad"),
            {
                "codigo": "INT-ORD-330-MAY",
                "docente": self.docente_int.pk,
                "cargo": cargo_int.pk,
                "fecha_desde": "2026-10-10",
                "dias": 11,
            },
        )
        self.assertEqual(resp_antig.status_code, 200)
        data_antig = resp_antig.json()
        self.assertFalse(data_antig["valido"])
        self.assertEqual(data_antig["tope_dias"], 10)
        self.assertTrue(data_antig["tope_reducido"])

    def test_ca02_interino_borde_exacto_3_vs_4_meses_cumplidos(self):
        """
        CA-02: Un interino con 3 meses y 29 días sigue en < 4 meses (tope 10d),
        mientras que al cumplir exactamente 4 meses calendario desbloquea 30 días.
        """
        # Alta 02/06/2026 -> al 01/10/2026 faltan 1 día para cumplir 4 meses
        cargo_borde = self._crear_cargo(
            docente=self.docente_int,
            regimen=REGIMEN_INT,
            fecha_alta=datetime.date(2026, 6, 2),
        )
        info_antes = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_int_330_may,
            cargo=cargo_borde,
            docente=self.docente_int,
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(info_antes["antiguedad_meses"], 3)
        self.assertEqual(info_antes["tope_dias"], 10)
        self.assertTrue(info_antes["tope_reducido"])

        # Al día siguiente (02/10/2026) cumple exactamente 4 meses -> tope 30 días
        info_exacto = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_int_330_may,
            cargo=cargo_borde,
            docente=self.docente_int,
            fecha_referencia=datetime.date(2026, 10, 2),
        )
        self.assertEqual(info_exacto["antiguedad_meses"], 4)
        self.assertEqual(info_exacto["tope_dias"], 30)
        self.assertFalse(info_exacto["tope_reducido"])

        # Permite 30 días continuos y bloquea 31 días
        validar_solicitud_licencia(
            tipo_licencia=self.tipo_int_330_may,
            docente=self.docente_int,
            cargo=cargo_borde,
            fecha_desde=datetime.date(2026, 10, 2),
            dias=30,
        )
        with self.assertRaises(ValidationError):
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_int_330_may,
                docente=self.docente_int,
                cargo=cargo_borde,
                fecha_desde=datetime.date(2026, 10, 2),
                dias=31,
            )

    def test_ca03_suplente_menor_4_meses_tope_5_dias_y_bloqueo_dia_6(self):
        """
        CA-03: Suplente con < 4 meses de antigüedad (Art. 339) tiene tope
        recortado a 5 días corridos; 6 días o el día 6 acumulado se bloquean.
        """
        cargo_sup = self._crear_cargo(
            docente=self.docente_sup,
            regimen=REGIMEN_SUP,
            fecha_alta=datetime.date(2026, 8, 15),  # 1 mes al 01/10/2026
        )

        # Incluso consultando SUP-ORD-339-MAY (15d), recorta a 5 días
        info = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_sup_339_may,
            cargo=cargo_sup,
            docente=self.docente_sup,
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(info["antiguedad_meses"], 1)
        self.assertEqual(info["tope_dias"], 5)
        self.assertTrue(info["tope_reducido"])

        # Solicitud directa de 6 días bloqueada
        with self.assertRaises(ValidationError) as ctx:
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_sup_339_men,
                docente=self.docente_sup,
                cargo=cargo_sup,
                fecha_desde=datetime.date(2026, 10, 1),
                fecha_hasta=datetime.date(2026, 10, 6),  # 6 días
            )
        self.assertIn("5 días", str(ctx.exception))

        # Consumo acumulado de 3 + 2 = 5 días permitido
        LicenciaOtorgada.objects.create(
            docente=self.docente_sup,
            cargo=cargo_sup,
            tipo_licencia=self.tipo_sup_339_men,
            fecha_desde=datetime.date(2026, 9, 10),
            fecha_hasta_prevista=datetime.date(2026, 9, 12),  # 3 días
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )
        LicenciaOtorgada.objects.create(
            docente=self.docente_sup,
            cargo=cargo_sup,
            tipo_licencia=self.tipo_sup_339_men,
            fecha_desde=datetime.date(2026, 10, 1),
            fecha_hasta_prevista=datetime.date(2026, 10, 2),  # 2 días -> total 5
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        # Intento de registrar el día 6 bloqueado en modelo, form HTTP y APIs
        lic_6 = LicenciaOtorgada(
            docente=self.docente_sup,
            cargo=cargo_sup,
            tipo_licencia=self.tipo_sup_339_men,
            fecha_desde=datetime.date(2026, 10, 5),
            fecha_hasta_prevista=datetime.date(2026, 10, 5),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError):
            lic_6.save()

        form_data = {
            "docente": self.docente_sup.pk,
            "cargo": cargo_sup.pk,
            "tipo_licencia": self.tipo_sup_339_men.pk,
            "fecha_desde": "2026-10-05",
            "fecha_hasta_prevista": "2026-10-05",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        total_antes = LicenciaOtorgada.objects.count()
        resp_post = self.client.post(
            reverse("licencias:licenciaotorgada_create"), data=form_data
        )
        self.assertEqual(resp_post.status_code, 200)
        self.assertEqual(LicenciaOtorgada.objects.count(), total_antes)

        resp_api = self.client.get(
            reverse("licencias:validar_saldos"),
            {
                "codigo": "SUP-ORD-339-MEN",
                "docente": self.docente_sup.pk,
                "cargo": cargo_sup.pk,
                "fecha_desde": "2026-10-05",
                "fecha_hasta": "2026-10-05",
            },
        )
        self.assertEqual(resp_api.status_code, 200)
        data_api = resp_api.json()
        self.assertFalse(data_api["valido"])
        self.assertEqual(data_api["tope_maximo"], 5)
        self.assertTrue(data_api["tope_reducido"])
        self.assertEqual(data_api["dias_consumidos"], 5)
        self.assertEqual(data_api["saldo_disponible"], 0)

        resp_antig_sup = self.client.get(
            reverse("licencias:validar_antiguedad"),
            {
                "codigo": "SUP-ORD-339-MAY",
                "docente": self.docente_sup.pk,
                "cargo": cargo_sup.pk,
                "fecha_desde": "2026-10-05",
                "dias": 6,
            },
        )
        self.assertEqual(resp_antig_sup.status_code, 200)
        data_antig_sup = resp_antig_sup.json()
        self.assertFalse(data_antig_sup["valido"])
        self.assertEqual(data_antig_sup["tope_dias"], 5)
        self.assertTrue(data_antig_sup["tope_reducido"])

    def test_ca03_suplente_con_4_meses_desbloquea_tope_15_dias(self):
        """
        CA-03: Suplente con 4 meses cumplidos accede al tope completo de 15 días
        corridos (SUP-ORD-339-MAY) y se bloquea recién al día 16.
        """
        cargo_sup_4m = self._crear_cargo(
            docente=self.docente_sup,
            regimen=REGIMEN_SUP,
            fecha_alta=datetime.date(2026, 6, 1),  # 4 meses al 01/10/2026
        )

        info = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_sup_339_may,
            cargo=cargo_sup_4m,
            docente=self.docente_sup,
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(info["antiguedad_meses"], 4)
        self.assertEqual(info["tope_dias"], 15)
        self.assertFalse(info["tope_reducido"])

        # Permite exactamente 15 días y bloquea 16 días
        validar_solicitud_licencia(
            tipo_licencia=self.tipo_sup_339_may,
            docente=self.docente_sup,
            cargo=cargo_sup_4m,
            fecha_desde=datetime.date(2026, 10, 1),
            dias=15,
        )
        with self.assertRaises(ValidationError):
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_sup_339_may,
                docente=self.docente_sup,
                cargo=cargo_sup_4m,
                fecha_desde=datetime.date(2026, 10, 1),
                dias=16,
            )


class TestCA12CalculoDiasHabilesYFeriados(BaseCasosAceptacionLey647ETestCase):
    """
    CA-12: Cálculo de días hábiles omitiendo fines de semana y feriados.
    """

    def setUp(self):
        super().setUp()
        # Calendario de prueba: Octubre 2026
        # Jue 08/10, Vie 09/10, Sáb 10/10, Dom 11/10, Lun 12/10 (Feriado),
        # Mar 13/10, Mié 14/10 (Asueto), Jue 15/10, Vie 16/10, Sáb 17/10,
        # Dom 18/10, Lun 19/10, Mar 20/10, Mié 21/10, Jue 22/10, Vie 23/10,
        # Sáb 24/10, Dom 25/10, Lun 26/10 (Feriado puente), Mar 27/10.
        self.feriado_lun_12 = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 10, 12),
            tipo="FERIADO",
            descripcion="Día del Respeto a la Diversidad Cultural",
        )
        self.asueto_mie_14 = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 10, 14),
            tipo="ASUETO",
            descripcion="Asueto Institucional IESETyFP",
        )
        self.feriado_lun_26 = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 10, 26),
            tipo="FERIADO",
            descripcion="Feriado Puente Institucional",
        )

    def test_ca12_dias_habiles_omite_fines_de_semana_y_feriados_bd(self):
        """
        CA-12: Una licencia con unidad Hábiles del catálogo oficial (10 días
        hábiles - TIT-EXT-318-G) iniciada un jueves salta sábados, domingos y
        los feriados/asuetos de DiaNoLaborable, incluido un feriado en el día
        candidato de reintegro.
        """
        inicio_jueves = datetime.date(2026, 10, 8)
        res = self.tipo_tit_matrimonio.calcular_fechas(
            fecha_desde=inicio_jueves,
            dias=10,
        )

        # Desglose esperado de los 10 días hábiles:
        # 1: Jue 08/10 | 2: Vie 09/10
        # [Sáb 10/10, Dom 11/10 omitidos]
        # [Lun 12/10 FERIADO omitido]
        # 3: Mar 13/10
        # [Mié 14/10 ASUETO omitido]
        # 4: Jue 15/10 | 5: Vie 16/10
        # [Sáb 17/10, Dom 18/10 omitidos]
        # 6: Lun 19/10 | 7: Mar 20/10 | 8: Mié 21/10 | 9: Jue 22/10 | 10: Vie 23/10
        # Reintegro candidato Sáb 24/10 -> Dom 25/10 -> Lun 26/10 (FERIADO)
        # => Reintegro efectivo: Martes 27/10/2026
        self.assertEqual(res.unidad, UNIDAD_HABILES)
        self.assertEqual(res.dias_consumidos, 10)
        self.assertEqual(res.dias_habiles, 10)
        self.assertEqual(res.fecha_hasta, datetime.date(2026, 10, 23))
        self.assertEqual(res.fecha_reintegro, datetime.date(2026, 10, 27))
        self.assertEqual(res.dias_corridos, 16)  # 08/10 al 23/10 inclusive
        self.assertEqual(res.fines_de_semana, 4)  # 10, 11, 17, 18 de octubre
        self.assertEqual(
            res.dias_feriados,
            [self.feriado_lun_12.fecha, self.asueto_mie_14.fecha],
        )

        # Caso puente corto: 2 días hábiles desde Viernes 09/10 (SUP-EXT-344-MATR)
        # Día 1: Vie 09/10 -> [Sáb 10, Dom 11, Lun 12 Feriado] -> Día 2: Mar 13/10
        # Candidato reintegro Mié 14/10 (Asueto) -> Reintegro efectivo: Jue 15/10
        res_puente = self.tipo_sup_matrimonio.calcular_fechas(
            fecha_desde=datetime.date(2026, 10, 9),
            dias=2,
        )
        self.assertEqual(res_puente.fecha_hasta, datetime.date(2026, 10, 13))
        self.assertEqual(res_puente.fecha_reintegro, datetime.date(2026, 10, 15))
        self.assertEqual(res_puente.dias_consumidos, 2)
        self.assertEqual(res_puente.fines_de_semana, 2)
        self.assertEqual(res_puente.dias_feriados, [self.feriado_lun_12.fecha])

    def test_ca12_conteo_inverso_rango_explicito_y_endpoint_api(self):
        """
        CA-12: Dado un rango explícito [fecha_desde, fecha_hasta], el cálculo
        inverso y el endpoint API /api/licencias/calcular-fechas/ descuentan
        exactamente fines de semana y días no laborables.
        """
        # Rango: Vie 09/10/2026 al Vie 16/10/2026 (8 días calendario)
        # No laborables: Sáb 10, Dom 11, Lun 12 (Feriado), Mié 14 (Asueto)
        # Hábiles esperados (4): Vie 09, Mar 13, Jue 15, Vie 16
        f_desde = datetime.date(2026, 10, 9)
        f_hasta = datetime.date(2026, 10, 16)

        self.assertEqual(contar_dias_habiles(f_desde, f_hasta), 4)

        calc = calcular_fechas_licencia(
            fecha_desde=f_desde,
            fecha_hasta=f_hasta,
            tipo_licencia=self.tipo_int_matrimonio,
        )
        self.assertEqual(calc.dias_consumidos, 4)
        self.assertEqual(calc.dias_habiles, 4)
        self.assertEqual(calc.dias_corridos, 8)
        self.assertEqual(calc.fines_de_semana, 2)
        self.assertEqual(calc.fecha_reintegro, datetime.date(2026, 10, 19))

        # Verificación vía HTTP GET en API REST
        url_api = reverse("licencias:calcular_fechas")
        resp_get = self.client.get(
            url_api,
            {
                "fecha_desde": "2026-10-08",
                "dias": 2,
                "tipo_licencia": self.tipo_sup_matrimonio.codigo,
            },
        )
        self.assertEqual(resp_get.status_code, 200)
        payload = resp_get.json()
        self.assertEqual(payload["status"], "success")
        data = payload["data"]
        # 2 días hábiles desde Jue 08/10 -> Vie 09/10;
        # Sáb 10, Dom 11 y Lun 12 (feriado) omitidos -> reintegro Mar 13/10
        self.assertEqual(data["fecha_hasta"], "2026-10-09")
        self.assertEqual(data["fecha_reintegro"], "2026-10-13")
        self.assertEqual(data["dias_consumidos"], 2)

        # Verificación vía HTTP POST en /api/calcular-fechas/ (alias api_licencias)
        resp_post = self.client.post(
            reverse("api_licencias:calcular_fechas"),
            {
                "fecha_desde": "2026-10-09",
                "fecha_hasta": "2026-10-16",
                "tipo_licencia": self.tipo_int_matrimonio.pk,
            },
        )
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()["data"]
        self.assertEqual(data_post["dias_habiles"], 4)
        self.assertEqual(data_post["fines_de_semana"], 2)
        self.assertEqual(
            json.dumps(data_post["dias_feriados"]),
            json.dumps(["2026-10-12", "2026-10-14"]),
        )

    def test_ca12_sincronizacion_asistencia_y_justificacion_omiten_feriados_y_findes(
        self,
    ):
        """
        CA-12: Tanto la sincronización de LicenciaOtorgada como la justificación
        diferida por rango omiten fines de semana y feriados al generar marcas
        diarias 'LIC' en RegistroAsistencia.
        """
        docente = Docente.objects.create(
            nombre="Sofía",
            apellido="Almirón",
            dni="30555666",
            activo=True,
        )
        cargo = self._crear_cargo(
            docente=docente,
            regimen=REGIMEN_TIT,
            fecha_alta=datetime.date(2020, 3, 1),
        )

        # 1. LicenciaOtorgada aprobada del Vie 09/10 al Vie 16/10/2026
        LicenciaOtorgada.objects.create(
            docente=docente,
            cargo=cargo,
            tipo_licencia=self.tipo_tit_matrimonio,
            fecha_desde=datetime.date(2026, 10, 9),
            fecha_hasta_prevista=datetime.date(2026, 10, 16),
            estado="OTORGADA",
        )

        fechas_sync = sorted(
            RegistroAsistencia.objects.filter(
                docente=docente, cargo=cargo, marca_diaria="LIC"
            ).values_list("fecha", flat=True)
        )
        esperadas = [
            datetime.date(2026, 10, 9),
            datetime.date(2026, 10, 13),
            datetime.date(2026, 10, 15),
            datetime.date(2026, 10, 16),
        ]
        self.assertEqual(fechas_sync, esperadas)

        # 2. Justificación diferida sobre otro período con fin de semana y feriado:
        # Vie 23/10 al Mar 27/10 (Sáb 24, Dom 25 y Lun 26 Feriado deben omitirse)
        procesar_justificacion_rango(
            docente=docente,
            fecha_desde=datetime.date(2026, 10, 23),
            fecha_hasta=datetime.date(2026, 10, 27),
            nueva_marca="LIC",
            tipo_licencia=self.tipo_tit_matrimonio,
            cargo=cargo,
            usuario=self.user,
        )
        fechas_justif = sorted(
            RegistroAsistencia.objects.filter(
                docente=docente,
                cargo=cargo,
                fecha__range=[
                    datetime.date(2026, 10, 23),
                    datetime.date(2026, 10, 27),
                ],
            ).values_list("fecha", flat=True)
        )
        self.assertEqual(
            fechas_justif,
            [datetime.date(2026, 10, 23), datetime.date(2026, 10, 27)],
        )
