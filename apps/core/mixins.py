"""
Mixins de autenticación y autorización estricta para el sistema Zunin.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class PermisosEstrictosMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin base para permisos estrictos.
    - Protección Global: Los usuarios anónimos son redirigidos al
      formulario de login institucional (HTTP 302).
    - Permisos de Escritura y Acceso: Los usuarios autenticados que carezcan
      del rol o privilegios requeridos reciben 'Acceso Denegado' estricto
      (HTTP 403 Forbidden) mediante raise_exception=True, evitando ser
      redirigidos al login.
    """

    raise_exception = True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        raise PermissionDenied(self.get_permission_denied_message())


class SoloAdminInstitucionalMixin(PermisosEstrictosMixin):
    """
    Mixin para restringir el acceso exclusivamente a Superusuarios y
    miembros del grupo Admin_Institucional (Ticket 10.1, Ticket 11, Ticket 22).
    Los usuarios no autenticados son redirigidos a la pantalla de login (302).
    Los usuarios autenticados sin el rol adecuado reciben HTTP 403 Forbidden.
    """

    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Admin_Institucional").exists()
        )
