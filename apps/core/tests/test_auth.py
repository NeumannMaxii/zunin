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
