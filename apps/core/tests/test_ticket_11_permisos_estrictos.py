"""
Pruebas para el Ticket 11: Permisos Estrictos en Vistas (403).

Especificación Técnica:
- Protección Global: Aplicar @login_required en todas las vistas operativas
  (redirección 302 al login para usuarios anónimos).
- Permisos de Escritura (POST): Validar permisos con raise_exception=True
  para devolver 403 estricto cuando un usuario intente forzar una acción.

Criterios de Aceptación:
1. Un usuario Directivo (solo lectura) intenta hacer POST a Asistencia y recibe 403.
2. Un usuario de Bedelía intenta hacer POST al endpoint de Baja y recibe 403.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse

from apps.personal.models import CargoDocente, Docente, EspacioCurricular

User = get_user_model()


class Ticket11PermisosEstrictosTests(TestCase):
    """
    Suite de pruebas integral para el Ticket 11 (Permisos Estrictos y HTTP 403).
    """

    def setUp(self):
        # 1. Configuración de Grupos
        self.grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.grupo_directivo, _ = Group.objects.get_or_create(name="Consulta_Directiva")

        perms_admin = Permission.objects.filter(
            Q(codename__startswith="add_")
            | Q(codename__startswith="change_")
            | Q(codename__startswith="delete_")
            | Q(codename__startswith="view_")
        )
        self.grupo_admin.permissions.set(perms_admin)

        perms_bedelia = Permission.objects.filter(
            Q(codename__startswith="add_")
            | Q(codename__startswith="change_")
            | Q(codename__startswith="view_")
        ).exclude(codename__startswith="delete_")
        self.grupo_bedelia.permissions.set(perms_bedelia)

        perms_directivo = Permission.objects.filter(codename__startswith="view_")
        self.grupo_directivo.permissions.set(perms_directivo)

        self.user_directivo = User.objects.create_user(
            username="directivo_t11", password="password123", is_staff=True
        )
        self.user_directivo.groups.add(self.grupo_directivo)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_t11", password="password123", is_staff=True
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_admin = User.objects.create_user(
            username="admin_t11", password="password123", is_staff=True
        )
        self.user_admin.groups.add(self.grupo_admin)

        self.docente = Docente.objects.create(
            dni="30111222",
            apellido="GUTIERREZ",
            nombre="Clara",
            sexo="F",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="PROG-01",
            nombre="Programación I",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            activo=True,
        )

    # --------------------------------------------------------------------------
    # CRITERIO 1: Directivo (solo lectura) intenta POST a Asistencia -> 403
    # --------------------------------------------------------------------------

    def test_criterio_1_directivo_recibe_403_al_hacer_post_a_asistencia_diaria(self):
        """
        Criterio 1: Directivo intenta POST a Asistencia Diaria y recibe HTTP 403.
        """
        self.client.login(username="directivo_t11", password="password123")
        url = reverse("asistencia:asistencia_diaria")

        response = self.client.post(
            url,
            {
                "fecha": "2026-11-04",
                f"estado_{self.docente.id}": "PRESENTE",
                f"marca_diaria_{self.docente.id}": "PR",
            },
        )
        self.assertEqual(
            response.status_code,
            403,
            "Directivo debe recibir HTTP 403 Forbidden al hacer POST a Asistencia.",
        )

    def test_carga_masiva_redirecciona_301_permanentemente(self):
        """
        Ticket 12.10: Valida que /asistencia/carga-masiva/ responda con HTTP 301
        redireccionando permanentemente a /asistencia/diaria/.
        """
        response = self.client.get(reverse("asistencia:carga_masiva"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("asistencia:asistencia_diaria"))

    def test_criterio_1_directivo_recibe_403_al_hacer_post_a_justificaciones_lote(self):
        """
        Criterio 1: Directivo recibe 403 al hacer POST a justificaciones por lote.
        """
        self.client.login(username="directivo_t11", password="password123")
        url = reverse("asistencia:justificaciones_lote")

        response = self.client.post(url, {"items": ["item1"]})
        self.assertEqual(
            response.status_code,
            403,
            "Directivo debe recibir 403 al hacer POST a Justificaciones Lote.",
        )

    def test_directivo_puede_hacer_get_a_asistencia_solo_lectura(self):
        """
        Verifica que el usuario Directivo SÍ tenga acceso de solo lectura (GET).
        """
        self.client.login(username="directivo_t11", password="password123")
        url = reverse("asistencia:asistencia_diaria")

        response = self.client.get(url, {"fecha": "2026-11-04"})
        self.assertEqual(response.status_code, 200)

    # --------------------------------------------------------------------------
    # CRITERIO 2: Bedelía intenta POST al endpoint de Baja -> 403
    # --------------------------------------------------------------------------

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_docente(self):
        """
        Criterio 2: Bedelía intenta hacer POST a Baja de Docente y recibe HTTP 403.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_baja = reverse("personal:docente_baja", kwargs={"pk": self.docente.pk})

        response = self.client.post(url_baja)
        self.assertEqual(
            response.status_code,
            403,
            "Bedelía debe recibir 403 Forbidden al hacer POST a baja de docente.",
        )

        self.docente.refresh_from_db()
        self.assertTrue(
            self.docente.activo, "El docente no debe haber sido dado de baja."
        )

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_docente_alias(self):
        """
        Criterio 2: Bedelía recibe 403 en ruta alias /personal/docentes/<pk>/baja/.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_alias = reverse(
            "personal:docente_baja", kwargs={"pk": self.docente.pk}
        )

        response = self.client.post(url_alias)
        self.assertEqual(response.status_code, 403)

        self.docente.refresh_from_db()
        self.assertTrue(self.docente.activo)

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_cargo(self):
        """
        Criterio 2: Bedelía recibe 403 al hacer POST al cese de CargoDocente.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_cargo_baja = reverse(
            "personal:cargodocente_baja", kwargs={"pk": self.cargo.pk}
        )

        response = self.client.post(url_cargo_baja)
        self.assertEqual(
            response.status_code,
            403,
            "Bedelía debe recibir 403 Forbidden al hacer POST al cese de cargo.",
        )

        self.cargo.refresh_from_db()
        self.assertTrue(self.cargo.activo)
        self.assertIsNone(self.cargo.fecha_baja)

    def test_admin_puede_hacer_post_a_baja_docente_y_cargo(self):
        """
        Valida que el Administrador sí tenga autorización para ejecutar bajas.
        """
        self.client.login(username="admin_t11", password="password123")

        url_cargo_baja = reverse(
            "personal:cargodocente_baja", kwargs={"pk": self.cargo.pk}
        )
        resp_cargo = self.client.post(url_cargo_baja)
        self.assertEqual(resp_cargo.status_code, 302)
        self.cargo.refresh_from_db()
        self.assertFalse(self.cargo.activo)
        self.assertEqual(self.cargo.fecha_baja, datetime.date.today())

        url_doc_baja = reverse("personal:docente_baja", kwargs={"pk": self.docente.pk})
        resp_doc = self.client.post(url_doc_baja)
        self.assertEqual(resp_doc.status_code, 302)
        self.docente.refresh_from_db()
        self.assertFalse(self.docente.activo)

    # --------------------------------------------------------------------------
    # PROTECCIÓN GLOBAL (@login_required / LoginRequiredMixin)
    # --------------------------------------------------------------------------

    def test_proteccion_global_anonimo_redirige_a_login_en_todas_vistas_operativas(
        self,
    ):
        """
        Verifica que los intentos de acceso no autenticado a las rutas operativas
        del sistema redirijan al formulario de login (HTTP 302 con ?next=...).
        """
        rutas_operativas = [
            reverse("core:dashboard_home"),
            reverse("personal:docente_list"),
            reverse("personal:docente_create"),
            reverse("personal:docente_update", kwargs={"pk": self.docente.pk}),
            reverse("personal:docente_baja", kwargs={"pk": self.docente.pk}),
            reverse("personal:cargodocente_list"),
            reverse("personal:cargodocente_baja", kwargs={"pk": self.cargo.pk}),
            reverse("personal:importar_csv"),
            reverse("personal:catalogos_hub"),
            reverse("personal:carrera_list"),
            reverse("asistencia:asistencia_list"),
            reverse("asistencia:asistencia_diaria"),
            reverse("asistencia:justificaciones_lote"),
            reverse("asistencia:feriado_list"),
            reverse("licencias:tipolicencia_list"),
            reverse("licencias:planilla_list"),
            reverse("licencias:justificacion_diferida"),
        ]

        for ruta in rutas_operativas:
            with self.subTest(ruta=ruta):
                resp = self.client.get(ruta)
                self.assertEqual(
                    resp.status_code,
                    302,
                    f"Ruta {ruta} debe redirigir a login para no autenticados.",
                )
                self.assertIn(
                    "/accounts/login/",
                    resp.headers.get("Location", ""),
                    f"Ruta {ruta} debe redirigir a /accounts/login/.",
                )

    def test_usuario_autenticado_sin_permiso_nunca_redirige_al_login(self):
        """
        Valida que un usuario autenticado sin permisos NUNCA sea redirigido
        al login, sino que reciba el rechazo estricto HTTP 403 Forbidden.
        """
        self.client.login(username="directivo_t11", password="password123")

        rutas_restringidas = [
            ("POST", reverse("asistencia:asistencia_diaria"), {"fecha": "2026-11-04"}),
            (
                "POST",
                reverse("personal:docente_baja", kwargs={"pk": self.docente.pk}),
                {},
            ),
            ("GET", reverse("personal:docente_create"), {}),
            ("GET", reverse("personal:catalogos_hub"), {}),
            ("GET", reverse("personal:importar_csv"), {}),
        ]

        for metodo, ruta, datos in rutas_restringidas:
            with self.subTest(metodo=metodo, ruta=ruta):
                if metodo == "POST":
                    resp = self.client.post(ruta, datos)
                else:
                    resp = self.client.get(ruta, datos)

                self.assertEqual(
                    resp.status_code,
                    403,
                    f"{metodo} {ruta} debe devolver 403 y no redirigir al login.",
                )
