"""
Pruebas automatizadas para la modularización del Django Admin (Ticket 2.5).
Verifica registro de modelos, títulos institucionales y candados de borrado.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    TipoAutorizacion,
)


class ModularAdminTests(TestCase):
    """Verifica el desacoplamiento y configuración del admin modular."""

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="admin_test",
            password="testpassword123",
            is_staff=True,
            is_superuser=True,
        )

    def test_titulos_institucionales_configurados(self):
        """Verifica que el panel de administración tenga los títulos del IESETyFP."""
        self.assertEqual(
            admin.site.site_header, "IESETyFP - Bedelía y Gestión Docente"
        )
        self.assertEqual(admin.site.site_title, "IESETyFP Bedelía")
        self.assertEqual(admin.site.index_title, "Panel de Administración")

    def test_modelos_personal_registrados_en_admin(self):
        """Verifica que todos los modelos de apps.personal estén registrados."""
        modelos_personal = [
            Docente,
            CargoDocente,
            Carrera,
            CargoCatalogo,
            TipoAutorizacion,
            EspacioCurricular,
        ]
        for modelo in modelos_personal:
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(
                    admin.site.is_registered(modelo),
                    f"{modelo.__name__} no está registrado en admin.site",
                )

    def test_modelos_asistencia_registrados_en_admin(self):
        """Verifica que todos los modelos de apps.asistencia estén registrados."""
        modelos_asistencia = [DiaNoLaborable, RegistroAsistencia]
        for modelo in modelos_asistencia:
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(
                    admin.site.is_registered(modelo),
                    f"{modelo.__name__} no está registrado en admin.site",
                )

    def test_modelos_licencias_registrados_en_admin(self):
        """Verifica que todos los modelos de apps.licencias estén registrados."""
        modelos_licencias = [TipoLicencia, RenglonPlanillaMensual]
        for modelo in modelos_licencias:
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(
                    admin.site.is_registered(modelo),
                    f"{modelo.__name__} no está registrado en admin.site",
                )

    def test_candados_de_borrado_has_delete_permission_false(self):
        """
        Verifica que DocenteAdmin, CargoDocenteAdmin, RegistroAsistenciaAdmin y
        RenglonPlanillaMensualAdmin prohíban el borrado desde el admin (Ticket 3.9.2).
        """
        request = self.factory.get("/admin/")
        request.user = self.user

        docente_admin = admin.site._registry[Docente]
        cargo_admin = admin.site._registry[CargoDocente]
        asistencia_admin = admin.site._registry[RegistroAsistencia]
        renglon_admin = admin.site._registry[RenglonPlanillaMensual]

        self.assertFalse(docente_admin.has_delete_permission(request))
        self.assertFalse(cargo_admin.has_delete_permission(request))
        self.assertFalse(asistencia_admin.has_delete_permission(request))
        self.assertFalse(renglon_admin.has_delete_permission(request))

    def test_cargodocente_admin_bloqueo_completo_borrado_y_acciones_masivas(self):
        """
        Criterios de Aceptación Ticket 3.9.2:
        1. has_delete_permission retorna False a nivel general y por objeto.
        2. No permite acciones de borrado masivo (sin delete_selected).
        3. El panel admin no muestra el botón de eliminar en formulario.
        4. Acceder a vista de eliminación de CargoDocente retorna 403.
        """
        from django.urls import reverse

        docente = Docente.objects.create(
            dni="30555666",
            apellido="Seguridad",
            nombre="Admin",
            sexo="M",
        )
        cargo = CargoDocente.objects.create(
            docente=docente,
            situacion_revista="TIT",
            horas_lunes=4,
        )

        request = self.factory.get("/admin/")
        request.user = self.user
        cargo_admin = admin.site._registry[CargoDocente]

        # 1. has_delete_permission
        self.assertFalse(cargo_admin.has_delete_permission(request))
        self.assertFalse(cargo_admin.has_delete_permission(request, obj=cargo))

        # 2. get_actions no incluye delete_selected
        acciones = cargo_admin.get_actions(request)
        self.assertNotIn("delete_selected", acciones)

        # 3. Vista de edición sin botón de eliminar
        self.client.login(username="admin_test", password="testpassword123")
        url_change = reverse(
            "admin:personal_cargodocente_change", args=[cargo.pk]
        )
        url_delete = reverse(
            "admin:personal_cargodocente_delete", args=[cargo.pk]
        )
        resp_change = self.client.get(url_change)
        self.assertEqual(resp_change.status_code, 200)
        self.assertFalse(resp_change.context["has_delete_permission"])
        self.assertNotContains(resp_change, "deletelink-box")
        self.assertNotContains(resp_change, url_delete)

        # 4. Vista de eliminación bloqueada con 403 Forbidden
        resp_delete = self.client.get(url_delete)
        self.assertEqual(resp_delete.status_code, 403)

    def test_admin_index_responde_302_anonimo_y_200_staff(self):
        """El admin de Django redirige anónimos y responde 200 a staff."""
        resp_anon = self.client.get("/admin/")
        self.assertEqual(resp_anon.status_code, 302)

        self.client.login(username="admin_test", password="testpassword123")
        resp_staff = self.client.get("/admin/")
        self.assertEqual(resp_staff.status_code, 200)
