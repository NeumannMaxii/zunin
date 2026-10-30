"""
Filtros y etiquetas de plantilla para control de acceso y grupos de usuarios.
"""

from django import template

register = template.Library()


@register.filter(name="has_group")
def has_group(user, group_name):
    """Verifica si el usuario pertenece al grupo especificado."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter(name="es_administrador")
def es_administrador(user):
    """
    Determina si un usuario tiene rol de administrador institucional
    (superusuario o miembro de Admin_Institucional).
    """
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.groups.filter(name="Admin_Institucional").exists()
    )


@register.filter(name="puede_gestionar_asistencia")
def puede_gestionar_asistencia(user):
    """
    Determina si un usuario tiene permisos de edición / carga en Asistencia.
    Los usuarios que solo pertenecen a Consulta_Directiva no pueden gestionar.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.groups.filter(name="Consulta_Directiva").exists():
        if not user.groups.filter(
            name__in=["Admin_Institucional", "Bedelia_Operadoras"]
        ).exists():
            return False
    return (
        user.has_perm("asistencia.add_registroasistencia")
        or user.groups.filter(
            name__in=["Admin_Institucional", "Bedelia_Operadoras"]
        ).exists()
    )
