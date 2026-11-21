"""
Pruebas automatizadas para Ticket 19.2:
Impacto Automático de Inasistencias por Licencia según Situación de Revista.

Criterios de Aceptación:
1. Evaluación por Materia/Cargo:
   Cruza el artículo de licencia solicitado con la situacion_revista (Titular,
   Interino, Suplente) de cada cargo/materia que dicta el docente (Ley 647-E).
2. Generación Automática de Inasistencias:
   - Para las materias que aplican: genera registros en RegistroAsistencia con
     estado LICENCIA, marca LIC/LT, justificando y asociando el instrumento.
   - Para las materias donde NO aplica: genera o actualiza con inasistencia
     injustificada / ausente (estado AUSENTE, marca I, justifica False).
3. Resumen Operativo para la Bedel:
   Endpoint y función de evaluación que desglosa en vivo por materia:
   "Materia X (Titular) -> Aplica Licencia Art. Y"
   "Materia Z (Suplente) -> No aplica por situación de revista"
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.licencias.services import procesar_justificacion_rango
from apps.licencias.validaciones import evaluar_impacto_licencia_por_revista
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    PlanEstudio,
)

User = get_user_model()


class ImpactoRevistaTicket19_2Tests(TestCase):
    """
    Suite de pruebas para validar el motor de impacto por situación de revista.
    """

    def setUp(self):
        super().setUp()

        # 1. Crear Docente de prueba
        self.docente = Docente.objects.create(
            dni="28555666",
            apellido="BENITEZ",
            nombre="Laura Beatriz",
            activo=True,
            fecha_creacion=datetime.datetime(2025, 1, 1, 10, 0),
        )

        # 2. Carrera y Plan de Estudio
        self.carrera = Carrera.objects.create(
            codigo="TSDS-19",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.plan = PlanEstudio.objects.create(
            carrera=self.carrera,
            nombre="Plan 2022",
            resolucion="Res. 1100/22",
            anio_implementacion=2022,
            activo=True,
        )

        # 3. Materias
        self.materia_a = EspacioCurricular.objects.create(
            codigo="MAT-19A",
            nombre="Sistemas Operativos",
            carrera=self.carrera,
            plan_estudio_ref=self.plan,
            anio=1,
            turno="NOCHE",
        )
        self.materia_b = EspacioCurricular.objects.create(
            codigo="MAT-19B",
            nombre="Algoritmos y Estructuras",
            carrera=self.carrera,
            plan_estudio_ref=self.plan,
            anio=1,
            turno="NOCHE",
        )

        # 4. Cargos con distinta Situación de Revista
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="PROF-19",
            descripcion="Profesor de Cátedra",
            activo=True,
        )
        # Cargo A: TITULAR en Sistemas Operativos
        self.cargo_titular = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.materia_a,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2023, 3, 1),
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            activo=True,
        )
        # Cargo B: SUPLENTE en Algoritmos
        self.cargo_suplente = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.materia_b,
            situacion_revista="SUP",
            fecha_alta=datetime.date(2026, 9, 1),  # Reciente (< 4 meses)
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            activo=True,
        )

        # 5. Tipos de Licencia
        # Tipo 1: Exclusivo para Titulares (ej: Mayor Jerarquía / Sabático)
        self.tipo_lic_solo_titular = TipoLicencia.objects.create(
            codigo="LIC-TIT-ONLY",
            articulo="320-T",
            descripcion="Licencia Exclusiva Titulares",
            categoria="LICENCIA",
            situacion_revista_aplicable="TIT",
            forma_goce="100%",
            duracion_maxima=30,
            cuadro_mensual="IL-01",
            activo=True,
        )
        # Tipo 2: Universal (TIT, INT, SUP)
        self.tipo_lic_universal = TipoLicencia.objects.create(
            codigo="LIC-UNI-ALL",
            articulo="340-U",
            descripcion="Licencia Universal Ordinaria",
            categoria="LICENCIA",
            situacion_revista_aplicable="TIT,INT,SUP",
            forma_goce="100%",
            duracion_maxima=45,
            cuadro_mensual="IL-01",
            activo=True,
        )
        # Tipo 3: Enfermedad común (restringida a 5 días para suplente < 4 meses)
        self.tipo_lic_enfermedad = TipoLicencia.objects.create(
            codigo="LIC-308",
            articulo="308",
            descripcion="Afecciones Comunes y Enfermedad Común",
            categoria="LICENCIA",
            situacion_revista_aplicable="TIT,INT,SUP",
            forma_goce="100%",
            duracion_maxima=45,
            cuadro_mensual="IL-01",
            activo=True,
        )

        # 6. Usuario administrativo
        self.admin_user = User.objects.create_user(
            username="admin_revista_19",
            password="password123",
            is_staff=True,
        )
        admin_group, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.admin_user.groups.add(admin_group)

    def test_01_evaluar_impacto_discrimina_materias_segun_revista(self):
        """
        Prueba que evaluar_impacto_licencia_por_revista distinga correctamente
        las materias que aplican de las que no aplican por revista.
        """
        impactos = evaluar_impacto_licencia_por_revista(
            docente=self.docente,
            tipo_licencia=self.tipo_lic_solo_titular,
            fecha_desde=datetime.date(2026, 11, 4),
            fecha_hasta=datetime.date(2026, 11, 6),
        )

        self.assertEqual(len(impactos), 2)
        dict_por_cargo = {item["cargo_id"]: item for item in impactos}

        # Materia A (Titular): Aplica
        eval_a = dict_por_cargo[self.cargo_titular.pk]
        self.assertTrue(eval_a["aplica"])
        self.assertEqual(eval_a["estado_asistencia"], "LICENCIA")
        self.assertEqual(eval_a["marca_diaria"], "LIC")
        self.assertTrue(eval_a["justifica"])
        self.assertIn("Aplica Licencia Art. 320-T", eval_a["mensaje"])

        # Materia B (Suplente): No aplica
        eval_b = dict_por_cargo[self.cargo_suplente.pk]
        self.assertFalse(eval_b["aplica"])
        self.assertEqual(eval_b["estado_asistencia"], "AUSENTE")
        self.assertEqual(eval_b["marca_diaria"], "I")
        self.assertFalse(eval_b["justifica"])
        self.assertEqual(eval_b["mensaje"], "No aplica por situación de revista")
        self.assertIn("no habilitado estatutariamente", eval_b["detalle"])

    def test_02_evaluar_impacto_enfermedad_comun_suplente_tope_reducido(self):
        """
        Prueba que para enfermedad común, un suplente con < 4 meses de antigüedad
        vea tope reducido o bloqueo si se solicitan más días de los admitidos.
        """
        # Solicitud de 7 días (excede los 5 días tope de suplente < 4 meses)
        desde = datetime.date(2026, 11, 2)
        hasta = datetime.date(2026, 11, 8)

        impactos = evaluar_impacto_licencia_por_revista(
            docente=self.docente,
            tipo_licencia=self.tipo_lic_enfermedad,
            fecha_desde=desde,
            fecha_hasta=hasta,
        )

        dict_por_cargo = {item["cargo_id"]: item for item in impactos}

        # Titular con antigüedad suficiente: aplica
        self.assertTrue(dict_por_cargo[self.cargo_titular.pk]["aplica"])

        # Suplente reciente: no aplica por superar tope reducido a 5 días
        eval_sup = dict_por_cargo[self.cargo_suplente.pk]
        self.assertFalse(eval_sup["aplica"])
        self.assertEqual(eval_sup["estado_asistencia"], "AUSENTE")
        self.assertIn("menor a 4 meses", eval_sup["detalle"])

    def test_03_sincronizacion_licencia_genera_marcas_diferenciadas(self):
        """
        Al otorgar una licencia que solo aplica a Titular, el sistema genera
        automáticamente LICENCIA para Materia A (Titular) y AUSENTE para
        Materia B (Suplente).
        """
        desde = datetime.date(2026, 11, 4)  # Miércoles
        hasta = datetime.date(2026, 11, 4)  # 1 día hábil

        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            tipo_licencia=self.tipo_lic_solo_titular,
            fecha_desde=desde,
            fecha_hasta_prevista=hasta,
            estado="OTORGADA",
            instrumento_legal="Disp. 088/26",
            sincronizar_asistencia=True,
        )
        self.assertIsNotNone(licencia.pk)

        # Verificar registros de asistencia creados
        reg_titular = RegistroAsistencia.objects.filter(
            docente=self.docente,
            cargo=self.cargo_titular,
            fecha=desde,
        ).first()
        self.assertIsNotNone(reg_titular)
        self.assertEqual(reg_titular.estado, "LICENCIA")
        self.assertEqual(reg_titular.marca_diaria, "LIC")
        self.assertTrue(reg_titular.justifica)
        self.assertEqual(reg_titular.tipo_licencia, self.tipo_lic_solo_titular)
        self.assertEqual(reg_titular.numero_disposicion, "Disp. 088/26")

        reg_suplente = RegistroAsistencia.objects.filter(
            docente=self.docente,
            cargo=self.cargo_suplente,
            fecha=desde,
        ).first()
        self.assertIsNotNone(reg_suplente)
        self.assertEqual(reg_suplente.estado, "AUSENTE")
        self.assertEqual(reg_suplente.marca_diaria, "I")
        self.assertFalse(reg_suplente.justifica)
        self.assertIsNone(reg_suplente.tipo_licencia)
        self.assertIn("NO_APLICA_REVISTA", reg_suplente.observaciones)

    def test_04_procesar_justificacion_rango_respeta_revista_por_materia(self):
        """
        procesar_justificacion_rango genera marcas de licencia solo en materias
        donde la situación de revista habilite el artículo.
        """
        desde = datetime.date(2026, 11, 2)  # Lunes
        hasta = datetime.date(2026, 11, 2)  # Lunes

        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=desde,
            fecha_hasta=hasta,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic_solo_titular,
            numero_disposicion="Disp. 101/26",
            usuario=self.admin_user,
        )

        # Se deben haber procesado los 2 cargos del docente para ese lunes
        self.assertEqual(len(registros), 2)

        reg_a = next(r for r in registros if r.cargo == self.cargo_titular)
        self.assertEqual(reg_a.estado, "LICENCIA")
        self.assertEqual(reg_a.marca_diaria, "LIC")
        self.assertTrue(reg_a.justifica)

        reg_b = next(r for r in registros if r.cargo == self.cargo_suplente)
        self.assertEqual(reg_b.estado, "AUSENTE")
        self.assertEqual(reg_b.marca_diaria, "I")
        self.assertFalse(reg_b.justifica)
        self.assertIn("NO APLICA LICENCIA", reg_b.observaciones)

    def test_05_api_evaluar_impacto_revista_endpoint(self):
        """
        Prueba el endpoint JSON /api/licencias/evaluar-impacto-revista/
        usado por el formulario para el resumen operativo de la Bedel.
        """
        self.client.force_login(self.admin_user)
        url = reverse("licencias:api_evaluar_impacto_revista")

        # Llamada GET
        resp = self.client.get(
            url,
            {
                "docente": self.docente.pk,
                "tipo_licencia": self.tipo_lic_solo_titular.pk,
                "fecha_desde": "2026-11-04",
                "fecha_hasta": "2026-11-06",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["resumen"]["total"], 2)
        self.assertEqual(data["resumen"]["aplicables"], 1)
        self.assertEqual(data["resumen"]["no_aplicables"], 1)
        self.assertTrue(data["resumen"]["tiene_incompatibilidad"])

        # Llamada POST con JSON payload
        post_resp = self.client.post(
            url,
            data={
                "docente": self.docente.pk,
                "tipo_licencia": self.tipo_lic_universal.pk,
                "fecha_desde": "2026-11-04",
                "fecha_hasta": "2026-11-06",
            },
            content_type="application/json",
        )
        self.assertEqual(post_resp.status_code, 200)
        post_data = post_resp.json()
        self.assertEqual(post_data["resumen"]["aplicables"], 2)
        self.assertEqual(post_data["resumen"]["no_aplicables"], 0)
        self.assertFalse(post_data["resumen"]["tiene_incompatibilidad"])

    def test_06_api_evaluar_impacto_errores_400_y_404(self):
        """Prueba manejo de parámetros faltantes o entidades inexistentes."""
        self.client.force_login(self.admin_user)
        url = reverse("licencias:api_evaluar_impacto_revista")

        # Falta docente
        r1 = self.client.get(url, {"tipo_licencia": self.tipo_lic_universal.pk})
        self.assertEqual(r1.status_code, 400)

        # Falta tipo_licencia
        r2 = self.client.get(url, {"docente": self.docente.pk})
        self.assertEqual(r2.status_code, 400)

        # Docente inexistente
        r3 = self.client.get(
            url,
            {"docente": 999999, "tipo_licencia": self.tipo_lic_universal.pk},
        )
        self.assertEqual(r3.status_code, 404)
