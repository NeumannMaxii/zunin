"""
Pruebas unitarias para el Ticket 19.3:
Numerador Correlativo Automático Anual de Disposiciones Internas.
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.forms import LicenciaOtorgadaForm
from apps.licencias.models import (
    LicenciaOtorgada,
    NumeradorDisposicion,
    RenglonPlanillaMensual,
    TipoLicencia,
)
from apps.licencias.services import (
    confirmar_correlativo_disposicion,
    extraer_numero_y_anio_disposicion,
    generar_planilla_mes,
    obtener_max_disposicion_existente,
    obtener_siguiente_correlativo_disposicion,
    procesar_justificacion_rango,
    sincronizar_licencia_con_asistencia,
    verificar_disposicion_duplicada,
)
from apps.personal.models import CargoCatalogo, CargoDocente, Docente

User = get_user_model()


class Ticket193CorrelativoDisposicionesTest(TestCase):
    """
    Suite de pruebas para validación y correlatividad de Disposiciones Internas.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="bedel1",
            password="password123",
            is_staff=True,
        )
        self.docente = Docente.objects.create(
            nombre="María",
            apellido="Zunin",
            dni="28444555",
            activo=True,
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="PROF-19-3",
            descripcion="Profesor",
            activo=True,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2023, 3, 1),
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            activo=True,
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="322-A",
            articulo="322",
            descripcion="Enfermedad Común",
            categoria="LICENCIA",
            situacion_revista_aplicable="TIT,INT,SUP",
            forma_goce="100%",
            duracion_maxima=30,
            cuadro_mensual="IL-01",
            activo=True,
        )

    def test_extraer_numero_y_anio_disposicion(self):
        """Valida parsing de múltiples formatos de Disposición Interna."""
        self.assertEqual(
            extraer_numero_y_anio_disposicion("014/2026"),
            (14, 2026),
        )
        self.assertEqual(
            extraer_numero_y_anio_disposicion("Disp. 055/26"),
            (55, 2026),
        )
        self.assertEqual(
            extraer_numero_y_anio_disposicion("Disposición 001/2027"),
            (1, 2027),
        )
        self.assertEqual(
            extraer_numero_y_anio_disposicion("Disp. Interna 150/2026"),
            (150, 2026),
        )
        # Resoluciones externas son ignoradas
        self.assertEqual(
            extraer_numero_y_anio_disposicion("Res. 1450/2026"),
            (None, None),
        )
        self.assertEqual(
            extraer_numero_y_anio_disposicion("Resolución Ministerial 2026"),
            (None, None),
        )

    def test_obtener_siguiente_correlativo_y_reserva(self):
        """Valida generación correlativa NNN/AAAA y reserva atómica."""
        siguiente = obtener_siguiente_correlativo_disposicion(
            anio=2026, reservar=False
        )
        self.assertEqual(siguiente, "001/2026")

        # Reservar asigna 001/2026
        reservado = obtener_siguiente_correlativo_disposicion(
            anio=2026, reservar=True, usuario=self.user
        )
        self.assertEqual(reservado, "001/2026")

        num_obj = NumeradorDisposicion.objects.get(anio=2026)
        self.assertEqual(num_obj.ultimo_numero, 1)

        # Siguiente ahora es 002/2026
        siguiente_2 = obtener_siguiente_correlativo_disposicion(
            anio=2026, reservar=False
        )
        self.assertEqual(siguiente_2, "002/2026")

    def test_transicion_anual_independiente(self):
        """Valida que el contador reinicia en 001 para cada nuevo año calendario."""
        confirmar_correlativo_disposicion(
            numero_str_o_int=14, anio=2026, usuario=self.user
        )
        self.assertEqual(
            obtener_siguiente_correlativo_disposicion(anio=2026),
            "015/2026",
        )
        # Año 2027 empieza en 001/2027
        self.assertEqual(
            obtener_siguiente_correlativo_disposicion(anio=2027),
            "001/2027",
        )

    def test_sincronizacion_con_registros_existentes(self):
        """
        Si existen registros previos con números mayores (ej. 014/2026),
        el numerador se auto-sincroniza con el máximo existente.
        """
        RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            cuadro="IL-01",
            mes=3,
            anio=2026,
            oficina="1452",
            desde=datetime.date(2026, 3, 2),
            hasta=datetime.date(2026, 3, 4),
            horas_afectadas=12,
            marca_origen="LIC",
            tipo_instrumento="DISPOSICION",
            numero_instrumento="014/2026",
            creado_por=self.user,
        )

        max_num = obtener_max_disposicion_existente(2026)
        self.assertEqual(max_num, 14)

        sig = obtener_siguiente_correlativo_disposicion(anio=2026)
        self.assertEqual(sig, "015/2026")

    def test_verificar_disposicion_duplicada(self):
        """Detecta duplicaciones manuales en el mismo año."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 4, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 5),
            estado="APROBADA",
            tipo_instrumento="DISPOSICION",
            instrumento_legal="015/2026",
            creado_por=self.user,
        )

        # Consulta con variantes de formato
        dup1 = verificar_disposicion_duplicada("015/2026", anio=2026)
        self.assertTrue(dup1["duplicado"])
        self.assertIn("ya fue asignado", dup1["mensaje"])

        dup2 = verificar_disposicion_duplicada("Disp. 015/26", anio=2026)
        self.assertTrue(dup2["duplicado"])

        # Otro número está disponible
        dup3 = verificar_disposicion_duplicada("016/2026", anio=2026)
        self.assertFalse(dup3["duplicado"])

        # Mismo número en otro año está disponible
        dup4 = verificar_disposicion_duplicada("015/2027", anio=2027)
        self.assertFalse(dup4["duplicado"])

    def test_api_siguiente_disposicion(self):
        """Prueba endpoint GET /api/licencias/siguiente-disposicion/."""
        self.client.force_login(self.user)
        confirmar_correlativo_disposicion(5, anio=2026, usuario=self.user)

        url = reverse("licencias:api_siguiente_disposicion")
        response = self.client.get(f"{url}?anio=2026")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["siguiente"], "006/2026")
        self.assertEqual(data["anio"], 2026)

    def test_api_validar_disposicion(self):
        """Prueba endpoint GET /api/licencias/validar-disposicion/."""
        self.client.force_login(self.user)
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 5, 1),
            fecha_hasta_prevista=datetime.date(2026, 5, 3),
            estado="APROBADA",
            tipo_instrumento="DISPOSICION",
            instrumento_legal="020/2026",
            creado_por=self.user,
        )

        url = reverse("licencias:api_validar_disposicion")
        # Duplicado
        resp_dup = self.client.get(f"{url}?numero=020/2026&anio=2026")
        self.assertEqual(resp_dup.status_code, 200)
        data_dup = resp_dup.json()
        self.assertTrue(data_dup["duplicado"])

        # Disponible
        resp_ok = self.client.get(f"{url}?numero=021/2026&anio=2026")
        self.assertEqual(resp_ok.status_code, 200)
        data_ok = resp_ok.json()
        self.assertFalse(data_ok["duplicado"])

    def test_formulario_licencia_rechaza_duplicado(self):
        """LicenciaOtorgadaForm rechaza números de disposición duplicados."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 6, 1),
            fecha_hasta_prevista=datetime.date(2026, 6, 2),
            estado="APROBADA",
            tipo_instrumento="DISPOSICION",
            instrumento_legal="030/2026",
            creado_por=self.user,
        )

        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo.pk,
            "tipo_licencia": self.tipo_lic.pk,
            "fecha_desde": "2026-06-10",
            "fecha_hasta_prevista": "2026-06-11",
            "estado": "SOLICITADA",
            "porcentaje_goce": "100",
            "tipo_instrumento": "DISPOSICION",
            "instrumento_legal": "030/2026",  # Duplicado
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("instrumento_legal", form.errors)

    def test_sincronizacion_licencia_auto_asigna_correlativo(self):
        """
        Al sincronizar una licencia con tipo_instrumento='DISPOSICION' y
        sin instrumento_legal provisto, se auto-asigna el correlativo y se persiste.
        """
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 7, 1),
            fecha_hasta_prevista=datetime.date(2026, 7, 1),
            estado="APROBADA",
            tipo_instrumento="DISPOSICION",
            instrumento_legal="",
            creado_por=self.user,
        )
        sincronizar_licencia_con_asistencia(lic, usuario=self.user)
        lic.refresh_from_db()
        self.assertTrue(lic.instrumento_legal.endswith("/2026"))
        self.assertRegex(lic.instrumento_legal, r"^\d{3}/2026$")

    def test_procesar_justificacion_rango_confirma_disposicion(self):
        """
        La justificación diferida con número provisto confirma el correlativo
        en el numerador institucional.
        """
        reg_asist = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=datetime.date(2026, 8, 3),  # Lunes
            estado="AUSENTE",
            marca_diaria="I",
        )

        procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=datetime.date(2026, 8, 3),
            fecha_hasta=datetime.date(2026, 8, 3),
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            numero_disposicion="045/2026",
            tipo_instrumento="DISPOSICION",
            usuario=self.user,
        )

        reg_asist.refresh_from_db()
        self.assertEqual(reg_asist.numero_disposicion, "045/2026")
        num_obj = NumeradorDisposicion.objects.get(anio=2026)
        self.assertEqual(num_obj.ultimo_numero, 45)

    def test_generar_planilla_mes_actualiza_numerador(self):
        """
        La generación mensual consolida renglones y actualiza el último número
        en NumeradorDisposicion.
        """
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=datetime.date(2026, 9, 1),
            estado="AUSENTE",
            marca_diaria="I",
        )

        renglones = generar_planilla_mes(mes=9, anio=2026, usuario=self.user)
        self.assertTrue(len(renglones) > 0)

        num_obj = NumeradorDisposicion.objects.get(anio=2026)
        self.assertTrue(num_obj.ultimo_numero >= 1)
