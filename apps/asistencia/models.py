"""
Modelos del módulo de Asistencia y Novedades Diarias para el IESETyFP.
Gestiona el parte diario de novedades, inasistencias y feriados institucionales.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import AuditoriaModel


class DiaNoLaborable(models.Model):
    """
    Feriados, asuetos y días no laborables para cómputo de asistencia
    y control de partes diarios de Bedelía.
    """

    TIPO_CHOICES = [
        ("FERIADO", "Feriado"),
        ("ASUETO", "Asueto"),
        ("NO_LABORABLE", "Día No Laborable"),
    ]

    fecha = models.DateField(unique=True, verbose_name="Fecha")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="FERIADO",
        verbose_name="Tipo",
    )
    descripcion = models.CharField(max_length=150, verbose_name="Descripción")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dias_no_laborables_creados",
        verbose_name="Creado por",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True, verbose_name="Creado en"
    )

    class Meta:
        verbose_name = "Día No Laborable"
        verbose_name_plural = "Días No Laborables"
        ordering = ["fecha"]
        db_table = "gestion_asistencia_dianolaborable"

    def __str__(self):
        return f"{self.fecha} - {self.get_tipo_display()}: {self.descripcion}"


class RegistroAsistencia(AuditoriaModel):
    """
    Parte diario de novedades y control de asistencia docente de Bedelía.
    """

    ESTADO_CHOICES = [
        ("PRESENTE", "Presente"),
        ("AUSENTE", "Ausente"),
        ("LICENCIA", "Licencia"),
        ("JUSTIFICADO", "Justificado"),
    ]

    MARCA_DIARIA_CHOICES = [
        ("P", "Permiso"),
        ("I", "Inasistencia"),
        ("LIC", "Licencia médica o especial"),
        ("LIC.", "Licencia médica o especial (Compatibilidad)"),
        ("LT", "Largo tratamiento"),
        ("PR", "Presente"),
        ("INA", "Inasistencia (Compatibilidad)"),
        ("PERM", "Permiso (Compatibilidad)"),
    ]

    docente = models.ForeignKey(
        "personal.Docente",
        on_delete=models.PROTECT,
        related_name="asistencias",
        verbose_name="Docente",
    )
    cargo = models.ForeignKey(
        "personal.CargoDocente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias",
        verbose_name="Cargo / Materia",
    )
    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    fecha_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Hasta",
    )
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default="PRESENTE",
        verbose_name="Estado de Asistencia",
    )
    marca_diaria = models.CharField(
        max_length=15,
        choices=MARCA_DIARIA_CHOICES,
        blank=True,
        default="P",
        help_text="Marca en planilla: P, I, LIC, LT, PR, etc.",
        verbose_name="Marca Diaria",
    )
    oficina = models.CharField(
        max_length=20,
        default="1452",
        verbose_name="Oficina",
    )
    anio_planilla = models.PositiveIntegerField(
        default=2026,
        verbose_name="Año de Planilla",
    )
    justifica = models.BooleanField(
        default=True,
        verbose_name="Justifica",
    )
    tipo_licencia = models.ForeignKey(
        "licencias.TipoLicencia",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_asistencia",
        verbose_name="Tipo de Licencia",
    )
    numero_disposicion = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número de Disposición",
    )
    observaciones = models.TextField(
        blank=True, verbose_name="Observaciones / Justificación"
    )

    class Meta:
        verbose_name = "Registro de Asistencia"
        verbose_name_plural = "Registros de Asistencia"
        db_table = "gestion_asistencia_registroasistencia"
        constraints = [
            models.UniqueConstraint(
                fields=["docente", "fecha"],
                name="unique_docente_asistencia_diaria",
            )
        ]
        ordering = ["-fecha", "docente__apellido"]

    def clean(self):
        super().clean()
        if self.estado == "LICENCIA" and not self.tipo_licencia:
            raise ValidationError(
                {
                    "tipo_licencia": (
                        "Debe especificar el Tipo de Licencia "
                        "cuando el estado es LICENCIA."
                    )
                }
            )
        if self.estado == "PRESENTE" and self.tipo_licencia:
            raise ValidationError(
                {
                    "tipo_licencia": (
                        "No debe asignar un Tipo de Licencia "
                        "si el estado es PRESENTE."
                    )
                }
            )
        # RN-06: Las inasistencias solamente pueden ser por un día.
        if self.fecha_hasta and self.fecha_hasta != self.fecha:
            es_inasistencia = (
                self.estado == "AUSENTE"
                or self.marca_diaria in ["I", "INA"]
                or (
                    self.tipo_licencia
                    and self.tipo_licencia.categoria == "INASISTENCIA"
                )
            )
            if es_inasistencia:
                raise ValidationError(
                    "RN-06: Las inasistencias solamente pueden ser por un día."
                )

    def justificar_con_formulario(
        self, nueva_marca, tipo_licencia=None, usuario=None
    ):
        """
        RF-09 y RF-11: Transiciona un registro diario de inasistencia ('I' o 'INA')
        a 'LIC' o 'P' (o 'LT') al recibir el formulario oficial en papel de Bedelía.
        Actualiza el estado, marca_diaria, tipo_licencia y modificado_por.
        """
        if self.marca_diaria not in ["I", "INA"] and self.estado != "AUSENTE":
            raise ValidationError(
                "Solo se pueden justificar registros en estado de inasistencia ('I')."
            )
        if nueva_marca not in ["LIC", "LIC.", "P", "LT", "PERM"]:
            raise ValidationError(
                f"Marca no válida para justificación: {nueva_marca}."
            )

        if nueva_marca in ["LIC", "LIC.", "LT"]:
            self.estado = "LICENCIA"
            if tipo_licencia:
                self.tipo_licencia = tipo_licencia
            elif not self.tipo_licencia:
                raise ValidationError(
                    "Debe especificar un Tipo de Licencia para justificar con LIC."
                )
        elif nueva_marca in ["P", "PERM"]:
            self.estado = "JUSTIFICADO"
            if tipo_licencia:
                self.tipo_licencia = tipo_licencia

        self.marca_diaria = nueva_marca
        self.justifica = True
        if usuario:
            self.modificado_por = usuario
        self.full_clean()
        self.save()
        return self

    def horas_afectadas(self):
        """
        Calcula las horas cátedra que el docente debía dictar en la fecha registrada
        según la distribución de sus cargos activos para ese día de la semana.
        """
        weekday = self.fecha.weekday()
        if self.cargo:
            return self.cargo.get_horas_dia(weekday)
        return sum(
            cargo.get_horas_dia(weekday) for cargo in self.docente.cargos.all()
        )

    def __str__(self):
        docente = self.docente.nombre_completo
        return f"{self.fecha} - {docente}: {self.get_estado_display()}"
