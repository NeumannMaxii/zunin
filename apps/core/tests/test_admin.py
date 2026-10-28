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
        Verifica que DocenteAdmin, RegistroAsistenciaAdmin y
        RenglonPlanillaMensualAdmin prohíban el borrado desde el admin.
        """
        request = self.factory.get("/admin/")
        request.user = self.user

        docente_admin = admin.site._registry[Docente]
        asistencia_admin = admin.site._registry[RegistroAsistencia]
        renglon_admin = admin.site._registry[RenglonPlanillaMensual]

        self.assertFalse(docente_admin.has_delete_permission(request))
        self.assertFalse(asistencia_admin.has_delete_permission(request))
        self.assertFalse(renglon_admin.has_delete_permission(request))

    def test_admin_index_responde_302_anonimo_y_200_staff(self):
        """El admin de Django redirige anónimos y responde 200 a staff."""
        resp_anon = self.client.get("/admin/")
        self.assertEqual(resp_anon.status_code, 302)

        self.client.login(username="admin_test", password="testpassword123")
        resp_staff = self.client.get("/admin/")
        self.assertEqual(resp_staff.status_code, 200)
