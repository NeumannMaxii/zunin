"""
Pruebas automatizadas para el Ticket 17.1: Validación de Régimen de Revista.

Criterio de Aceptación:
El sistema restringe y bloquea solicitudes de licencias no aplicables al
régimen del cargo docente (TIT, INT, SUP).
"""

import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.licencias.forms import (
    JustificacionDiferidaForm,
    LicenciaOtorgadaForm,
    TipoLicenciaSearchForm,
)
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.validaciones import (
    REGIMEN_INT,
    REGIMEN_SUP,
    REGIMEN_TIT,
    es_regimen_compatible,
    filtrar_tipos_licencia_por_regimen,
    normalizar_regimen,
    obtener_regimenes_permitidos,
    validar_regimen_revista,
)
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class ValidacionRegimenRevistaTests(TestCase):
    """
    Suite de pruebas para validación y filtrado por régimen de revista (Ticket 17.1).
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Carlos",
            apellido="Benítez",
            dni="29444333",
            activo=True,
        )
        self.docente_otro = Docente.objects.create(
            nombre="Ana",
            apellido="Martínez",
            dni="32111222",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-17",
            nombre="Desarrollo de Software",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PRG-17",
            nombre="Programación",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-17",
            descripcion="Profesor",
            activo=True,
        )

        # 3 Cargos docentes con distintos regímenes de revista
        self.cargo_tit = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )
        self.cargo_int = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista="INT",
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )
        self.cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista="SUP",
            fecha_alta=datetime.date(2025, 1, 1),
            activo=True,
        )

        # Tipos de licencia según especificaciones normativas Ley 647-E
        self.tipo_tit_307 = TipoLicencia.objects.create(
            codigo="TIT-ORD-307",
            articulo="Art. 307",
            descripcion="Descanso anual exclusivo Titulares",
            regimen="TIT",
            situacion_revista_aplicable="TIT",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=60,
            unidad="Corridos",
        )
        self.tipo_int_308 = TipoLicencia.objects.create(
            codigo="INT-ORD-308",
            articulo="Art. 308",
            descripcion="Enfermedad común para Interinos",
            regimen="INT",
            situacion_revista_aplicable="INT",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=30,
            unidad="Corridos",
        )
        self.tipo_sup_308 = TipoLicencia.objects.create(
            codigo="SUP-ORD-308",
            articulo="Art. 308",
            descripcion="Enfermedad común para Suplentes",
            regimen="SUP",
            situacion_revista_aplicable="SUP",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=20,
            unidad="Corridos",
        )
        self.tipo_multi = TipoLicencia.objects.create(
            codigo="GEN-MULTI-340",
            articulo="Art. 340",
            descripcion="Afección común régimen general",
            regimen="TIT",
            situacion_revista_aplicable="TIT,INT,SUP",
            categoria="Ordinaria",
            forma_goce="100%",
            duracion_maxima=10,
            unidad="Hábiles",
        )

        self.hoy = datetime.date(2026, 11, 10)
        self.hasta = datetime.date(2026, 11, 20)

    # =========================================================================
    # CRITERIO DE ACEPTACIÓN: RESTRICCIÓN Y BLOQUEO BACKEND
    # =========================================================================

    def test_criterio_aceptacion_bloqueo_licencia_titular_en_cargo_interino(self):
        """
        Criterio de Aceptación:
        El sistema restringe y bloquea solicitudes de licencias exclusivas
        de Titular (TIT) si el cargo docente es Interino (INT).
        """
        lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_int,  # Interino
            tipo_licencia=self.tipo_tit_307,  # Titular exclusivo
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )

        with self.assertRaises(ValidationError) as ctx:
            lic.save()

        self.assertIn("TIT-ORD-307", str(ctx.exception))
        self.assertIn("Interino", str(ctx.exception))
        self.assertIn("Titular", str(ctx.exception))

    def test_bloqueo_licencia_titular_en_cargo_suplente(self):
        """
        Bloquea solicitud de licencia de Titular en cargo Suplente (SUP).
        """
        lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_sup,  # Suplente
            tipo_licencia=self.tipo_tit_307,  # Titular
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )

        with self.assertRaises(ValidationError) as ctx:
            lic.clean()

        self.assertIn("Suplente", str(ctx.exception))

    def test_bloqueo_licencia_interina_en_cargo_titular(self):
        """
        Bloquea solicitud de licencia de Interino en cargo Titular (TIT).
        """
        lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_tit,  # Titular
            tipo_licencia=self.tipo_int_308,  # Interino
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )

        with self.assertRaises(ValidationError) as ctx:
            lic.save()

        self.assertIn("INT-ORD-308", str(ctx.exception))
        self.assertIn("Titular", str(ctx.exception))

    def test_bloqueo_licencia_suplente_en_cargo_titular(self):
        """
        Bloquea solicitud de licencia de Suplente en cargo Titular (TIT).
        """
        lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_sup_308,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )

        with self.assertRaises(ValidationError):
            lic.clean()

    # =========================================================================
    # ACEPTACIÓN ANTE REGÍMENES COMPATIBLES
    # =========================================================================

    def test_aceptacion_licencia_titular_en_cargo_titular(self):
        """Permite registrar licencia Titular en cargo Titular."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_tit_307,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
            porcentaje_goce=Decimal("100.00"),
        )
        self.assertEqual(lic.pk, lic.id)
        self.assertEqual(lic.cargo.situacion_revista, "TIT")

    def test_aceptacion_licencia_interina_en_cargo_interino(self):
        """Permite registrar licencia Interina en cargo Interino."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_int,
            tipo_licencia=self.tipo_int_308,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        self.assertEqual(lic.cargo.situacion_revista, "INT")

    def test_aceptacion_licencia_suplente_en_cargo_suplente(self):
        """Permite registrar licencia Suplente en cargo Suplente."""
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_sup,
            tipo_licencia=self.tipo_sup_308,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        self.assertEqual(lic.cargo.situacion_revista, "SUP")

    def test_aceptacion_licencia_multirregimen_en_cualquier_cargo(self):
        """
        Una licencia con situacion_revista_aplicable='TIT,INT,SUP'
        es válida para cualquier régimen de revista.
        """
        lic_tit = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_tit,
            tipo_licencia=self.tipo_multi,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        lic_int = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_int,
            tipo_licencia=self.tipo_multi,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        lic_sup = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo_sup,
            tipo_licencia=self.tipo_multi,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )

        self.assertIsNotNone(lic_tit.pk)
        self.assertIsNotNone(lic_int.pk)
        self.assertIsNotNone(lic_sup.pk)

    def test_validacion_coherencia_docente_cargo(self):
        """
        Bloquea si el cargo asignado pertenece a un docente diferente.
        """
        cargo_otro = CargoDocente.objects.create(
            docente=self.docente_otro,
            cargo_catalogo=self.cargo_cat,
            situacion_revista="TIT",
        )
        lic = LicenciaOtorgada(
            docente=self.docente,
            cargo=cargo_otro,  # Pertenece a docente_otro
            tipo_licencia=self.tipo_tit_307,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        with self.assertRaises(ValidationError) as ctx:
            lic.clean()
        self.assertIn("no pertenece", str(ctx.exception))

    # =========================================================================
    # FORMULARIOS: FILTRADO Y VALIDACIÓN EN FORMULARIOS
    # =========================================================================

    def test_licencia_otorgada_form_filtrado_queryset_por_cargo(self):
        """
        Verifica que LicenciaOtorgadaForm filtre el campo tipo_licencia
        según el cargo suministrado en el constructor.
        """
        form_int = LicenciaOtorgadaForm(cargo=self.cargo_int)
        qs_int = form_int.fields["tipo_licencia"].queryset

        # Interino debe ver licencias de INT y multi-régimen,
        # pero NO exclusivas de TIT o SUP
        self.assertIn(self.tipo_int_308, qs_int)
        self.assertIn(self.tipo_multi, qs_int)
        self.assertNotIn(self.tipo_tit_307, qs_int)
        self.assertNotIn(self.tipo_sup_308, qs_int)

        form_tit = LicenciaOtorgadaForm(cargo=self.cargo_tit)
        qs_tit = form_tit.fields["tipo_licencia"].queryset
        self.assertIn(self.tipo_tit_307, qs_tit)
        self.assertIn(self.tipo_multi, qs_tit)
        self.assertNotIn(self.tipo_int_308, qs_tit)
        self.assertNotIn(self.tipo_sup_308, qs_tit)

    def test_licencia_otorgada_form_bloquea_tipo_incompatible(self):
        """
        Si se intenta enviar por formulario un tipo incompatible con el cargo,
        is_valid() retorna False y agrega error en tipo_licencia.
        """
        form_data = {
            "docente": self.docente.id,
            "cargo": self.cargo_int.id,  # Cargo Interino
            "tipo_licencia": self.tipo_tit_307.id,  # Licencia Titular
            "fecha_desde": self.hoy.isoformat(),
            "fecha_hasta_prevista": self.hasta.isoformat(),
            "estado": "OTORGADA",
            "porcentaje_goce": "100.00",
        }
        form = LicenciaOtorgadaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        error_msg = str(form.errors["tipo_licencia"])
        self.assertIn("Interino", error_msg)
        self.assertIn("Titular", error_msg)

    def test_justificacion_diferida_form_bloquea_tipo_incompatible_con_cargo(self):
        """
        JustificacionDiferidaForm también restringe si el tipo_licencia
        no corresponde al régimen del cargo seleccionado.
        """
        form_data = {
            "docente": self.docente.id,
            "cargo": self.cargo_sup.id,  # Suplente
            "tipo_licencia": self.tipo_tit_307.id,  # Titular
            "fecha_desde": self.hoy.isoformat(),
            "fecha_hasta": self.hasta.isoformat(),
            "nueva_marca": "LIC",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)

    def test_tipo_licencia_search_form_filtrar_por_regimen(self):
        """
        TipoLicenciaSearchForm filtra correctamente por parámetro ?regimen=.
        """
        form_tit = TipoLicenciaSearchForm(data={"regimen": "TIT"})
        self.assertTrue(form_tit.is_valid())
        res_tit = form_tit.filtrar()
        self.assertIn(self.tipo_tit_307, res_tit)
        self.assertNotIn(self.tipo_int_308, res_tit)
        self.assertNotIn(self.tipo_sup_308, res_tit)

        form_int = TipoLicenciaSearchForm(data={"regimen": "INT"})
        self.assertTrue(form_int.is_valid())
        res_int = form_int.filtrar()
        self.assertIn(self.tipo_int_308, res_int)
        self.assertNotIn(self.tipo_tit_307, res_int)

    # =========================================================================
    # ENDPOINTS Y APIS
    # =========================================================================

    def test_autocompletar_api_filtrado_por_regimen(self):
        """
        API /api/licencias/autocompletar/?articulo=307&regimen=INT
        excluye licencias incompatibles con el régimen.
        """
        url = reverse("api_licencias:autocompletar")

        # Sin régimen: encuentra 307
        resp_all = self.client.get(url, {"articulo": "307"})
        self.assertEqual(resp_all.status_code, 200)
        codigos_all = [x["codigo"] for x in resp_all.json()]
        self.assertIn("TIT-ORD-307", codigos_all)

        # Con régimen INT: no debe devolver TIT-ORD-307
        resp_int = self.client.get(url, {"articulo": "307", "regimen": "INT"})
        self.assertEqual(resp_int.status_code, 200)
        codigos_int = [x["codigo"] for x in resp_int.json()]
        self.assertNotIn("TIT-ORD-307", codigos_int)

    def test_autocompletar_api_filtrado_por_cargo_id(self):
        """
        API /api/licencias/autocompletar/?articulo=307&cargo_id=<cargo_int>
        deduce el régimen del cargo y filtra las incompatibles.
        """
        url = reverse("api_licencias:autocompletar")
        resp = self.client.get(
            url, {"articulo": "307", "cargo_id": self.cargo_int.id}
        )
        self.assertEqual(resp.status_code, 200)
        codigos = [x["codigo"] for x in resp.json()]
        self.assertNotIn("TIT-ORD-307", codigos)

    def test_api_validar_regimen_endpoint(self):
        """
        API /api/licencias/validar-regimen/ valida compatibilidad por HTTP.
        """
        url = reverse("api_licencias:validar_regimen")

        # 1. Caso compatible: TIT con TIT
        resp_ok = self.client.get(
            url,
            {"tipo_licencia": "TIT-ORD-307", "regimen": "TIT"},
        )
        self.assertEqual(resp_ok.status_code, 200)
        data_ok = resp_ok.json()
        self.assertEqual(data_ok["status"], "success")
        self.assertTrue(data_ok["valido"])

        # 2. Caso incompatible: TIT con INT
        resp_fail = self.client.get(
            url,
            {"tipo_licencia": "TIT-ORD-307", "regimen": "INT"},
        )
        self.assertEqual(resp_fail.status_code, 200)
        data_fail = resp_fail.json()
        self.assertEqual(data_fail["status"], "success")
        self.assertFalse(data_fail["valido"])
        self.assertIn("no es aplicable", data_fail["mensaje"])

        # 3. Validación pasando cargo_id
        resp_cargo = self.client.get(
            url,
            {"tipo_licencia": "TIT-ORD-307", "cargo_id": self.cargo_int.id},
        )
        self.assertEqual(resp_cargo.status_code, 200)
        self.assertFalse(resp_cargo.json()["valido"])

    # =========================================================================
    # MÉTODOS DEL MODELO Y UTILIDADES
    # =========================================================================

    def test_metodos_modelo_tipo_licencia_es_aplicable_a_regimen(self):
        """
        Verifica métodos es_aplicable_a_regimen y obtener_regimenes_permitidos
        en TipoLicencia.
        """
        self.assertTrue(self.tipo_tit_307.es_aplicable_a_regimen("TIT"))
        self.assertTrue(self.tipo_tit_307.es_aplicable_a_regimen("TITULAR"))
        self.assertFalse(self.tipo_tit_307.es_aplicable_a_regimen("INT"))
        self.assertFalse(self.tipo_tit_307.es_aplicable_a_regimen("SUP"))

        self.assertEqual(
            self.tipo_tit_307.obtener_regimenes_permitidos(), {"TIT"}
        )
        self.assertEqual(
            self.tipo_int_308.obtener_regimenes_permitidos(), {"INT"}
        )
        self.assertEqual(
            self.tipo_sup_308.obtener_regimenes_permitidos(), {"SUP"}
        )
        self.assertEqual(
            self.tipo_multi.obtener_regimenes_permitidos(),
            {"TIT", "INT", "SUP"},
        )

    def test_normalizar_regimen_variantes_lexicas(self):
        """
        Verifica normalización de textos de revista a 'TIT', 'INT', 'SUP'.
        """
        self.assertEqual(normalizar_regimen("TIT"), REGIMEN_TIT)
        self.assertEqual(normalizar_regimen("titular"), REGIMEN_TIT)
        self.assertEqual(normalizar_regimen("Titular"), REGIMEN_TIT)
        self.assertEqual(normalizar_regimen("INT"), REGIMEN_INT)
        self.assertEqual(normalizar_regimen("interino"), REGIMEN_INT)
        self.assertEqual(normalizar_regimen("SUP"), REGIMEN_SUP)
        self.assertEqual(normalizar_regimen("suplente"), REGIMEN_SUP)
        self.assertIsNone(normalizar_regimen(None))
        self.assertIsNone(normalizar_regimen(""))
        self.assertIsNone(normalizar_regimen("CONTRATADO"))

    def test_funciones_utilitarias_modulo_validaciones(self):
        """
        Verifica llamadas directas a es_regimen_compatible, validar_regimen_revista,
        obtener_regimenes_permitidos y filtrar_tipos_licencia_por_regimen.
        """
        self.assertTrue(
            es_regimen_compatible(self.tipo_tit_307, situacion_revista="TIT")
        )
        self.assertFalse(
            es_regimen_compatible(self.tipo_tit_307, situacion_revista="INT")
        )
        self.assertTrue(
            validar_regimen_revista(self.tipo_tit_307, cargo=self.cargo_tit)
        )
        with self.assertRaises(ValidationError):
            validar_regimen_revista(self.tipo_tit_307, cargo=self.cargo_int)

        self.assertEqual(
            obtener_regimenes_permitidos(self.tipo_tit_307), {"TIT"}
        )

        qs_sup = filtrar_tipos_licencia_por_regimen(
            situacion_revista=REGIMEN_SUP
        )
        self.assertIn(self.tipo_sup_308, qs_sup)
        self.assertNotIn(self.tipo_tit_307, qs_sup)

    def test_licencia_sin_cargo_no_restringe_regimen(self):
        """
        Una licencia otorgada sin cargo asociado (a nivel agente/docente)
        no se bloquea por régimen de revista.
        """
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=None,
            tipo_licencia=self.tipo_tit_307,
            fecha_desde=self.hoy,
            fecha_hasta_prevista=self.hasta,
        )
        self.assertIsNotNone(lic.pk)
        self.assertIsNone(lic.cargo)

    def test_filtrar_tipos_licencia_por_cargo_id_y_lista(self):
        """
        filtrar_tipos_licencia_por_regimen acepta cargo_id o lista de regímenes.
        """
        qs_cargo_id = filtrar_tipos_licencia_por_regimen(cargo=self.cargo_int.id)
        self.assertIn(self.tipo_int_308, qs_cargo_id)
        self.assertNotIn(self.tipo_tit_307, qs_cargo_id)

        qs_lista = filtrar_tipos_licencia_por_regimen(
            situacion_revista=["INT", "SUP"]
        )
        self.assertIn(self.tipo_int_308, qs_lista)
        self.assertIn(self.tipo_sup_308, qs_lista)
        self.assertNotIn(self.tipo_tit_307, qs_lista)

    def test_licencia_otorgada_form_filtrado_cargos_por_docente(self):
        """
        Al inicializar LicenciaOtorgadaForm con docente, se filtran
        únicamente los cargos correspondientes a ese docente.
        """
        form = LicenciaOtorgadaForm(docente=self.docente)
        cargos = list(form.fields["cargo"].queryset)
        self.assertIn(self.cargo_tit, cargos)
        self.assertIn(self.cargo_int, cargos)
        self.assertIn(self.cargo_sup, cargos)

    def test_api_validar_regimen_post_json(self):
        """
        API /api/licencias/validar-regimen/ soporta payload JSON vía POST.
        """
        url = reverse("api_licencias:validar_regimen")
        payload = {
            "tipo_licencia": "TIT-ORD-307",
            "regimen": "INT",
        }
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["valido"])

    def test_api_validar_regimen_errores_400_y_404(self):
        """
        API /api/licencias/validar-regimen/ retorna 400 si falta parámetro
        y 404 si el tipo de licencia no existe.
        """
        url = reverse("api_licencias:validar_regimen")
        resp_400 = self.client.get(url)
        self.assertEqual(resp_400.status_code, 400)

        resp_404 = self.client.get(url, {"tipo_licencia": "INEXISTENTE-999"})
        self.assertEqual(resp_404.status_code, 404)
