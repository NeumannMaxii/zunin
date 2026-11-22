"""
Pruebas automatizadas para el Ticket 19.4: Control de Superposición y Colisión
de Licencias Activas (apps.licencias).

Reglas de Negocio Verificadas:
1. Superposición Temporal: D1 <= H2 y H1 >= D2.
2. Alcance Institucional vs. Cargo Específico:
   - Si una licencia tiene cargo=None (institucional), colisiona con cualquier
     licencia activa del docente en ese rango temporal.
   - Si ambas tienen cargo asignado:
     * Mismo cargo: colisión directa.
     * Distintos cargos: colisiona si alguna de las dos es médica / reposo / salud.
     * Distintos cargos: se permite la coexistencia si ambas son estrictamente
       no médicas.
3. Estados Activos: SOLICITADA, OTORGADA, APROBADA (FINALIZADA). Se excluyen
   CANCELADA, ANULADA, RECHAZADA.
4. Exclusión de la propia instancia al editar.
5. Mensajes de error detallados con fechas DD/MM/AAAA, código, solicitud y cargo.
6. Integración con LicenciaOtorgada, formularios y endpoint API.
"""

import datetime
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.licencias.forms import JustificacionDiferidaForm, LicenciaOtorgadaForm
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.validaciones import (
    buscar_licencias_solapadas,
    es_licencia_medica_o_reposo,
    validar_solapamiento_licencias,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class Ticket194ControlSuperposicionTests(TestCase):
    """
    Suite de pruebas unitarias y de integración para Ticket 19.4.
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Marcelo",
            apellido="Quiroga",
            dni="29888777",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-194",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.materia_a = EspacioCurricular.objects.create(
            codigo="BD-194",
            nombre="Bases de Datos Relacionales",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.materia_b = EspacioCurricular.objects.create(
            codigo="PRG-194",
            nombre="Programación Backend",
            carrera=self.carrera,
            anio=2,
            turno="MANANA",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-194",
            descripcion="Profesor de Nivel Superior",
            activo=True,
        )

        self.cargo_a = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.materia_a,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2024, 1, 1),
            activo=True,
        )

        self.cargo_b = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.materia_b,
            situacion_revista="INT",
            fecha_alta=datetime.date(2024, 1, 1),
            activo=True,
        )

        # Tipos de Licencias
        # Médica / Salud
        self.tipo_medica = TipoLicencia.objects.create(
            codigo="MED-340A-194",
            articulo="340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            duracion_maxima=30,
            tope_anual=30,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen="TIT",
            situacion_revista_aplicable="TIT,INT,SUP",
            activo=True,
        )
        # No Médica (Exámenes / Perfeccionamiento)
        self.tipo_examen = TipoLicencia.objects.create(
            codigo="EXAM-345-194",
            articulo="345",
            descripcion="Exámenes o Perfeccionamiento Docente",
            duracion_maxima=15,
            tope_anual=15,
            goce_haberes=True,
            cuadro_mensual="IL-02",
            regimen="TIT",
            situacion_revista_aplicable="TIT,INT,SUP",
            activo=True,
        )
        # No Médica (Razones Particulares)
        self.tipo_particular = TipoLicencia.objects.create(
            codigo="PART-346-194",
            articulo="346",
            descripcion="Razones Particulares",
            duracion_maxima=30,
            tope_anual=30,
            goce_haberes=False,
            cuadro_mensual="IL-02",
            regimen="TIT",
            situacion_revista_aplicable="TIT,INT,SUP",
            activo=True,
        )

        self.desde_base = datetime.date(2026, 11, 10)
        self.hasta_base = datetime.date(2026, 11, 20)

    # -------------------------------------------------------------------------
    # 1. Función Auxiliar: Identificación de Naturaleza Médica / Reposo
    # -------------------------------------------------------------------------

    def test_es_licencia_medica_o_reposo_clasificacion(self):
        """Verifica detección de licencias médicas, salud o reposo."""
        self.assertTrue(es_licencia_medica_o_reposo(self.tipo_medica))
        self.assertFalse(es_licencia_medica_o_reposo(self.tipo_examen))
        self.assertFalse(es_licencia_medica_o_reposo(self.tipo_particular))
        self.assertFalse(es_licencia_medica_o_reposo(None))

        # Creación con código LT o Art 308
        tipo_lt = TipoLicencia(codigo="LIC-LT", descripcion="Largo Tratamiento")
        self.assertTrue(es_licencia_medica_o_reposo(tipo_lt))

        tipo_308 = TipoLicencia(codigo="LIC-308", articulo="308")
        self.assertTrue(es_licencia_medica_o_reposo(tipo_308))

        tipo_341 = TipoLicencia(
            codigo="LIC-341", articulo="341", descripcion="Maternidad"
        )
        self.assertTrue(es_licencia_medica_o_reposo(tipo_341))

    # -------------------------------------------------------------------------
    # 2. Superposición en el Mismo Cargo
    # -------------------------------------------------------------------------

    def test_mismo_cargo_superposicion_bloquea_con_mensaje_detallado(self):
        """Bloquea solicitudes en el mismo cargo detallando fechas y solicitud."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=datetime.date(2026, 11, 15),
                fecha_hasta=datetime.date(2026, 11, 25),
                docente=self.docente,
                tipo_licencia=self.tipo_particular,
            )

        err_msg = str(ctx.exception)
        self.assertIn("ya posee otra licencia activa", err_msg)
        self.assertIn("10/11/2026", err_msg)
        self.assertIn("20/11/2026", err_msg)
        self.assertIn(f"Solicitud #{lic.pk}", err_msg)
        self.assertIn(self.tipo_particular.codigo, err_msg)

    # -------------------------------------------------------------------------
    # 3. Alcance Institucional vs. Cargo Específico
    # -------------------------------------------------------------------------

    def test_licencia_institucional_existente_bloquea_cargo_especifico(self):
        """
        Una licencia previa con cargo=None (institucional) bloquea cualquier
        solicitud posterior en cargos específicos del docente en esas fechas.
        """
        lic_inst = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=None,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=datetime.date(2026, 11, 12),
                fecha_hasta=datetime.date(2026, 11, 18),
                docente=self.docente,
                tipo_licencia=self.tipo_particular,
            )

        err_msg = str(ctx.exception)
        self.assertIn("Alcance Institucional", err_msg)
        self.assertIn("Afecta a todos los cargos", err_msg)
        self.assertIn(f"Solicitud #{lic_inst.pk}", err_msg)
        self.assertIn("10/11/2026", err_msg)

    def test_cargo_especifico_existente_bloquea_nueva_licencia_institucional(self):
        """
        Si ya existe una licencia activa en un cargo, se bloquea la solicitud
        de una licencia institucional (cargo=None) para ese docente en el período.
        """
        lic_cargo = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="APROBADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=None,
                fecha_desde=datetime.date(2026, 11, 15),
                fecha_hasta=datetime.date(2026, 11, 25),
                docente=self.docente,
                tipo_licencia=self.tipo_particular,
            )

        err_msg = str(ctx.exception)
        self.assertIn(
            "No se puede otorgar una licencia de Alcance Institucional", err_msg
        )
        self.assertIn("ya posee otra licencia activa en el cargo", err_msg)
        self.assertIn(f"Solicitud #{lic_cargo.pk}", err_msg)

    def test_dos_licencias_institucionales_colisionan(self):
        """Dos solicitudes institucionales (cargo=None) colisionan si solapan."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=None,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="SOLICITADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=None,
                fecha_desde=datetime.date(2026, 11, 18),
                fecha_hasta=datetime.date(2026, 11, 22),
                docente=self.docente,
                tipo_licencia=self.tipo_particular,
            )
        self.assertIn("Alcance Institucional", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 4. Distintos Cargos: Regla de Licencias Médicas vs. No Médicas
    # -------------------------------------------------------------------------

    def test_distintos_cargos_licencia_medica_activa_bloquea_otra_licencia(self):
        """
        Una licencia médica activa en Cargo A inhabilita y colisiona con una
        solicitud en Cargo B durante el mismo período.
        """
        lic_med = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_medica,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=self.cargo_b,
                fecha_desde=datetime.date(2026, 11, 12),
                fecha_hasta=datetime.date(2026, 11, 18),
                docente=self.docente,
                tipo_licencia=self.tipo_examen,
            )

        err_msg = str(ctx.exception)
        self.assertIn("Conflicto por reposo de salud", err_msg)
        self.assertIn(f"Solicitud #{lic_med.pk}", err_msg)
        self.assertIn("10/11/2026 al 20/11/2026", err_msg)

    def test_distintos_cargos_solicitud_medica_colisiona_con_no_medica_activa(self):
        """
        Una solicitud médica en Cargo B colisiona con una licencia no médica
        preexistente en Cargo A (el reposo médico es global para la persona).
        """
        lic_exam = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_examen,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=self.cargo_b,
                fecha_desde=datetime.date(2026, 11, 12),
                fecha_hasta=datetime.date(2026, 11, 18),
                docente=self.docente,
                tipo_licencia=self.tipo_medica,
            )

        err_msg = str(ctx.exception)
        self.assertIn("Conflicto por reposo de salud", err_msg)
        self.assertIn(f"Solicitud #{lic_exam.pk}", err_msg)

    def test_distintos_cargos_ambas_no_medicas_permite_coexistencia(self):
        """
        Dos licencias estrictamente no médicas (ej. Exámenes en Cargo A y
        Razones Particulares en Cargo B) pueden coexistir sin colisionar.
        """
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_examen,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        try:
            valido = validar_solapamiento_licencias(
                cargo=self.cargo_b,
                fecha_desde=datetime.date(2026, 11, 12),
                fecha_hasta=datetime.date(2026, 11, 18),
                docente=self.docente,
                tipo_licencia=self.tipo_particular,
            )
            self.assertTrue(valido)
        except ValidationError:
            self.fail(
                "Dos licencias no médicas en distintos cargos deben poder coexistir."
            )

    # -------------------------------------------------------------------------
    # 5. Estados Inactivos No Generan Colisión
    # -------------------------------------------------------------------------

    def test_estados_inactivos_no_colisionan(self):
        """
        Licencias canceladas, anuladas o rechazadas no bloquean solicitudes.
        """
        for est in ["CANCELADA", "ANULADA", "RECHAZADA"]:
            lic = LicenciaOtorgada.objects.create(
                docente=self.docente,
                cargo=self.cargo_a,
                tipo_licencia=self.tipo_medica,
                fecha_desde=self.desde_base,
                fecha_hasta_prevista=self.hasta_base,
                estado=est,
            )
            # Debe permitir nueva solicitud sin error
            try:
                valido = validar_solapamiento_licencias(
                    cargo=self.cargo_a,
                    fecha_desde=self.desde_base,
                    fecha_hasta=self.hasta_base,
                    docente=self.docente,
                    tipo_licencia=self.tipo_medica,
                )
                self.assertTrue(valido)
            except ValidationError:
                self.fail(f"Estado '{est}' no debería bloquear nuevas solicitudes.")
            lic.delete()

    # -------------------------------------------------------------------------
    # 6. Exclusión de Instancia al Editar
    # -------------------------------------------------------------------------

    def test_edicion_misma_instancia_no_autocolisiona(self):
        """Al modificar una licencia existente, no colisiona consigo misma."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_medica,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )
        lic.observaciones = "Ampliación de certificado"
        try:
            lic.clean()
            lic.save()
        except ValidationError:
            self.fail("La edición de la misma instancia no debe autocolisionar.")

    # -------------------------------------------------------------------------
    # 7. Integración con Formularios
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_form_valida_institucional_y_cargos(self):
        """LicenciaOtorgadaForm valida colisiones institucionales y médicas."""
        # Creamos una licencia médica activa en Cargo A
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_medica,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        # Intento de cargar en Cargo B
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_b.pk,
            "tipo_licencia": self.tipo_examen.pk,
            "fecha_desde": "2026-11-12",
            "fecha_hasta_prevista": "2026-11-18",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_desde", form.errors)
        self.assertIn("Conflicto por reposo de salud", str(form.errors["fecha_desde"]))

        # Intento de cargar una Institucional (cargo vacío)
        form_data_inst = {
            "docente": self.docente.pk,
            "cargo": "",
            "tipo_licencia": self.tipo_particular.pk,
            "fecha_desde": "2026-11-12",
            "fecha_hasta_prevista": "2026-11-18",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form_inst = LicenciaOtorgadaForm(data=form_data_inst)
        self.assertFalse(form_inst.is_valid())
        self.assertIn("fecha_desde", form_inst.errors)
        self.assertIn("Alcance Institucional", str(form_inst.errors["fecha_desde"]))

    def test_justificacion_diferida_form_valida_alcance_institucional(self):
        """JustificacionDiferidaForm valida colisiones sin cargo asignado."""
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=None,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_a.pk,
            "tipo_licencia": self.tipo_particular.pk,
            "fecha_desde": "2026-11-12",
            "fecha_hasta": "2026-11-18",
            "nueva_marca": "LIC",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_desde", form.errors)
        self.assertIn("Alcance Institucional", str(form.errors["fecha_desde"]))

    # -------------------------------------------------------------------------
    # 8. Endpoint API: Validar Solapamiento
    # -------------------------------------------------------------------------

    def test_api_validar_solapamiento_soporta_solicitud_institucional_sin_cargo(self):
        """El endpoint API acepta cargo vacío si se especifica docente_id."""
        url = reverse("licencias:validar_solapamiento")
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_particular,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        response = self.client.get(
            url,
            {
                "docente": self.docente.pk,
                "cargo": "",
                "fecha_desde": "2026-11-12",
                "fecha_hasta": "2026-11-18",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["valido"])
        self.assertTrue(data["hay_solapamiento"])
        self.assertGreaterEqual(data["cantidad_solapadas"], 1)
        self.assertIn("Alcance Institucional", data["mensaje"])

        primera = data["licencias_solapadas"][0]
        self.assertIn("es_institucional", primera)
        self.assertIn("es_medica", primera)
        self.assertIn("cargo", primera)

    def test_api_validar_solapamiento_detecta_conflicto_medico_multicargo(self):
        """El endpoint API reporta colisión médica entre distintos cargos."""
        url = reverse("licencias:validar_solapamiento")
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_medica,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )

        response = self.client.get(
            url,
            {
                "docente": self.docente.pk,
                "cargo": self.cargo_b.pk,
                "tipo_licencia": self.tipo_examen.pk,
                "fecha_desde": "2026-11-12",
                "fecha_hasta": "2026-11-18",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valido"])
        self.assertTrue(data["hay_solapamiento"])
        self.assertIn("Conflicto por reposo de salud", data["mensaje"])

    def test_buscar_licencias_solapadas_directo(self):
        """Verifica la invocación directa del helper buscar_licencias_solapadas."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_medica,
            fecha_desde=self.desde_base,
            fecha_hasta_prevista=self.hasta_base,
            estado="OTORGADA",
        )
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_b,
            fecha_desde=self.desde_base,
            fecha_hasta=self.hasta_base,
            docente=self.docente,
            tipo_licencia=self.tipo_examen,
        )
        self.assertEqual(solapadas.count(), 1)
        self.assertEqual(solapadas.first().pk, lic.pk)
