"""
Modelos relacionales para el Sistema de Bedelía del IESETyFP.
Gestiona el cuerpo docente, espacios curriculares, asignación de cargos,
catálogos de referencia, licencias y el registro diario de asistencia.
"""

import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Carrera(models.Model):
    """Carrera o tecnicatura formativa dictada en el IESETyFP."""

    codigo = models.CharField(
        max_length=20, unique=True, verbose_name="Código"
    )
    nombre = models.CharField(
        max_length=150, verbose_name="Nombre de la Carrera"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Carrera"
        verbose_name_plural = "Carreras"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class CargoCatalogo(models.Model):
    """Catálogo administrable de cargos o funciones docentes."""

    codigo = models.CharField(
        max_length=30, unique=True, verbose_name="Código de Cargo"
    )
    descripcion = models.CharField(
        max_length=150, verbose_name="Descripción"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Cargo de Catálogo"
        verbose_name_plural = "Cargos de Catálogo"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class TipoAutorizacion(models.Model):
    """Tipo de instrumento administrativo de designación o cobertura."""

    nombre = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Tipo de Autorización",
        help_text="Ej: RESOLUCIÓN, DISPOSICIÓN",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Tipo de Autorización"
        verbose_name_plural = "Tipos de Autorizaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Docente(models.Model):
    """Información filiatoria y de contacto del personal docente del IESETyFP."""

    SEXO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("X", "No binario"),
    ]

    dni = models.CharField(max_length=20, unique=True, verbose_name="DNI")
    tipo_documento = models.CharField(
        max_length=10,
        default="DNI",
        blank=True,
        null=True,
        verbose_name="Tipo de Documento",
    )
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        default="M",
        verbose_name="Sexo",
    )
    fecha_nacimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Nacimiento",
    )
    estado_civil = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Estado Civil",
    )
    nacionalidad = models.CharField(
        max_length=50,
        default="Argentina",
        blank=True,
        null=True,
        verbose_name="Nacionalidad",
    )
    cuil_dgi = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="CUIL / N° Inscripción DGI",
    )
    inscripcion_dgr = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="N° Inscripción DGR",
    )
    domicilio_calle = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Calle y N° / Nomenclatura",
    )
    barrio = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Barrio",
    )
    localidad = models.CharField(
        max_length=100,
        default="Resistencia",
        blank=True,
        null=True,
        verbose_name="Localidad",
    )
    codigo_postal = models.CharField(
        max_length=10,
        default="3500",
        blank=True,
        null=True,
        verbose_name="Código Postal",
    )
    provincia = models.CharField(
        max_length=50,
        default="Chaco",
        blank=True,
        null=True,
        verbose_name="Provincia",
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
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="docentes_creados",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="docentes_modificados",
        verbose_name="Modificado por",
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

    COMISION_CHOICES = [
        ("UNICA", "Única"),
        ("A", "Comisión A"),
        ("B", "Comisión B"),
        ("C", "Comisión C"),
    ]
    TURNO_CHOICES = [
        ("MANANA", "Mañana"),
        ("TARDE", "Tarde"),
        ("NOCHE", "Noche"),
    ]
    REGIMEN_CHOICES = [
        ("ANUAL", "Anual"),
        ("CUAT_1", "1° Cuatrimestre"),
        ("CUAT_2", "2° Cuatrimestre"),
    ]

    codigo = models.CharField(
        max_length=30, unique=True, verbose_name="Código de Espacio"
    )
    nombre = models.CharField(
        max_length=150, verbose_name="Nombre de la Asignatura"
    )
    carrera = models.CharField(max_length=150, verbose_name="Carrera")
    anio = models.PositiveSmallIntegerField(verbose_name="Año de la Carrera")
    comision = models.CharField(
        max_length=10,
        choices=COMISION_CHOICES,
        default="UNICA",
        verbose_name="Comisión",
    )
    turno = models.CharField(
        max_length=10,
        choices=TURNO_CHOICES,
        default="NOCHE",
        verbose_name="Turno",
    )
    regimen = models.CharField(
        max_length=10,
        choices=REGIMEN_CHOICES,
        default="ANUAL",
        verbose_name="Régimen de Cursado",
    )
    aula = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Aula",
    )
    plan_estudio = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Plan de Estudio",
    )
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
    Designación de un docente en un espacio curricular o cargo institucional
    y su distribución semanal de horas cátedra por día hábil.
    """

    SITUACION_CHOICES = [
        ("TITULAR", "Titular"),
        ("INTERINO", "Interino"),
        ("SUPLENTE", "Suplente"),
        ("TIT", "Titular (TIT)"),
        ("INT", "Interino (INT)"),
        ("SUP", "Suplente (SUP)"),
    ]
    TIPO_CARGO_CHOICES = [
        ("HORAS_CATEDRA", "Horas Cátedra"),
        ("CARGO_ADM", "Cargo Administrativo / Bedel"),
    ]

    docente = models.ForeignKey(
        Docente,
        on_delete=models.PROTECT,
        related_name="cargos",
        verbose_name="Docente",
    )
    tipo_cargo = models.CharField(
        max_length=20,
        choices=TIPO_CARGO_CHOICES,
        default="HORAS_CATEDRA",
        verbose_name="Tipo de Cargo",
    )
    codigo_cargo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Código de Cargo",
    )
    codigo_motivo = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Código de Motivo",
    )
    carrera_ref = models.ForeignKey(
        Carrera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargos",
        verbose_name="Carrera",
    )
    cargo_catalogo = models.ForeignKey(
        CargoCatalogo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargos",
        verbose_name="Cargo de Catálogo",
    )
    tipo_autorizacion = models.ForeignKey(
        TipoAutorizacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargos",
        verbose_name="Tipo de Autorización",
    )
    materia = models.ForeignKey(
        EspacioCurricular,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cargos",
        verbose_name="Espacio Curricular",
    )
    situacion_revista = models.CharField(
        max_length=15,
        choices=SITUACION_CHOICES,
        default="INTERINO",
        verbose_name="Situación de Revista",
    )
    docente_reemplazado = models.ForeignKey(
        Docente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suplencias_recibidas",
        verbose_name="Docente Reemplazado",
    )
    numero_autorizacion = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número de Autorización",
    )
    anio_autorizacion = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Año de Autorización",
    )
    organismo_emisor = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Organismo Emisor",
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
    dia_lunes = models.CharField(
        max_length=15, blank=True, default="", verbose_name="Día Lunes (Texto)"
    )
    dia_martes = models.CharField(
        max_length=15, blank=True, default="", verbose_name="Día Martes (Texto)"
    )
    dia_miercoles = models.CharField(
        max_length=15,
        blank=True,
        default="",
        verbose_name="Día Miércoles (Texto)",
    )
    dia_jueves = models.CharField(
        max_length=15, blank=True, default="", verbose_name="Día Jueves (Texto)"
    )
    dia_viernes = models.CharField(
        max_length=15,
        blank=True,
        default="",
        verbose_name="Día Viernes (Texto)",
    )
    desde_texto = models.CharField(
        max_length=50,
        blank=True,
        default="SIN INICIO",
        verbose_name="Desde (Texto)",
    )
    hasta_texto = models.CharField(
        max_length=50,
        blank=True,
        default="SIN TERMINO",
        verbose_name="Hasta (Texto)",
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
    fecha_baja = models.DateField(
        blank=True, null=True, verbose_name="Fecha de Baja"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    observaciones = models.TextField(
        blank=True, null=True, verbose_name="Observaciones"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargos_creados",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargos_modificados",
        verbose_name="Modificado por",
    )

    class Meta:
        verbose_name = "Cargo Docente"
        verbose_name_plural = "Cargos Docentes"
        ordering = ["docente__apellido", "docente__nombre"]

    def __str__(self):
        materia_display = (
            self.materia.nombre
            if self.materia
            else (
                self.cargo_catalogo.descripcion
                if self.cargo_catalogo
                else self.get_tipo_cargo_display()
            )
        )
        return (
            f"{self.docente.nombre_completo} en {materia_display} "
            f"({self.get_situacion_revista_display()})"
        )

    def clean(self):
        super().clean()
        if self.situacion_revista == "SUPLENTE" and not self.docente_reemplazado:
            raise ValidationError(
                {
                    "docente_reemplazado": (
                        "Debe especificar el docente reemplazado para una suplencia "
                        "según Formulario DP-01"
                    )
                }
            )

    def es_designacion_vigente(self, fecha_referencia=None):
        """
        Retorna True si activo=True y hasta_texto contiene 'SIN TERMINO'
        o si al parsear hasta_texto como fecha es >= fecha_referencia.
        """
        if not self.activo:
            return False
        if fecha_referencia is None:
            fecha_referencia = timezone.now().date()
        elif isinstance(fecha_referencia, datetime.datetime):
            fecha_referencia = fecha_referencia.date()

        texto = (self.hasta_texto or "").strip().upper()
        if "SIN TERMINO" in texto or "SIN TÉRMINO" in texto or not texto:
            return True

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                f_dt = datetime.datetime.strptime(texto, fmt).date()
                return f_dt >= fecha_referencia
            except ValueError:
                continue
        return False

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

    CATEGORIA_CHOICES = [
        ("LICENCIA", "Licencia"),
        ("PERMISO", "Permiso"),
        ("INASISTENCIA", "Inasistencia"),
    ]
    FORMA_PAGO_CHOICES = [
        ("CON_GOCE", "Con Goce de haberes"),
        ("SIN_GOCE", "Sin goce de haberes"),
        ("CINCUENTA_PORCIENTO", "Con 50% de haberes"),
    ]
    CUADRO_CHOICES = [
        ("DL-01", "DL-01 - Licencias por Enfermedad"),
        ("DL-02", "DL-02 - Inasistencias, Permisos y Otras Licencias"),
    ]

    codigo = models.CharField(
        max_length=20, unique=True, verbose_name="Código"
    )
    articulo = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Artículo Legal (ej: 340-A)",
    )
    descripcion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Descripción",
    )
    categoria = models.CharField(
        max_length=15,
        choices=CATEGORIA_CHOICES,
        default="LICENCIA",
        verbose_name="Categoría",
    )
    forma_pago = models.CharField(
        max_length=25,
        choices=FORMA_PAGO_CHOICES,
        default="CON_GOCE",
        verbose_name="Forma de Pago",
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
    situacion_revista_aplicable = models.CharField(
        max_length=50,
        blank=True,
        default="TIT,INT,SUP",
        help_text="Situaciones de revista elegibles",
        verbose_name="Situación de Revista Aplicable",
    )
    tipo_novedad_excel = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Tipo según catálogo",
    )
    cantidad_duracion = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Cantidad / Duración permitida",
    )
    cuadro_mensual = models.CharField(
        max_length=10,
        choices=CUADRO_CHOICES,
        default="DL-02",
        verbose_name="Cuadro Mensual",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tipos_licencia_creados",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tipos_licencia_modificados",
        verbose_name="Modificado por",
    )

    class Meta:
        verbose_name = "Tipo de Licencia"
        verbose_name_plural = "Tipos de Licencias"
        ordering = ["codigo"]

    def __str__(self):
        goce = "C/Goce" if self.goce_haberes else "S/Goce"
        art = f"{self.articulo} " if self.articulo else ""
        return f"{art}({self.codigo}) - {self.descripcion} [{goce}]".strip()

    def save(self, *args, **kwargs):
        if not self.goce_haberes and self.forma_pago == "CON_GOCE":
            self.forma_pago = "SIN_GOCE"
        else:
            self.goce_haberes = (self.forma_pago == "CON_GOCE")
        super().save(*args, **kwargs)


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

    def __str__(self):
        return f"{self.fecha} - {self.get_tipo_display()}: {self.descripcion}"


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
    cargo = models.ForeignKey(
        CargoDocente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias",
        verbose_name="Cargo / Materia",
    )
    fecha = models.DateField(verbose_name="Fecha")
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
        blank=True,
        default="P",
        help_text="Marca en planilla: P, LIC., LT, INA, PERM, etc.",
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
        TipoLicencia,
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
    creado_el = models.DateTimeField(
        auto_now_add=True, verbose_name="Registrado el"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias_creadas",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias_modificadas",
        verbose_name="Modificado por",
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
        # RN-06: Las inasistencias solamente pueden ser por un día.
        if self.fecha_hasta and self.fecha_hasta != self.fecha:
            es_inasistencia = (
                self.estado == "AUSENTE"
                or self.marca_diaria == "INA"
                or (
                    self.tipo_licencia
                    and self.tipo_licencia.categoria == "INASISTENCIA"
                )
            )
            if es_inasistencia:
                raise ValidationError(
                    "RN-06: Las inasistencias solamente pueden ser por un día."
                )

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
