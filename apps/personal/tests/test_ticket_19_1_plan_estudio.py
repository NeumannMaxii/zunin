"""
Pruebas automatizadas para el Ticket 19.1:
Asociación de Materias a Carrera y Plan de Estudio Formal.

Valida:
1. Creación de PlanEstudio asociado a Carrera con campos oficiales.
2. Integridad referencial (carrera + nombre) y on_delete=models.PROTECT.
3. Validación en EspacioCurricular para impedir vincular planes de otra carrera.
4. Formularios PlanEstudioForm y EspacioCurricularForm con filtrado dinámico.
5. Endpoint API JSON para consulta de planes por carrera.
6. Permisos RBAC y vistas CRUD de catálogo (PlanEstudioListView, etc).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.personal.forms import EspacioCurricularForm, PlanEstudioForm
from apps.personal.models import Carrera, EspacioCurricular, PlanEstudio


class Ticket19_1PlanEstudioModelTests(TestCase):
    """Pruebas del modelo PlanEstudio y su relación con Carrera y EspacioCurricular."""

    def setUp(self):
        self.carrera_soft = Carrera.objects.create(
            codigo="TSDS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.carrera_redes = Carrera.objects.create(
            codigo="TSRI",
            nombre="Tecnicatura Superior en Redes e Infraestructura",
            activo=True,
        )

    def test_creacion_plan_estudio_asociado_a_carrera(self):
        """Verifica la persistencia y resolución de campos del PlanEstudio."""
        plan = PlanEstudio.objects.create(
            carrera=self.carrera_soft,
            nombre="Plan 2022",
            resolucion="Res. 542/19 - MECCyT",
            anio_implementacion=2022,
            activo=True,
            descripcion="Plan de estudios vigente con enfoque en desarrollo web.",
        )
        plan.refresh_from_db()
        self.assertEqual(plan.carrera, self.carrera_soft)
        self.assertEqual(plan.nombre, "Plan 2022")
        self.assertEqual(plan.resolucion, "Res. 542/19 - MECCyT")
        self.assertEqual(plan.anio_implementacion, 2022)
        self.assertTrue(plan.activo)
        self.assertIn("TSDS", str(plan))
        self.assertIn("Plan 2022", str(plan))

    def test_on_delete_protect_en_carrera_con_planes(self):
        """Verifica que no se pueda borrar una Carrera si tiene planes asociados."""
        PlanEstudio.objects.create(
            carrera=self.carrera_soft,
            nombre="Plan 2018",
            resolucion="Res. 100/18",
        )
        with self.assertRaises(ProtectedError):
            self.carrera_soft.delete()

    def test_on_delete_protect_en_plan_con_espacios_curriculares(self):
        """Impide borrar un PlanEstudio si tiene espacios curriculares asociados."""
        plan = PlanEstudio.objects.create(
            carrera=self.carrera_soft,
            nombre="Plan 2022",
        )
        EspacioCurricular.objects.create(
            codigo="DS-101",
            nombre="Programación I",
            carrera=self.carrera_soft,
            plan_estudio_ref=plan,
            anio=1,
        )
        with self.assertRaises(ProtectedError):
            plan.delete()

    def test_validacion_espacio_curricular_plan_de_otra_carrera_falla(self):
        """
        Criterio de Aceptación:
        El método clean() de EspacioCurricular debe rechazar si el plan de estudio
        elegido pertenece a una carrera diferente a la de la materia.
        """
        plan_redes = PlanEstudio.objects.create(
            carrera=self.carrera_redes,
            nombre="Plan 2020 Redes",
            resolucion="Res. 200/20",
        )
        espacio = EspacioCurricular(
            codigo="DS-999",
            nombre="Sistemas Operativos",
            carrera=self.carrera_soft,  # Software
            plan_estudio_ref=plan_redes,  # Redes (Incompatible)
            anio=1,
        )
        with self.assertRaises(ValidationError) as ctx:
            espacio.full_clean()
        self.assertIn("plan_estudio_ref", ctx.exception.message_dict)

    def test_sincronizacion_automatica_texto_plan_y_referencia_en_save(self):
        """Verifica que el campo texto plan_estudio se sincronice automáticamente."""
        plan = PlanEstudio.objects.create(
            carrera=self.carrera_soft,
            nombre="Plan 2022 Formal",
        )
        espacio = EspacioCurricular.objects.create(
            codigo="DS-102",
            nombre="Base de Datos",
            carrera=self.carrera_soft,
            plan_estudio_ref=plan,
            anio=1,
        )
        espacio.refresh_from_db()
        self.assertEqual(espacio.plan_estudio, "Plan 2022 Formal")
        self.assertIn("Plan 2022 Formal", str(espacio))


class Ticket19_1FormulariosTests(TestCase):
    """Pruebas de validación en PlanEstudioForm y EspacioCurricularForm."""

    def setUp(self):
        self.carrera_soft = Carrera.objects.create(
            codigo="TSDS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.carrera_redes = Carrera.objects.create(
            codigo="TSRI",
            nombre="Tecnicatura Superior en Redes e Infraestructura",
            activo=True,
        )
        self.plan_soft = PlanEstudio.objects.create(
            carrera=self.carrera_soft,
            nombre="Plan 2022 Software",
            resolucion="Res. 542/19",
            activo=True,
        )
        self.plan_redes = PlanEstudio.objects.create(
            carrera=self.carrera_redes,
            nombre="Plan 2021 Redes",
            resolucion="Res. 120/21",
            activo=True,
        )

    def test_plan_estudio_form_validacion_unicidad(self):
        """Verifica que el formulario rechace duplicados en la misma carrera."""
        form_data = {
            "carrera": self.carrera_soft.pk,
            "nombre": "Plan 2022 Software",  # Ya existe en Software
            "resolucion": "Otra Res",
            "activo": True,
        }
        form = PlanEstudioForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)

    def test_espacio_curricular_form_filtrado_dinamico_por_carrera(self):
        """Verifica que el queryset de plan_estudio_ref se filtre por carrera."""
        form = EspacioCurricularForm(data={"carrera": self.carrera_soft.pk})
        planes_qs = form.fields["plan_estudio_ref"].queryset
        self.assertIn(self.plan_soft, planes_qs)
        self.assertNotIn(self.plan_redes, planes_qs)

    def test_espacio_curricular_form_rechaza_plan_de_otra_carrera(self):
        """Verifica que el formulario rechace si se envía un plan de otra carrera."""
        form_data = {
            "codigo": "DS-205",
            "nombre": "Ingeniería de Software",
            "carrera": self.carrera_soft.pk,  # Software
            "plan_estudio_ref": self.plan_redes.pk,  # Redes
            "anio": 2,
            "comision": "UNICA",
            "turno": "NOCHE",
            "regimen": "ANUAL",
        }
        form = EspacioCurricularForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("plan_estudio_ref", form.errors)


class Ticket19_1VistasYAPITests(TestCase):
    """Pruebas de vistas, seguridad RBAC y API JSON de planes de estudio."""

    def setUp(self):
        User = get_user_model()
        grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")

        self.user_admin = User.objects.create_user(
            username="admin_planes",
            password="password123",
            is_staff=True,
        )
        self.user_admin.groups.add(grupo_admin)

        self.user_bedel = User.objects.create_user(
            username="bedel_planes",
            password="password123",
            is_staff=False,
        )
        self.user_bedel.groups.add(grupo_bedelia)

        self.carrera = Carrera.objects.create(
            codigo="TSDS",
            nombre="Desarrollo de Software",
            activo=True,
        )
        self.plan = PlanEstudio.objects.create(
            carrera=self.carrera,
            nombre="Plan 2022",
            resolucion="Res. 542/19",
            anio_implementacion=2022,
            activo=True,
        )

    def test_listado_planes_requiere_admin_institucional(self):
        """Bedelia no puede acceder al listado de planes (403 Forbidden)."""
        self.client.login(username="bedel_planes", password="password123")
        url = reverse("personal:planestudio_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_institucional_accede_listado_planes(self):
        """Admin institucional accede con 200 OK y visualiza los planes."""
        self.client.login(username="admin_planes", password="password123")
        url = reverse("personal:planestudio_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plan 2022")
        self.assertContains(response, "Res. 542/19")

    def test_creacion_plan_via_view_post(self):
        """Admin institucional puede crear un nuevo plan de estudio."""
        self.client.login(username="admin_planes", password="password123")
        url = reverse("personal:planestudio_create")
        data = {
            "carrera": self.carrera.pk,
            "nombre": "Plan 2026 Nuevo",
            "resolucion": "Res. 888/26 - MECCyT",
            "anio_implementacion": 2026,
            "activo": True,
            "descripcion": "Nuevo plan aprobado para la carrera",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PlanEstudio.objects.filter(nombre="Plan 2026 Nuevo").exists()
        )

    def test_api_planes_por_carrera_retorna_json(self):
        """El endpoint JSON retorna los planes activos asociados a la carrera."""
        url = reverse("personal:api_planes_por_carrera")
        response = self.client.get(url, {"carrera_id": self.carrera.pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("planes", data)
        self.assertEqual(len(data["planes"]), 1)
        self.assertEqual(data["planes"][0]["nombre"], "Plan 2022")
        self.assertEqual(data["planes"][0]["resolucion"], "Res. 542/19")

    def test_catalogos_hub_incluye_conteo_de_planes(self):
        """El hub de catálogos refleja el total y activos de planes de estudio."""
        self.client.login(username="admin_planes", password="password123")
        url = reverse("personal:catalogos_hub")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planes de Estudio")
        self.assertEqual(response.context["total_planes"], 1)
        self.assertEqual(response.context["planes_activos"], 1)

    def test_espaciocurricular_form_bloquea_carrera_y_plan_al_editar(self):
        """Al editar materia, carrera y plan quedan bloqueados."""
        from apps.personal.forms import EspacioCurricularForm
        materia = EspacioCurricular.objects.create(
            codigo="TEST-101",
            nombre="Materia Editable",
            carrera=self.carrera,
            plan_estudio_ref=self.plan,
            anio=1,
            comision="UNICA",
            turno="NOCHE",
            regimen="ANUAL",
        )
        form = EspacioCurricularForm(instance=materia)
        self.assertTrue(form.fields["carrera"].disabled)
        self.assertTrue(form.fields["plan_estudio_ref"].disabled)

        # POST sin enviar carrera ni plan_estudio_ref es válido porque son disabled
        post_form = EspacioCurricularForm(
            data={
                "codigo": "TEST-101",
                "nombre": "Materia Editada OK",
                "anio": 1,
                "comision": "UNICA",
                "turno": "NOCHE",
                "regimen": "ANUAL",
            },
            instance=materia,
        )
        self.assertTrue(post_form.is_valid(), post_form.errors)
        actualizada = post_form.save()
        self.assertEqual(actualizada.carrera, self.carrera)
        self.assertEqual(actualizada.plan_estudio_ref, self.plan)

    def test_docente_contacto_email_y_celular(self):
        """Docente sincroniza campos de contacto (email y celular) correctamente."""
        from apps.personal.models import Docente
        doc = Docente.objects.create(
            dni="99887766",
            apellido="Gomez",
            nombre="Juan",
            email="juan.gomez@iesetyfp.edu.ar",
            celular="362-4112233",
        )
        self.assertIn("juan.gomez@iesetyfp.edu.ar", doc.contacto)
        self.assertIn("362-4112233", doc.contacto)
        self.assertEqual(doc.celular_limpio, "3624112233")
