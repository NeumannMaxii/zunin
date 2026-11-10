"""
Pruebas automatizadas para el Ticket 17.3: Control de Solapamientos.

Objetivo:
Impedir superposición de licencias activas sobre el mismo cargo y fecha.

Especificaciones Técnicas:
Validar rangos de fechas (fecha_desde a fecha_hasta) por cargo_id antes de guardar.

Criterio de Aceptación:
El sistema bloquea el registro si el cargo ya posee otra licencia activa en el período.
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
    ESTADOS_LICENCIA_ACTIVAS,
    ESTADOS_LICENCIA_INACTIVAS,
    REGIMEN_INT,
    REGIMEN_TIT,
    buscar_licencias_solapadas,
    validar_solapamiento_licencias,
    validar_solicitud_licencia,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class ControlSolapamientosTests(TestCase):
    """
    Suite de pruebas para control y bloqueo de solapamientos de licencias (Ticket 17.3).
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Laura",
            apellido="Gómez",
            dni="27555444",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-173",
            nombre="Desarrollo de Software",
            activo=True,
        )
        self.espacio_a = EspacioCurricular.objects.create(
            codigo="BD-173",
            nombre="Bases de Datos",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.espacio_b = EspacioCurricular.objects.create(
            codigo="PRG-173",
            nombre="Programación Avanzada",
            carrera=self.carrera,
            anio=2,
            turno="MANANA",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-173",
            descripcion="Profesor",
            activo=True,
        )

        # Cargo A del docente (con antigüedad suficiente para evitar bloqueos del 17.2)
        self.cargo_a = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio_a,
            situacion_revista=REGIMEN_TIT,
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )

        # Cargo B del docente (segundo cargo en la institución)
        self.cargo_b = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio_b,
            situacion_revista=REGIMEN_INT,
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )

        # Tipos de Licencias
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="TIT-ORD-173",
            articulo="308",
            descripcion="Licencia ordinaria titular",
            duracion_maxima=45,
            tope_anual=45,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable="TIT,INT,SUP",
            activo=True,
        )
        self.tipo_lic_b = TipoLicencia.objects.create(
            codigo="INT-ORD-173",
            articulo="330",
            descripcion="Licencia interinos",
            duracion_maxima=30,
            tope_anual=30,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_INT,
            situacion_revista_aplicable="INT,SUP",
            activo=True,
        )

        # Licencia activa base en Cargo A: 10 al 20 de octubre de 2026
        self.base_desde = datetime.date(2026, 10, 10)
        self.base_hasta = datetime.date(2026, 10, 20)
        self.licencia_activa = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_lic,
            fecha_solicitud=datetime.date(2026, 10, 1),
            fecha_desde=self.base_desde,
            fecha_hasta_prevista=self.base_hasta,
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
        )

    # -------------------------------------------------------------------------
    # Tests de Constantes y Configuración de Estados
    # -------------------------------------------------------------------------

    def test_constantes_estados_licencia(self):
        """Verifica la definición de estados activos e inactivos."""
        self.assertIn("OTORGADA", ESTADOS_LICENCIA_ACTIVAS)
        self.assertIn("SOLICITADA", ESTADOS_LICENCIA_ACTIVAS)
        self.assertIn("FINALIZADA", ESTADOS_LICENCIA_ACTIVAS)
        self.assertIn("CANCELADA", ESTADOS_LICENCIA_INACTIVAS)
        self.assertIn("RECHAZADA", ESTADOS_LICENCIA_INACTIVAS)

    # -------------------------------------------------------------------------
    # Criterio de Aceptación: Bloqueo de Licencia Superpuesta en el Mismo Cargo
    # -------------------------------------------------------------------------

    def test_criterio_aceptacion_bloqueo_licencia_superpuesta_mismo_cargo(self):
        """
        Criterio de Aceptación:
        El sistema bloquea el registro si el cargo ya posee otra licencia activa
        en el período (ej: 15 al 25 de octubre solapa con 10 al 20 de octubre).
        """
        nueva_desde = datetime.date(2026, 10, 15)
        nueva_hasta = datetime.date(2026, 10, 25)

        with self.assertRaises(ValidationError) as ctx:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=nueva_desde,
                fecha_hasta=nueva_hasta,
            )

        mensaje = str(ctx.exception)
        self.assertIn("ya posee otra licencia activa", mensaje)
        self.assertIn("10/10/2026", mensaje)
        self.assertIn("20/10/2026", mensaje)

    # -------------------------------------------------------------------------
    # Casos de Solapamiento Matemático de Intervalos
    # -------------------------------------------------------------------------

    def test_solapamiento_parcial_inicio(self):
        """Inicia antes y finaliza dentro del período existente (5 al 12 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 5),
            fecha_hasta=datetime.date(2026, 10, 12),
        )
        self.assertEqual(solapadas.count(), 1)
        self.assertEqual(solapadas.first().pk, self.licencia_activa.pk)

    def test_solapamiento_parcial_fin(self):
        """Inicia dentro y finaliza después del rango (18 al 25 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 18),
            fecha_hasta=datetime.date(2026, 10, 25),
        )
        self.assertEqual(solapadas.count(), 1)

    def test_solapamiento_total_interno(self):
        """Completamente contenida en el período existente (12 al 18 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 12),
            fecha_hasta=datetime.date(2026, 10, 18),
        )
        self.assertEqual(solapadas.count(), 1)

    def test_solapamiento_total_envolvente(self):
        """Abarca completamente el período existente (1 al 31 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 1),
            fecha_hasta=datetime.date(2026, 10, 31),
        )
        self.assertEqual(solapadas.count(), 1)

    def test_solapamiento_fechas_identicas(self):
        """Mismas fechas exactas de inicio y fin (10 al 20 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=self.base_desde,
            fecha_hasta=self.base_hasta,
        )
        self.assertEqual(solapadas.count(), 1)

    def test_solapamiento_limite_inicio(self):
        """Solapa exactamente en el día de inicio (5 al 10 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 5),
            fecha_hasta=datetime.date(2026, 10, 10),
        )
        self.assertEqual(solapadas.count(), 1)

    def test_solapamiento_limite_fin(self):
        """Solapa exactamente en el día de fin (20 al 25 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 20),
            fecha_hasta=datetime.date(2026, 10, 25),
        )
        self.assertEqual(solapadas.count(), 1)

    # -------------------------------------------------------------------------
    # Casos Sin Solapamiento (Períodos Adyacentes y Separados)
    # -------------------------------------------------------------------------

    def test_sin_solapamiento_periodo_anterior_adyacente(self):
        """Finaliza el día inmediatamente anterior (1 al 9 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 1),
            fecha_hasta=datetime.date(2026, 10, 9),
        )
        self.assertEqual(solapadas.count(), 0)

    def test_sin_solapamiento_periodo_posterior_adyacente(self):
        """Inicia el día inmediatamente posterior (21 al 30 de octubre)."""
        solapadas = buscar_licencias_solapadas(
            cargo=self.cargo_a,
            fecha_desde=datetime.date(2026, 10, 21),
            fecha_hasta=datetime.date(2026, 10, 30),
        )
        self.assertEqual(solapadas.count(), 0)

    # -------------------------------------------------------------------------
    # Independencia entre Cargos Distintos
    # -------------------------------------------------------------------------

    def test_mismo_docente_diferente_cargo_permite_solicitud(self):
        """
        Una licencia activa en el Cargo A NO impide solicitar licencia
        para el Cargo B en el mismo período.
        """
        try:
            validar_solapamiento_licencias(
                cargo=self.cargo_b,
                fecha_desde=self.base_desde,
                fecha_hasta=self.base_hasta,
            )
        except ValidationError:
            self.fail(
                "No debe bloquearse una licencia en Cargo B por existencia en Cargo A."
            )

    # -------------------------------------------------------------------------
    # Estados Inactivos No Bloquean
    # -------------------------------------------------------------------------

    def test_licencia_cancelada_no_bloquea_nuevo_registro(self):
        """Una licencia con estado CANCELADA en el mismo cargo y fecha no bloquea."""
        self.licencia_activa.estado = "CANCELADA"
        self.licencia_activa.save()

        try:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=self.base_desde,
                fecha_hasta=self.base_hasta,
            )
        except ValidationError:
            self.fail("Una licencia cancelada no debería bloquear nuevas solicitudes.")

    def test_licencia_rechazada_no_bloquea_nuevo_registro(self):
        """Una licencia con estado RECHAZADA en el mismo cargo y fecha no bloquea."""
        self.licencia_activa.estado = "RECHAZADA"
        self.licencia_activa.save()

        try:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=self.base_desde,
                fecha_hasta=self.base_hasta,
            )
        except ValidationError:
            self.fail("Una licencia rechazada no debería bloquear nuevas solicitudes.")

    # -------------------------------------------------------------------------
    # Edición de la Misma Licencia (excluir_id)
    # -------------------------------------------------------------------------

    def test_edicion_misma_licencia_no_se_autobloquea(self):
        """Guardar edición de licencia existente no genera colisión consigo misma."""
        try:
            validar_solapamiento_licencias(
                cargo=self.cargo_a,
                fecha_desde=self.base_desde,
                fecha_hasta=self.base_hasta,
                instancia_actual=self.licencia_activa,
            )
        except ValidationError:
            self.fail("La edición de la misma licencia no debe bloquearse a sí misma.")

    def test_licencia_otorgada_save_modificacion_existente(self):
        """Al llamar a save() en licencia existente, clean() no detecta colisión."""
        self.licencia_activa.observaciones = "Observación actualizada"
        try:
            self.licencia_activa.save()
        except ValidationError:
            self.fail("save() de la misma licencia no debería lanzar ValidationError.")

    # -------------------------------------------------------------------------
    # Integración con Modelo LicenciaOtorgada
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_model_save_bloquea_solapamiento(self):
        """El modelo LicenciaOtorgada valida solapamiento en clean()/save()."""
        nueva_lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 10, 15),
            fecha_hasta_prevista=datetime.date(2026, 10, 25),
            estado="OTORGADA",
        )
        with self.assertRaises(ValidationError) as ctx:
            nueva_lic.save()

        self.assertIn("ya posee otra licencia activa", str(ctx.exception))

    def test_licencia_otorgada_model_save_permite_fechas_libres(self):
        """El modelo LicenciaOtorgada permite guardar en períodos sin superposición."""
        nueva_lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 10, 22),
            fecha_hasta_prevista=datetime.date(2026, 10, 28),
            estado="OTORGADA",
        )
        try:
            nueva_lic.save()
            self.assertIsNotNone(nueva_lic.pk)
        except ValidationError:
            self.fail("No debería bloquearse una licencia en fechas libres.")

    # -------------------------------------------------------------------------
    # Integración con Formularios
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_form_bloquea_solapamiento(self):
        """LicenciaOtorgadaForm rechaza solicitudes superpuestas en el mismo cargo."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_a.pk,
            "tipo_licencia": self.tipo_lic.pk,
            "fecha_desde": "2026-10-15",
            "fecha_hasta_prevista": "2026-10-25",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_desde", form.errors)
        self.assertIn("ya posee otra licencia activa", str(form.errors["fecha_desde"]))

    def test_licencia_otorgada_form_acepta_periodo_libre(self):
        """LicenciaOtorgadaForm es válido para períodos sin superposición."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_a.pk,
            "tipo_licencia": self.tipo_lic.pk,
            "fecha_desde": "2026-10-22",
            "fecha_hasta_prevista": "2026-10-28",
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Errores del form: {form.errors}")

    def test_justificacion_diferida_form_bloquea_solapamiento(self):
        """JustificacionDiferidaForm bloquea justificaciones en fechas superpuestas."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_a.pk,
            "tipo_licencia": self.tipo_lic.pk,
            "fecha_desde": "2026-10-12",
            "fecha_hasta": "2026-10-18",
            "nueva_marca": "LIC",
            "observaciones": "Superpuesta",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_desde", form.errors)
        self.assertIn("ya posee otra licencia activa", str(form.errors["fecha_desde"]))

    # -------------------------------------------------------------------------
    # Integración con Función Orquestadora
    # -------------------------------------------------------------------------

    def test_validar_solicitud_licencia_detecta_solapamiento(self):
        """validar_solicitud_licencia orquesta y bloquea ante superposición."""
        with self.assertRaises(ValidationError) as ctx:
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_lic,
                docente=self.docente,
                cargo=self.cargo_a,
                fecha_desde=datetime.date(2026, 10, 15),
                fecha_hasta=datetime.date(2026, 10, 25),
                dias=11,
            )
        self.assertIn("ya posee otra licencia activa", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Endpoint API: Validar Solapamiento
    # -------------------------------------------------------------------------

    def test_api_validar_solapamiento_get_detecta_conflicto(self):
        """Endpoint API responde status 200 con valido=False y detalle de solapadas."""
        url = reverse("licencias:validar_solapamiento")
        response = self.client.get(
            url,
            {
                "cargo_id": self.cargo_a.pk,
                "fecha_desde": "2026-10-15",
                "fecha_hasta": "2026-10-25",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["valido"])
        self.assertTrue(data["hay_solapamiento"])
        self.assertEqual(data["cantidad_solapadas"], 1)
        self.assertEqual(data["licencias_solapadas"][0]["id"], self.licencia_activa.pk)

    def test_api_validar_solapamiento_get_periodo_libre(self):
        """Endpoint API responde valido=True si no hay colisión."""
        url = reverse("licencias:validar_solapamiento")
        response = self.client.get(
            url,
            {
                "cargo_id": self.cargo_a.pk,
                "fecha_desde": "2026-10-22",
                "fecha_hasta": "2026-10-28",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["valido"])
        self.assertFalse(data["hay_solapamiento"])
        self.assertEqual(data["cantidad_solapadas"], 0)

    def test_api_validar_solapamiento_get_con_excluir_id(self):
        """Endpoint API excluye la licencia indicada si se está editando."""
        url = reverse("licencias:validar_solapamiento")
        response = self.client.get(
            url,
            {
                "cargo_id": self.cargo_a.pk,
                "fecha_desde": "2026-10-10",
                "fecha_hasta": "2026-10-20",
                "excluir_id": self.licencia_activa.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valido"])
        self.assertFalse(data["hay_solapamiento"])

    def test_api_validar_solapamiento_post_json(self):
        """Endpoint API acepta payload JSON por POST."""
        url = reverse("licencias:validar_solapamiento")
        payload = {
            "cargo": self.cargo_a.pk,
            "fecha_desde": "2026-10-15",
            "fecha_hasta": "2026-10-25",
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valido"])
        self.assertTrue(data["hay_solapamiento"])
