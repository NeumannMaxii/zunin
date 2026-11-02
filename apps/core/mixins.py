"""
Mixins de autenticación y autorización estricta para el sistema Zunin (Ticket 11).
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class PermisosEstrictosMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin base para permisos estrictos en vistas operativas (Ticket 11).
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
