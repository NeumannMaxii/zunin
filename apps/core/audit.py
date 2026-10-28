"""
Helper de Auditoría Polimórfico y Defensivo (Ticket 0.5).
Provee funciones y mixins para registrar trazabilidad de usuarios y timestamps
en modelos heterogéneos (legacy y modernos) sin fallar por ausencia de campos.
"""

from django.http import HttpResponseRedirect
from django.utils import timezone


def audit_save(obj, user, created=False):
    """
    Asigna defensivamente datos de auditoría al objeto según los campos
    disponibles y ejecuta su validación y persistencia.

    - Si tiene 'creado_por', created=True y no hay creado_por_id: asigna user.
    - Si tiene 'modificado_por': asigna user.
    - Si tiene 'actualizado_en' o 'fecha_modificacion': actualiza con ahora.
    - Finalmente ejecuta obj.full_clean() y obj.save().
    """
    audit_user = (
        user
        if (user is not None and getattr(user, "is_authenticated", True))
        else None
    )

    if (
        hasattr(obj, "creado_por")
        and created
        and not getattr(obj, "creado_por_id", None)
    ):
        obj.creado_por = audit_user

    if hasattr(obj, "modificado_por"):
        obj.modificado_por = audit_user

    ahora = timezone.now()
    if hasattr(obj, "actualizado_en"):
        obj.actualizado_en = ahora
    if hasattr(obj, "fecha_modificacion"):
        obj.fecha_modificacion = ahora

    if hasattr(obj, "full_clean"):
        obj.full_clean()
    obj.save()
    return obj


class AuditoriaFormMixin:
    """
    Mixin para vistas basadas en clases (CBV) de Django.
    Sobrescribe form_valid para interceptar el guardado e inyectar el usuario
    ejecutando audit_save.
    """

    def form_valid(self, form):
        obj = form.save(commit=False)
        created = getattr(obj, "pk", None) is None
        user = getattr(self.request, "user", None)
        self.object = audit_save(obj, user, created=created)
        if hasattr(form, "save_m2m"):
            form.save_m2m()
        if hasattr(self, "get_success_url"):
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)
