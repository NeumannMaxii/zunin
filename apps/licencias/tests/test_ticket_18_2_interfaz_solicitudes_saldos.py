"""
Pruebas automatizadas para el Ticket 18.2: Interfaz de Usuario para
Solicitudes y Vistas de Saldo.

Objetivo:
Proveer vistas para registro de licencias y visualización de saldos disponibles.

Especificaciones Técnicas:
Formulario adaptativo filtrado por régimen y panel informativo de saldos
del docente.

Criterio de Aceptación:
El formulario valida en tiempo real y muestra los días restantes antes
de confirmar.
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.services import obtener_resumen_saldos_docente
from apps.licencias.validaciones import REGIMEN_SUP, REGIMEN_TIT

from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)

User = get_user_model()


class Ticket182InterfazSolicitudesSaldosTests(TestCase):
    """
    Suite de validación integral para el Ticket 18.2:
    - Formulario adaptativo de licencias filtrado por régimen.
    - Panel informativo de saldos del docente.
    - Validación en tiempo real y cálculo de días restantes.
    - Endpoints API y vistas institucionales de saldo.
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(
            username="admin_test_18_2",
            password="test_password_18_2",
            email="admin182@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)

        # 1. Estructura Académica
        self.carrera = Carrera.objects.create(
            codigo="TSDS-182",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.espacio_1 = EspacioCurricular.objects.create(
            codigo="BD-182",
            nombre="Bases de Datos",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.espacio_2 = EspacioCurricular.objects.create(
            codigo="PR-182",
            nombre="Programación Avanzada",
            carrera=self.carrera,
            anio=2,
            turno="MANANA",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-PROF-182",
            descripcion="Profesor",
            activo=True,
        )

        # 2. Docente con antigüedad consolidada
        self.docente = Docente.objects.create(
            nombre="Mariana",
            apellido="Ríos",
            dni="32444555",
            activo=True,
        )

        # 3. Cargos del Docente: Uno Titular y uno Suplente
        self.cargo_tit = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio_1,
            situacion_revista=REGIMEN_TIT,
            fecha_alta=datetime.date(2021, 3, 1),
            activo=True,
        )
        self.cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio_2,
            situacion_revista=REGIMEN_SUP,
            fecha_alta=datetime.date(2026, 2, 1),  # Suplente reciente
            activo=True,
        )

        # 4. Catálogo de Tipos de Licencia
        self.tipo_tit_308 = TipoLicencia.objects.create(
            codigo="TIT-ORD-308",
            articulo="308",
            descripcion="Afecciones comunes titular",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable="TIT",
            duracion_maxima=45,
            periodo_tope="Año calendario",
            activo=True,
        )
        self.tipo_sup_308 = TipoLicencia.objects.create(
            codigo="SUP-ORD-308",
            articulo="308",
            descripcion="Afecciones comunes suplente",
            regimen=REGIMEN_SUP,
            situacion_revista_aplicable="SUP",
            duracion_maxima=30,
            periodo_tope="Año calendario",
            activo=True,
        )

        self.tipo_examen = TipoLicencia.objects.create(
            codigo="GEN-EXAM-344",
            articulo="344",
            descripcion="Examen o mesa examinadora",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable="TIT,INT,SUP",
            duracion_maxima=20,
            periodo_tope="Año calendario",
            activo=True,
        )

    def test_01_api_docente_cargos_retorna_cargos_activos(self):
        """
        Verifica que /api/licencias/docente-cargos/ retorne los cargos
        activos del docente para alimentar el selector dinámico del formulario.
        """
        url = reverse("licencias:docente_cargos")
        response = self.client.get(f"{url}?docente={self.docente.pk}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        cargos = data["cargos"]
        self.assertEqual(len(cargos), 2)

        cargos_ids = [c["id"] for c in cargos]
        self.assertIn(self.cargo_tit.pk, cargos_ids)
        self.assertIn(self.cargo_sup.pk, cargos_ids)

        c_tit = next(c for c in cargos if c["id"] == self.cargo_tit.pk)
        self.assertEqual(c_tit["situacion_revista"], REGIMEN_TIT)
        self.assertIn("Titular", c_tit["situacion_revista_display"])

    def test_02_api_docente_cargos_valida_parametro_requerido(self):
        """
        Verifica que /api/licencias/docente-cargos/ retorne error 400 si
        falta el parámetro docente o es inválido.
        """
        url = reverse("licencias:docente_cargos")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_03_api_tipos_por_regimen_filtra_correctamente(self):
        """
        Verifica que /api/licencias/tipos-por-regimen/ devuelva únicamente
        los tipos compatibles con el régimen especificado.
        """
        url = reverse("licencias:tipos_por_regimen")

        # Caso Régimen TIT
        res_tit = self.client.get(f"{url}?regimen=TIT")
        self.assertEqual(res_tit.status_code, 200)
        codigos_tit = [t["codigo"] for t in res_tit.json()["tipos"]]
        self.assertIn("TIT-ORD-308", codigos_tit)
        self.assertIn("GEN-EXAM-344", codigos_tit)
        self.assertNotIn("SUP-ORD-308", codigos_tit)

        # Caso Régimen SUP
        res_sup = self.client.get(f"{url}?regimen=SUP")
        self.assertEqual(res_sup.status_code, 200)
        codigos_sup = [t["codigo"] for t in res_sup.json()["tipos"]]
        self.assertIn("SUP-ORD-308", codigos_sup)
        self.assertIn("GEN-EXAM-344", codigos_sup)
        self.assertNotIn("TIT-ORD-308", codigos_sup)

    def test_04_api_tipos_por_regimen_resuelve_desde_cargo(self):
        """
        Verifica que /api/licencias/tipos-por-regimen/?cargo=<id>
        resuelva automáticamente la situación de revista del cargo.
        """
        url = reverse("licencias:tipos_por_regimen")
        res = self.client.get(f"{url}?cargo={self.cargo_sup.pk}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["regimen"], REGIMEN_SUP)
        codigos = [t["codigo"] for t in data["tipos"]]
        self.assertIn("SUP-ORD-308", codigos)
        self.assertNotIn("TIT-ORD-308", codigos)

    def test_05_api_validar_saldos_incluye_dias_restantes_en_tiempo_real(self):
        """
        Criterio de Aceptación:
        El formulario valida en tiempo real y muestra los días restantes antes
        de confirmar la solicitud.
        """
        # Docente consume previamente 10 días de examen en 2026
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_examen,
            fecha_desde=datetime.date(2026, 4, 1),
            fecha_hasta_prevista=datetime.date(2026, 4, 10),  # 10 días
            estado="OTORGADA",
            porcentaje_goce=100,
            sincronizar_asistencia=False,
        )

        # Solicita 5 días adicionales (del 15 al 19 de mayo 2026)
        # Tope total = 20 días. Consumidos previos = 10 días.
        # Saldo disponible previo = 10 días. Días solicitados = 5 días.
        # Días restantes antes de confirmar = 20 - 15 = 5 días.
        url = reverse("licencias:validar_saldos")
        response = self.client.get(
            f"{url}?tipo_licencia={self.tipo_examen.pk}"
            f"&docente={self.docente.pk}"
            f"&cargo={self.cargo_tit.pk}"
            f"&fecha_desde=2026-05-15&fecha_hasta=2026-05-19"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "success")
        self.assertTrue(data["valido"])
        self.assertFalse(data["supera_tope"])
        self.assertEqual(data["tope_maximo"], 20)
        self.assertEqual(data["dias_consumidos"], 10)
        self.assertEqual(data["saldo_disponible"], 10)
        self.assertEqual(data["dias_solicitados"], 5)
        self.assertEqual(data["total_acumulado"], 15)
        # Criterio de Aceptación Clave: dias_restantes tras aprobar la solicitud
        self.assertEqual(data["dias_restantes"], 5)

    def test_06_api_validar_saldos_detecta_exceso_de_tope_y_bloquea(self):
        """
        Verifica que si la solicitud excede el tope, retorne supera_tope=True,
        dias_restantes=0 y mensaje de bloqueo.
        """
        # Intenta solicitar 25 días teniendo tope de 20
        url = reverse("licencias:validar_saldos")
        response = self.client.get(
            f"{url}?tipo_licencia={self.tipo_examen.pk}"
            f"&docente={self.docente.pk}"
            f"&cargo={self.cargo_tit.pk}"
            f"&fecha_desde=2026-06-01&fecha_hasta=2026-06-25"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "success")
        self.assertFalse(data["valido"])
        self.assertTrue(data["supera_tope"])
        self.assertEqual(data["dias_restantes"], 0)
        self.assertTrue(any(w in data["mensaje"].lower() for w in ["supera", "excede"]))

    def test_07_servicio_obtener_resumen_saldos_docente(self):
        """
        Verifica que obtener_resumen_saldos_docente consolide adecuadamente
        todos los saldos, causales y métricas del docente para el año.
        """
        # Registrar una licencia previa de 5 días
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_308,
            fecha_desde=datetime.date(2026, 3, 1),
            fecha_hasta_prevista=datetime.date(2026, 3, 5),
            estado="OTORGADA",
            sincronizar_asistencia=False,
        )

        resumen = obtener_resumen_saldos_docente(self.docente, anio=2026)
        self.assertIsNotNone(resumen)
        self.assertEqual(resumen["docente"].pk, self.docente.pk)
        self.assertEqual(resumen["anio"], 2026)
        self.assertGreater(resumen["antiguedad_meses"], 12)
        self.assertEqual(resumen["total_licencias_otorgadas"], 1)

        causales = {c["codigo"]: c for c in resumen["resumen_causales"]}
        self.assertIn("TIT-ORD-308", causales)
        self.assertEqual(causales["TIT-ORD-308"]["dias_consumidos"], 5)
        self.assertEqual(causales["TIT-ORD-308"]["tope_maximo"], 45)
        self.assertEqual(causales["TIT-ORD-308"]["saldo_disponible"], 40)
        self.assertEqual(causales["TIT-ORD-308"]["alerta_nivel"], "success")

    def test_08_vista_docente_saldos_renderiza_correctamente(self):
        """
        Verifica la vista institucional /licencias/saldos/ y con parámetro
        /licencias/saldos/<docente_id>/.
        """
        # 1. Vista general sin ID (preselecciona el primer docente)
        url_general = reverse("licencias:docente_saldos")
        resp_gen = self.client.get(url_general)
        self.assertEqual(resp_gen.status_code, 200)
        self.assertTemplateUsed(resp_gen, "licencias/docente_saldos.html")
        self.assertContains(resp_gen, "Panel Informativo de Saldos de Licencias")
        self.assertContains(resp_gen, self.docente.apellido)

        # 2. Vista específica por docente
        url_detalle = reverse(
            "licencias:docente_saldos_detalle",
            kwargs={"docente_id": self.docente.pk},
        )
        resp_det = self.client.get(url_detalle)
        self.assertEqual(resp_det.status_code, 200)
        self.assertContains(resp_det, self.docente.nombre)
        self.assertContains(resp_det, "TIT-ORD-308")

    def test_09_formulario_solicitud_soporta_preseleccion_por_query_params(
        self,
    ):
        """
        Verifica que al acceder a /licencias/solicitudes/nueva/?docente=<id>&cargo=<id>
        el formulario inicialice los campos preseleccionados.
        """
        url = reverse("licencias:licenciaotorgada_create")
        query = (
            f"docente={self.docente.pk}"
            f"&cargo={self.cargo_tit.pk}"
            f"&tipo_licencia={self.tipo_tit_308.pk}"
        )
        response = self.client.get(f"{url}?{query}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "licencias/licenciaotorgada_form.html")
        form = response.context["form"]
        self.assertEqual(str(form.initial["docente"]), str(self.docente.pk))
        self.assertEqual(str(form.initial["cargo"]), str(self.cargo_tit.pk))
        self.assertEqual(str(form.initial["tipo_licencia"]), str(self.tipo_tit_308.pk))

    def test_10_listado_licencias_incluye_enlace_a_panel_de_saldos(self):
        """
        Verifica que el listado de solicitudes otorgadas incluya el botón
        de navegación 'Ver Saldos por Docente'.
        """
        url = reverse("licencias:licenciaotorgada_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ver Saldos por Docente")
        self.assertContains(response, reverse("licencias:docente_saldos"))
