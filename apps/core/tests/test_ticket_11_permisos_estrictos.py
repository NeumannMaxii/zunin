"""
Pruebas para el Ticket 11: Permisos Estrictos en Vistas (403).

Especificación Técnica:
- Protección Global: Aplicar @login_required en todas las vistas operativas (302 a login para anónimos).
- Permisos de Escritura (POST): Validar permisos con raise_exception=True para que Django
  devuelva un 403 estricto cuando un usuario intente forzar una acción que no le corresponde.

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

from apps.asistencia.models import RegistroAsistencia
from apps.personal.models import CargoDocente, Docente, EspacioCurricular

User = get_user_model()


class Ticket11PermisosEstrictosTests(TestCase):
    """
    Suite de pruebas integral para el Ticket 11 (Permisos Estrictos y HTTP 403).
    """

    def setUp(self):
        # 1. Configuración de Grupos
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_directivo, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )

        # Asignación de permisos según especificación Zunin
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

        perms_directivo = Permission.objects.filter(
            codename__startswith="view_"
        )
        self.grupo_directivo.permissions.set(perms_directivo)

        # 2. Creación de Usuarios por Rol
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

        # 3. Datos base para pruebas
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
    # CRITERIO DE ACEPTACIÓN 1: Directivo (solo lectura) intenta POST a Asistencia -> 403
    # --------------------------------------------------------------------------

    def test_criterio_1_directivo_recibe_403_al_hacer_post_a_asistencia_diaria(self):
        """
        Criterio 1: Un usuario Directivo (solo lectura) intenta hacer POST
        a Asistencia Diaria y recibe HTTP 403 Forbidden estricto (no 302).
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

    def test_criterio_1_directivo_recibe_403_al_hacer_post_a_carga_masiva(self):
        """
        Criterio 1: Directivo recibe 403 al hacer POST al endpoint de carga masiva.
        """
        self.client.login(username="directivo_t11", password="password123")
        url = reverse("asistencia:carga_masiva")

        response = self.client.post(
            url,
            {
                "fecha": "2026-11-04",
                f"estado_{self.docente.id}": "PRESENTE",
            },
        )
        self.assertEqual(
            response.status_code,
            403,
            "Directivo debe recibir HTTP 403 Forbidden al hacer POST a Carga Masiva.",
        )

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
            "Directivo debe recibir HTTP 403 Forbidden al hacer POST a Justificaciones Lote.",
        )

    def test_directivo_puede_hacer_get_a_asistencia_solo_lectura(self):
        """
        Verifica que el usuario Directivo SÍ tenga acceso de solo lectura (GET)
        a la planilla de asistencia diaria.
        """
        self.client.login(username="directivo_t11", password="password123")
        url = reverse("asistencia:asistencia_diaria")

        response = self.client.get(url, {"fecha": "2026-11-04"})
        self.assertEqual(response.status_code, 200)

    # --------------------------------------------------------------------------
    # CRITERIO DE ACEPTACIÓN 2: Bedelía intenta POST al endpoint de Baja -> 403
    # --------------------------------------------------------------------------

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_docente(self):
        """
        Criterio 2: Un usuario de Bedelía intenta hacer POST al endpoint de
        Baja de Docente y recibe HTTP 403 Forbidden estricto.
        El docente debe continuar activo.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_baja = reverse("personal:docente_baja", kwargs={"pk": self.docente.pk})

        response = self.client.post(url_baja)
        self.assertEqual(
            response.status_code,
            403,
            "Bedelía debe recibir HTTP 403 Forbidden al hacer POST a baja de docente.",
        )

        self.docente.refresh_from_db()
        self.assertTrue(self.docente.activo, "El docente no debe haber sido dado de baja.")

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_docente_alias(self):
        """
        Criterio 2: Bedelía recibe 403 también en la ruta alias /personal/docentes/<pk>/baja/.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_alias = reverse("personal:docente_baja_alias", kwargs={"pk": self.docente.pk})

        response = self.client.post(url_alias)
        self.assertEqual(response.status_code, 403)

        self.docente.refresh_from_db()
        self.assertTrue(self.docente.activo)

    def test_criterio_2_bedelia_recibe_403_al_hacer_post_a_baja_cargo(self):
        """
        Criterio 2: Bedelía recibe 403 al hacer POST al endpoint de cese de CargoDocente.
        El cargo debe continuar activo y sin fecha de baja.
        """
        self.client.login(username="bedelia_t11", password="password123")
        url_cargo_baja = reverse("personal:cargodocente_baja", kwargs={"pk": self.cargo.pk})

        response = self.client.post(url_cargo_baja)
        self.assertEqual(
            response.status_code,
            403,
            "Bedelía debe recibir HTTP 403 Forbidden al hacer POST al cese de cargo.",
        )

        self.cargo.refresh_from_db()
        self.assertTrue(self.cargo.activo)
        self.assertIsNone(self.cargo.fecha_baja)

    def test_admin_puede_hacer_post_a_baja_docente_y_cargo(self):
        """
        Valida que el usuario Administrador sí tenga autorización para ejecutar
        la baja lógica de docente y el cese de cargo puntual.
        """
        self.client.login(username="admin_t11", password="password123")

        # Cese de cargo por admin
        url_cargo_baja = reverse("personal:cargodocente_baja", kwargs={"pk": self.cargo.pk})
        resp_cargo = self.client.post(url_cargo_baja)
        self.assertEqual(resp_cargo.status_code, 302)
        self.cargo.refresh_from_db()
        self.assertFalse(self.cargo.activo)
        self.assertEqual(self.cargo.fecha_baja, datetime.date.today())

        # Baja de docente por admin
        url_doc_baja = reverse("personal:docente_baja", kwargs={"pk": self.docente.pk})
        resp_doc = self.client.post(url_doc_baja)
        self.assertEqual(resp_doc.status_code, 302)
        self.docente.refresh_from_db()
        self.assertFalse(self.docente.activo)

    # --------------------------------------------------------------------------
    # PROTECCIÓN GLOBAL (@login_required / LoginRequiredMixin)
    # --------------------------------------------------------------------------

    def test_proteccion_global_anonimo_redirige_a_login_en_todas_vistas_operativas(self):
        """
        Verifica que los intentos de acceso no autenticado a las rutas operativas
        del sistema redirijan al formulario de login (HTTP 302 con ?next=...),
        cumpliendo la protección global.
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
            reverse("asistencia:carga_masiva"),
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
                    f"Ruta {ruta} debe redirigir a login para usuarios no autenticados.",
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

        # Intentos de POST o acceso prohibido
        rutas_restringidas = [
            ("POST", reverse("asistencia:asistencia_diaria"), {"fecha": "2026-11-04"}),
            ("POST", reverse("personal:docente_baja", kwargs={"pk": self.docente.pk}), {}),
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
                    f"{metodo} {ruta} debe devolver 403 Forbidden y no redirigir al login.",
                )
