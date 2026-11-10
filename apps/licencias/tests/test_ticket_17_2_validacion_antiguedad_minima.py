"""
Pruebas automatizadas para el Ticket 17.2: Validación de Antigüedad Mínima.

Objetivo:
Aplicar las restricciones de antigüedad (ej: 4 meses en interinos/suplentes
para licencias de salud completas).

Especificaciones Técnicas:
Calcular la antigüedad desde el alta en el establecimiento (fecha_alta).
Si un interino/suplente posee < 4 meses, recortar la enfermedad común a
10 días (interino) o 5 días (suplente).

Criterio de Aceptación:
Un interino con 3 meses de antigüedad que solicita 11 días de enfermedad común
ve su tope reducido a 10 días con bloqueo automático.
"""

import datetime
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
    MESES_MINIMOS_ENFERMEDAD_COMPLETA,
    REGIMEN_INT,
    REGIMEN_SUP,
    REGIMEN_TIT,
    TOPE_ENFERMEDAD_INTERINO_MENOR_4_MESES,
    TOPE_ENFERMEDAD_SUPLENTE_MENOR_4_MESES,
    calcular_antiguedad_docente,
    calcular_antiguedad_meses,
    es_licencia_enfermedad_comun,
    obtener_fecha_alta_docente,
    obtener_tope_efectivo_licencia,
    validar_antiguedad_minima,
    validar_solicitud_licencia,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class ValidacionAntiguedadMinimaTests(TestCase):
    """
    Suite de pruebas para cálculo de antigüedad y restricciones estatutarias.
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Marcos",
            apellido="Ríos",
            dni="31888999",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-172",
            nombre="Desarrollo de Software",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="BD-172",
            nombre="Base de Datos",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-172",
            descripcion="Profesor",
            activo=True,
        )

        # Fecha base para pruebas: 1 de octubre de 2026
        # Si un docente ingresó el 1 de julio de 2026, tiene exactamente 3 meses.
        self.fecha_alta_3_meses = datetime.date(2026, 7, 1)
        self.fecha_alta_4_meses = datetime.date(2026, 6, 1)
        self.fecha_solicitud = datetime.date(2026, 10, 1)

        # Cargo Interino con 3 meses de antigüedad
        self.cargo_int_3_meses = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_INT,
            fecha_alta=self.fecha_alta_3_meses,
            activo=True,
        )

        # Tipos de Licencias
        # Enfermedad Común Interino (Art. 330)
        self.tipo_enf_int = TipoLicencia.objects.create(
            codigo="INT-ORD-330",
            articulo="330",
            descripcion="Afecciones comunes interinos",
            duracion_maxima=30,
            tope_anual=30,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_INT,
            situacion_revista_aplicable=REGIMEN_INT,
            activo=True,
        )

        # Enfermedad Común Suplente (Art. 339)
        self.tipo_enf_sup = TipoLicencia.objects.create(
            codigo="SUP-ORD-339",
            articulo="339",
            descripcion="Afecciones comunes suplentes",
            duracion_maxima=20,
            tope_anual=20,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_SUP,
            situacion_revista_aplicable=REGIMEN_SUP,
            activo=True,
        )

        # Enfermedad Común Titular (Art. 308)
        self.tipo_enf_tit = TipoLicencia.objects.create(
            codigo="TIT-ORD-308",
            articulo="308",
            descripcion="Afecciones comunes titulares",
            duracion_maxima=45,
            tope_anual=45,
            goce_haberes=True,
            cuadro_mensual="IL-01",
            regimen=REGIMEN_TIT,
            situacion_revista_aplicable=REGIMEN_TIT,
            activo=True,
        )

        # Licencia especial con antigüedad mínima de 12 meses
        self.tipo_antiguedad_12m = TipoLicencia.objects.create(
            codigo="ESP-ANT-12M",
            articulo="345",
            descripcion="Licencia especial con requisito de 1 año",
            duracion_maxima=60,
            tope_anual=60,
            goce_haberes=False,
            cuadro_mensual="IL-02",
            antiguedad_minima_meses=12,
            activo=True,
        )

    # -------------------------------------------------------------------------
    # Tests de Constantes y Utilidades de Cálculo de Antigüedad
    # -------------------------------------------------------------------------

    def test_constantes_estatutarias(self):
        """Verifica que las constantes estatutarias respeten la Ley 647-E."""
        self.assertEqual(TOPE_ENFERMEDAD_INTERINO_MENOR_4_MESES, 10)
        self.assertEqual(TOPE_ENFERMEDAD_SUPLENTE_MENOR_4_MESES, 5)
        self.assertEqual(MESES_MINIMOS_ENFERMEDAD_COMPLETA, 4)

    def test_calcular_antiguedad_meses_casos_estatutarios(self):
        """Verifica el cómputo exacto de meses calendario completos."""
        # 3 meses completos
        m = calcular_antiguedad_meses(
            fecha_alta=datetime.date(2026, 7, 1),
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(m, 3)

        # 3 meses y medio sigue siendo 3 meses cumplidos
        m2 = calcular_antiguedad_meses(
            fecha_alta=datetime.date(2026, 7, 1),
            fecha_referencia=datetime.date(2026, 10, 15),
        )
        self.assertEqual(m2, 3)

        # 4 meses cumplidos
        m3 = calcular_antiguedad_meses(
            fecha_alta=datetime.date(2026, 6, 1),
            fecha_referencia=datetime.date(2026, 10, 1),
        )
        self.assertEqual(m3, 4)

        # Fecha de referencia anterior a fecha de alta da 0
        m4 = calcular_antiguedad_meses(
            fecha_alta=datetime.date(2026, 10, 1),
            fecha_referencia=datetime.date(2026, 9, 1),
        )
        self.assertEqual(m4, 0)

        # None en fecha_alta da 0
        self.assertEqual(calcular_antiguedad_meses(None), 0)

    def test_obtener_fecha_alta_docente_cargos(self):
        """Verifica que detecta la fecha de alta más temprana en la institución."""
        fecha_earliest = obtener_fecha_alta_docente(
            self.docente, self.cargo_int_3_meses
        )
        self.assertEqual(fecha_earliest, self.fecha_alta_3_meses)

        # Si el docente tiene otro cargo más antiguo, debe tomar el más antiguo
        CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_TIT,
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )
        fecha_antigua = self.docente.fecha_alta_establecimiento()
        self.assertEqual(fecha_antigua, datetime.date(2025, 1, 1))

        # calcular_antiguedad_docente con cargo más antiguo
        meses = calcular_antiguedad_docente(
            docente=self.docente,
            fecha_referencia=datetime.date(2026, 1, 1),
        )
        self.assertEqual(meses, 12)

    def test_es_licencia_enfermedad_comun_deteccion(self):
        """Verifica la detección automática de tipos de afecciones comunes."""
        self.assertTrue(es_licencia_enfermedad_comun(self.tipo_enf_int))
        self.assertTrue(es_licencia_enfermedad_comun(self.tipo_enf_sup))
        self.assertTrue(es_licencia_enfermedad_comun(self.tipo_enf_tit))
        self.assertFalse(es_licencia_enfermedad_comun(self.tipo_antiguedad_12m))

    def test_obtener_tope_efectivo_licencia_interino_recortado(self):
        """Verifica el cálculo de tope efectivo para interino con < 4 meses."""
        info = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_enf_int,
            cargo=self.cargo_int_3_meses,
            docente=self.docente,
            fecha_referencia=self.fecha_solicitud,
        )
        self.assertEqual(info["antiguedad_meses"], 3)
        self.assertEqual(info["tope_dias"], 10)
        self.assertTrue(info["tope_reducido"])
        self.assertEqual(info["regimen"], REGIMEN_INT)
        self.assertTrue(info["es_enfermedad_comun"])

    def test_obtener_tope_efectivo_licencia_interino_completo(self):
        """Verifica el cálculo de tope efectivo para interino con 4 meses."""
        self.cargo_int_3_meses.fecha_alta = self.fecha_alta_4_meses
        self.cargo_int_3_meses.save()

        info = obtener_tope_efectivo_licencia(
            tipo_licencia=self.tipo_enf_int,
            cargo=self.cargo_int_3_meses,
            docente=self.docente,
            fecha_referencia=self.fecha_solicitud,
        )
        self.assertEqual(info["antiguedad_meses"], 4)
        self.assertEqual(info["tope_dias"], 30)
        self.assertFalse(info["tope_reducido"])

    # -------------------------------------------------------------------------
    # Criterio de Aceptación: Interino con 3 meses vs 11 días
    # -------------------------------------------------------------------------

    def test_criterio_aceptacion_interino_3_meses_solicita_11_dias_bloqueado(self):
        """
        Criterio de Aceptación:
        Un interino con 3 meses de antigüedad que solicita 11 días de enfermedad común
        ve su tope reducido a 10 días con bloqueo automático.
        """
        with self.assertRaises(ValidationError) as ctx:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_int,
                docente=self.docente,
                cargo=self.cargo_int_3_meses,
                fecha_desde=self.fecha_solicitud,
                dias=11,
            )

        mensaje = str(ctx.exception)
        self.assertIn("10 días", mensaje)
        self.assertIn("3 meses", mensaje)
        self.assertIn("reducido", mensaje.lower())

    def test_interino_3_meses_solicita_10_dias_exitoso(self):
        """Un interino con 3 meses puede solicitar hasta 10 días sin error."""
        try:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_int,
                docente=self.docente,
                cargo=self.cargo_int_3_meses,
                fecha_desde=self.fecha_solicitud,
                dias=10,
            )
        except ValidationError:
            self.fail("10 días debería ser válido para un interino con 3 meses.")

    def test_interino_4_meses_solicita_11_dias_exitoso(self):
        """Un interino con 4 meses de antigüedad no tiene tope reducido a 10."""
        self.cargo_int_3_meses.fecha_alta = self.fecha_alta_4_meses
        self.cargo_int_3_meses.save()

        try:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_int,
                docente=self.docente,
                cargo=self.cargo_int_3_meses,
                fecha_desde=self.fecha_solicitud,
                dias=11,
            )
        except ValidationError:
            self.fail(
                "Con 4 meses de antigüedad, el interino no debería ser recortado a 10."
            )

    def test_interino_4_meses_supera_tope_general_falla(self):
        """Un interino con 4 meses que solicita más de su tope general (30) falla."""
        self.cargo_int_3_meses.fecha_alta = self.fecha_alta_4_meses
        self.cargo_int_3_meses.save()

        with self.assertRaises(ValidationError):
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_int,
                docente=self.docente,
                cargo=self.cargo_int_3_meses,
                fecha_desde=self.fecha_solicitud,
                dias=31,
            )

    # -------------------------------------------------------------------------
    # Restricciones para Suplentes (< 4 meses recortado a 5 días)
    # -------------------------------------------------------------------------

    def test_suplente_menos_4_meses_solicita_6_dias_bloqueado(self):
        """Un suplente con 2 meses que solicita 6 días ve tope reducido a 5 días."""
        cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_SUP,
            fecha_alta=datetime.date(2026, 8, 1),  # 2 meses
            activo=True,
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_sup,
                docente=self.docente,
                cargo=cargo_sup,
                fecha_desde=self.fecha_solicitud,
                dias=6,
            )

        mensaje = str(ctx.exception)
        self.assertIn("5 días", mensaje)
        self.assertIn("suplente", mensaje.lower())

    def test_suplente_menos_4_meses_solicita_5_dias_exitoso(self):
        """Un suplente con 2 meses solicitando 5 días es aceptado."""
        cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_SUP,
            fecha_alta=datetime.date(2026, 8, 1),
            activo=True,
        )

        try:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_sup,
                docente=self.docente,
                cargo=cargo_sup,
                fecha_desde=self.fecha_solicitud,
                dias=5,
            )
        except ValidationError:
            self.fail("5 días debería ser válido para suplente con < 4 meses.")

    def test_suplente_4_meses_solicita_6_dias_exitoso(self):
        """Un suplente con 4 meses de antigüedad no tiene recorte a 5 días."""
        cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_SUP,
            fecha_alta=self.fecha_alta_4_meses,
            activo=True,
        )

        try:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_sup,
                docente=self.docente,
                cargo=cargo_sup,
                fecha_desde=self.fecha_solicitud,
                dias=6,
            )
        except ValidationError:
            self.fail("Con 4 meses el suplente puede solicitar más de 5 días.")

    # -------------------------------------------------------------------------
    # Titular no tiene recorte de 4 meses
    # -------------------------------------------------------------------------

    def test_titular_recien_ingresado_no_tiene_recorte(self):
        """Un docente titular con 1 mes de antigüedad mantiene sus 45 días."""
        cargo_tit = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista=REGIMEN_TIT,
            fecha_alta=datetime.date(2026, 9, 1),  # 1 mes
            activo=True,
        )

        try:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_enf_tit,
                docente=self.docente,
                cargo=cargo_tit,
                fecha_desde=self.fecha_solicitud,
                dias=25,
            )
        except ValidationError:
            self.fail("Un titular no debe tener recorte por tener menos de 4 meses.")

    # -------------------------------------------------------------------------
    # Requisito General de Antigüedad Mínima
    # -------------------------------------------------------------------------

    def test_licencia_con_antiguedad_minima_12_meses_bloquea_si_tiene_menos(self):
        """Una licencia con 12 meses mínimos bloquea si tiene menos antigüedad."""
        with self.assertRaises(ValidationError) as ctx:
            validar_antiguedad_minima(
                tipo_licencia=self.tipo_antiguedad_12m,
                docente=self.docente,
                cargo=self.cargo_int_3_meses,
                fecha_desde=self.fecha_solicitud,
                dias=5,
            )
        self.assertIn("12 meses", str(ctx.exception))

    def test_validar_solicitud_licencia_orquestador(self):
        """Verifica la función orquestadora que agrupa régimen y antigüedad."""
        with self.assertRaises(ValidationError):
            validar_solicitud_licencia(
                tipo_licencia=self.tipo_enf_int,
                cargo=self.cargo_int_3_meses,
                docente=self.docente,
                fecha_desde=self.fecha_solicitud,
                dias=11,
            )

    # -------------------------------------------------------------------------
    # Integración con Modelos (LicenciaOtorgada.clean y save)
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_model_clean_bloquea_interino_excedido(self):
        """El modelo LicenciaOtorgada ejecuta la validación de antigüedad en clean()."""
        licencia = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_int_3_meses,
            tipo_licencia=self.tipo_enf_int,
            fecha_desde=self.fecha_solicitud,
            fecha_hasta_prevista=(
                self.fecha_solicitud + datetime.timedelta(days=10)
            ),
            estado="SOLICITADA",
        )

        with self.assertRaises(ValidationError) as ctx:
            licencia.clean()

        self.assertIn("10 días", str(ctx.exception))

    def test_licencia_otorgada_model_clean_permite_dentro_del_tope(self):
        """El modelo LicenciaOtorgada valida correctamente dentro del tope reducido."""
        licencia = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_int_3_meses,
            tipo_licencia=self.tipo_enf_int,
            fecha_desde=self.fecha_solicitud,
            fecha_hasta_prevista=(
                self.fecha_solicitud + datetime.timedelta(days=9)
            ),
            estado="SOLICITADA",
        )
        try:
            licencia.clean()
        except ValidationError:
            self.fail("licencia.clean() no debería fallar con 10 días.")

    # -------------------------------------------------------------------------
    # Integración con Formularios
    # -------------------------------------------------------------------------

    def test_licencia_otorgada_form_bloquea_interino_11_dias(self):
        """LicenciaOtorgadaForm rechaza solicitudes que excedan el tope recortado."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_int_3_meses.pk,
            "tipo_licencia": self.tipo_enf_int.pk,
            "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
            "fecha_hasta_prevista": (
                self.fecha_solicitud + datetime.timedelta(days=10)
            ).strftime("%Y-%m-%d"),
            "estado": "SOLICITADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("10 días", str(form.errors["tipo_licencia"]))

    def test_licencia_otorgada_form_acepta_interino_10_dias(self):
        """LicenciaOtorgadaForm acepta solicitudes dentro del tope recortado."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_int_3_meses.pk,
            "tipo_licencia": self.tipo_enf_int.pk,
            "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
            "fecha_hasta_prevista": (
                self.fecha_solicitud + datetime.timedelta(days=9)
            ).strftime("%Y-%m-%d"),
            "estado": "SOLICITADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Errores del form: {form.errors}")

    def test_justificacion_diferida_form_bloquea_interino_11_dias(self):
        """JustificacionDiferidaForm rechaza solicitudes excedidas."""
        form_data = {
            "docente": self.docente.pk,
            "cargo": self.cargo_int_3_meses.pk,
            "tipo_licencia": self.tipo_enf_int.pk,
            "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
            "fecha_hasta": (
                self.fecha_solicitud + datetime.timedelta(days=10)
            ).strftime("%Y-%m-%d"),
            "nueva_marca": "LIC",
            "observaciones": "Justificación médica",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("10 días", str(form.errors["tipo_licencia"]))

    # -------------------------------------------------------------------------
    # API Validar Antigüedad View Tests
    # -------------------------------------------------------------------------

    def test_api_validar_antiguedad_get_interino_11_dias_bloqueado(self):
        """Endpoint API responde status 200 con valido=False y mensaje de tope."""
        url = reverse("licencias:validar_antiguedad")
        response = self.client.get(
            url,
            {
                "tipo_licencia": self.tipo_enf_int.pk,
                "docente": self.docente.pk,
                "cargo": self.cargo_int_3_meses.pk,
                "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
                "dias": 11,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["valido"])
        self.assertEqual(data["tope_dias"], 10)
        self.assertTrue(data["tope_reducido"])
        self.assertEqual(data["antiguedad_meses"], 3)
        self.assertIn("10 días", data["mensaje"])

    def test_api_validar_antiguedad_get_interino_10_dias_valido(self):
        """Endpoint API responde valido=True cuando no excede el tope reducido."""
        url = reverse("licencias:validar_antiguedad")
        response = self.client.get(
            url,
            {
                "tipo_licencia": self.tipo_enf_int.pk,
                "docente": self.docente.pk,
                "cargo": self.cargo_int_3_meses.pk,
                "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
                "dias": 10,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["valido"])
        self.assertEqual(data["tope_dias"], 10)
        self.assertTrue(data["tope_reducido"])

    def test_api_validar_antiguedad_post_json(self):
        """Endpoint API acepta payload JSON por POST."""
        url = reverse("licencias:validar_antiguedad")
        payload = {
            "tipo_licencia": self.tipo_enf_int.codigo,
            "docente_id": self.docente.pk,
            "cargo_id": self.cargo_int_3_meses.pk,
            "fecha_desde": self.fecha_solicitud.strftime("%Y-%m-%d"),
            "dias": 12,
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valido"])
        self.assertEqual(data["tope_dias"], 10)
