"""
Modelos relacionales para el Sistema de Bedelía del IESETyFP.
Gestiona el cuerpo docente, espacios curriculares, asignación de cargos,
catálogo de tipos de licencias y el registro diario de asistencia.
"""

from django.db import models
from django.core.exceptions import ValidationError


class Docente(models.Model):
    """Información filiatoria y de contacto del personal docente del IESETyFP."""

    SEXO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("X", "No binario"),
    ]

    dni = models.CharField(max_length=20, unique=True, verbose_name="DNI")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        default="M",
        verbose_name="Sexo",
    )
    contacto = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Contacto (Teléfono/Email)",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación"
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de Modificación"
    )

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} (DNI: {self.dni})"

    @property
    def nombre_completo(self):
        """Retorna el nombre y apellido en formato Apellido, Nombre."""
        return f"{self.apellido}, {self.nombre}"

    @property
    def total_horas_semanales(self):
        """Calcula el total de horas cátedra semanales acumuladas en sus cargos."""
        return sum(cargo.total_horas_semanales for cargo in self.cargos.all())


class EspacioCurricular(models.Model):
    """Asignaturas, materias o talleres de las carreras técnicas y profesorados."""

    codigo = models.CharField(
        max_length=30, unique=True, verbose_name="Código de Espacio"
    )
    nombre = models.CharField(
        max_length=150, verbose_name="Nombre de la Asignatura"
    )
    carrera = models.CharField(max_length=150, verbose_name="Carrera")
    anio = models.PositiveSmallIntegerField(verbose_name="Año de la Carrera")
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación"
    )

    class Meta:
        verbose_name = "Espacio Curricular"
        verbose_name_plural = "Espacios Curriculares"
        ordering = ["carrera", "anio", "nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre} ({self.carrera} - {self.anio}° Año)"


class CargoDocente(models.Model):
    """
    Designación de un docente en un espacio curricular y su distribución
    semanal de horas cátedra por día hábil.
    """

    SITUACION_CHOICES = [
        ("TITULAR", "Titular"),
        ("INTERINO", "Interino"),
        ("SUPLENTE", "Suplente"),
    ]

    docente = models.ForeignKey(
        Docente,
        on_delete=models.PROTECT,
        related_name="cargos",
        verbose_name="Docente",
    )
    materia = models.ForeignKey(
        EspacioCurricular,
        on_delete=models.PROTECT,
        related_name="cargos",
        verbose_name="Espacio Curricular",
    )
    situacion_revista = models.CharField(
        max_length=15,
        choices=SITUACION_CHOICES,
        default="INTERINO",
        verbose_name="Situación de Revista",
    )
    horas_lunes = models.PositiveSmallIntegerField(
        default=0, verbose_name="Horas Lunes"
    )
    horas_martes = models.PositiveSmallIntegerField(
        default=0, verbose_name="Horas Martes"
    )
    horas_miercoles = models.PositiveSmallIntegerField(
        default=0, verbose_name="Horas Miércoles"
    )
    horas_jueves = models.PositiveSmallIntegerField(
        default=0, verbose_name="Horas Jueves"
    )
    horas_viernes = models.PositiveSmallIntegerField(
        default=0, verbose_name="Horas Viernes"
    )
    resolucion = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Resolución de Designación",
    )
    fecha_alta = models.DateField(
        blank=True, null=True, verbose_name="Fecha de Alta"
    )

    class Meta:
        verbose_name = "Cargo Docente"
        verbose_name_plural = "Cargos Docentes"
        ordering = ["docente__apellido", "materia__nombre"]

    def __str__(self):
        return (
            f"{self.docente.nombre_completo} en {self.materia.nombre} "
            f"({self.get_situacion_revista_display()})"
        )

    @property
    def total_horas_semanales(self):
        """Retorna la suma total de horas cátedra asignadas de lunes a viernes."""
        return (
            self.horas_lunes
            + self.horas_martes
            + self.horas_miercoles
            + self.horas_jueves
            + self.horas_viernes
        )

    def get_horas_dia(self, weekday):
        """
        Retorna las horas cátedra correspondientes al día de la semana.
        0: Lunes, 1: Martes, 2: Miércoles, 3: Jueves, 4: Viernes.
        """
        dias_map = {
            0: self.horas_lunes,
            1: self.horas_martes,
            2: self.horas_miercoles,
            3: self.horas_jueves,
            4: self.horas_viernes,
        }
        return dias_map.get(weekday, 0)


class TipoLicencia(models.Model):
    """
    Régimen legal de licencias docentes según el estatuto o reglamentación
    institucional del IESETyFP.
    """

    codigo = models.CharField(
        max_length=20, unique=True, verbose_name="Código"
    )
    articulo = models.CharField(
        max_length=50, verbose_name="Artículo Legal (ej: 340-A)"
    )
    descripcion = models.CharField(
        max_length=255, verbose_name="Descripción"
    )
    goce_haberes = models.BooleanField(
        default=True, verbose_name="Goce de Haberes"
    )
    tope_anual = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Tope Anual (Días)",
        help_text="Dejar en blanco si no tiene tope anual fijado.",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Tipo de Licencia"
        verbose_name_plural = "Tipos de Licencias"
        ordering = ["codigo"]

    def __str__(self):
        goce = "C/Goce" if self.goce_haberes else "S/Goce"
        return f"{self.articulo} ({self.codigo}) - {self.descripcion} [{goce}]"


class RegistroAsistencia(models.Model):
    """
    Parte diario de novedades y control de asistencia docente de Bedelía.
    """

    ESTADO_CHOICES = [
        ("PRESENTE", "Presente"),
        ("AUSENTE", "Ausente"),
        ("LICENCIA", "Licencia"),
        ("JUSTIFICADO", "Justificado"),
    ]

    docente = models.ForeignKey(
        Docente,
        on_delete=models.CASCADE,
        related_name="asistencias",
        verbose_name="Docente",
    )
    fecha = models.DateField(verbose_name="Fecha")
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default="PRESENTE",
        verbose_name="Estado de Asistencia",
    )
    tipo_licencia = models.ForeignKey(
        TipoLicencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_asistencia",
        verbose_name="Tipo de Licencia",
    )
    observaciones = models.TextField(
        blank=True, verbose_name="Observaciones / Justificación"
    )
    creado_el = models.DateTimeField(
        auto_now_add=True, verbose_name="Registrado el"
    )

    class Meta:
        verbose_name = "Registro de Asistencia"
        verbose_name_plural = "Registros de Asistencia"
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

    def horas_afectadas(self):
        """
        Calcula las horas cátedra que el docente debía dictar en la fecha registrada
        según la distribución de sus cargos activos para ese día de la semana.
        """
        weekday = self.fecha.weekday()
        return sum(
            cargo.get_horas_dia(weekday) for cargo in self.docente.cargos.all()
        )

    def __str__(self):
        docente = self.docente.nombre_completo
        return f"{self.fecha} - {docente}: {self.get_estado_display()}"
