"""
Pruebas automatizadas de autenticación para el Ticket 1:
- Acceso a pantalla de login para usuarios anónimos (HTTP 200).
- Redirección tras inicio de sesión exitoso hacia '/' (HTTP 302).
- Manejo de credenciales inválidas.
- Requisito de método POST para logout seguro (Django 5+).
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AuthViewsTests(TestCase):
    """Pruebas de endpoints de autenticación y sesiones."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.username = "operador_test"
        self.password = "passwordSegura123"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )

    def test_pantalla_login_accesible_para_usuario_anonimo(self):
        """
        1. Valida que un usuario anónimo puede acceder a la pantalla de login
        recibiendo código HTTP 200 y utilizando la plantilla registration/login.html.
        """
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, "Iniciar Sesión")
        self.assertContains(response, "Proyecto Zunin")

    def test_login_exitoso_redirige_a_raiz(self):
        """
        2. Valida que un inicio de sesión exitoso redirige a '/' (HTTP 302).
        """
        response = self.client.post(
            reverse("login"),
            {
                "username": self.username,
                "password": self.password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_credenciales_invalidas_permanece_en_login(self):
        """
        Valida que credenciales inválidas no autentiquen y devuelvan código 200
        con el mensaje de error correspondiente.
        """
        response = self.client.post(
            reverse("login"),
            {
                "username": self.username,
                "password": "password_incorrecta",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        user = response.context["user"]
        self.assertFalse(user.is_authenticated)

    def test_logout_requiere_metodo_post(self):
        """
        Valida que el logout en Django requiere el método POST por seguridad.
        Una solicitud GET debe retornar HTTP 405 (Method Not Allowed).
        """
        self.client.login(username=self.username, password=self.password)

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("logout"))
        self.assertIn(post_response.status_code, [200, 302])


class CrearUsuariosCommandTests(TestCase):
    """Pruebas para el comando crear_usuarios (Ticket 0 / Ticket 3.9.4)."""

    def test_crear_usuarios_reset_crea_mudarte_con_permisos(self):
        """
        Ticket 3.9.4:
        - Al correr crear_usuarios --reset, la usuaria mudarte se crea exitosamente.
        - mudarte autentica y posee permisos de carga (grupo Bedelia_Operadoras).
        """
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("crear_usuarios", reset=True, stdout=out)

        User = get_user_model()
        self.assertTrue(User.objects.filter(username="mudarte").exists())

        usuario_mudarte = User.objects.get(username="mudarte")
        self.assertEqual(usuario_mudarte.first_name, "María Eva")
        self.assertEqual(usuario_mudarte.last_name, "Duarte")
        self.assertTrue(usuario_mudarte.is_staff)
        self.assertFalse(usuario_mudarte.is_superuser)

        # Autenticación con contraseña admin123
        self.assertTrue(usuario_mudarte.check_password("admin123"))

        # Pertenencia a grupo Bedelia_Operadoras
        self.assertTrue(
            usuario_mudarte.groups.filter(name="Bedelia_Operadoras").exists()
        )

        # Permisos operativos de carga (add y change) pero NO delete
        self.assertTrue(usuario_mudarte.has_perm("asistencia.add_registroasistencia"))
        self.assertTrue(usuario_mudarte.has_perm("asistencia.change_registroasistencia"))
        self.assertTrue(usuario_mudarte.has_perm("personal.add_docente"))
        self.assertFalse(usuario_mudarte.has_perm("personal.delete_docente"))

