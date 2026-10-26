"""
Modelos base y abstractos para el sistema IESETyFP.
"""

from django.conf import settings
from django.db import models


class AuditoriaModel(models.Model):
    """
    Modelo base abstracto que provee trazabilidad y auditoría de creación
    y modificación de registros.
    """

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_creados",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_modificados",
        verbose_name="Modificado por",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
    )

    class Meta:
        abstract = True

    @property
    def creado_el(self):
        """Compatibilidad con referencias previas a creado_el."""
        return self.creado_en

    @property
    def modificado_el(self):
        """Compatibilidad con referencias previas a modificado_el."""
        return self.actualizado_en
