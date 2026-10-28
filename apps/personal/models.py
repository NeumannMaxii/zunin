"""
Modelos del módulo de Personal y Designaciones para el IESETyFP.
Gestiona el cuerpo docente, carreras, espacios curriculares y cargos asignados.
"""

import datetime
import re
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
        db_table = "gestion_asistencia_carrera"

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
        db_table = "gestion_asistencia_cargocatalogo"

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
        db_table = "gestion_asistencia_tipoautorizacion"

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
        db_table = "gestion_asistencia_docente"

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

    def obtener_resumen_inasistencias(self, anio=None, limite_reglamentario=10):
        """
        RF-18: Calcula el acumulado anual de inasistencias ('I' o 'INA')
        y permisos ('P' o 'PERM') para el docente, retornando los totales
        y el nivel de alerta reglamentario ('NORMAL', 'PRECAUCION', 'CRITICO').
        """
        if anio is None:
            anio = timezone.now().year if timezone.now() else 2026

        registros = self.asistencias.filter(fecha__year=anio)

        inasistencias_qs = registros.filter(
            models.Q(marca_diaria__in=["I", "INA"])
            | models.Q(estado="AUSENTE")
            | models.Q(tipo_licencia__categoria="INASISTENCIA")
        ).exclude(estado="PRESENTE", marca_diaria="PR").distinct()
        total_inasistencias = inasistencias_qs.count()

        permisos_qs = (
            registros.filter(
                models.Q(
                    marca_diaria__in=["P", "PERM"],
                    estado__in=["JUSTIFICADO", "LICENCIA"],
                )
                | models.Q(tipo_licencia__categoria="PERMISO")
            )
            .exclude(id__in=inasistencias_qs.values_list("id", flat=True))
            .distinct()
        )
        total_permisos = permisos_qs.count()

        total_acumulado = total_inasistencias + total_permisos
        restantes = max(0, limite_reglamentario - total_acumulado)

        if total_acumulado >= limite_reglamentario:
            nivel_alerta = "CRITICO"
        elif total_acumulado >= (limite_reglamentario * 0.7):
            nivel_alerta = "PRECAUCION"
        else:
            nivel_alerta = "NORMAL"

        return {
            "anio": anio,
            "inasistencias": total_inasistencias,
            "permisos": total_permisos,
            "total": total_acumulado,
            "total_acumulado": total_acumulado,
            "limite": limite_reglamentario,
            "limite_reglamentario": limite_reglamentario,
            "restantes": restantes,
            "nivel_alerta": nivel_alerta,
            "alerta": nivel_alerta,
        }

    @property
    def renglones_planilla(self):
        return self.renglones_mensuales


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
        db_table = "gestion_asistencia_espaciocurricular"

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
        db_table = "gestion_asistencia_cargodocente"

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

    def save(self, *args, **kwargs):
        """
        Normaliza automáticamente el campo situacion_revista a códigos
        estándar de tres letras: TITULAR -> TIT, INTERINO -> INT, SUPLENTE -> SUP.
        """
        normalizaciones = {
            "TITULAR": "TIT",
            "INTERINO": "INT",
            "SUPLENTE": "SUP",
        }
        if self.situacion_revista:
            revista_upper = str(self.situacion_revista).strip().upper()
            if revista_upper in normalizaciones:
                self.situacion_revista = normalizaciones[revista_upper]
        super().save(*args, **kwargs)

    def es_designacion_vigente(self, fecha_referencia=None):
        """
        Retorna True si activo=True y la designación se encuentra vigente.
        Prioriza la validación de fecha_baja: si existe y es menor a
        fecha_referencia, retorna False. Si fecha_baja es nula o una fecha futura,
        utiliza hasta_texto como validación secundaria (fallback).
        """
        if not self.activo:
            return False
        if fecha_referencia is None:
            fecha_referencia = timezone.now().date()
        elif isinstance(fecha_referencia, datetime.datetime):
            fecha_referencia = fecha_referencia.date()

        if self.fecha_baja is not None and self.fecha_baja < fecha_referencia:
            return False

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

    def obtener_horas_en_fecha(self, fecha_obj):
        """
        RF-13: Retorna la cantidad de horas cátedra asignadas en la fecha dada.
        Evalúa el día de la semana (0: Lunes .. 4: Viernes).
        Toma horas_lunes..horas_viernes o evalúa dia_lunes..dia_viernes
        (extrayendo el número o asignando 1 si contiene 'X').
        """
        weekday = fecha_obj.weekday()
        if weekday >= 5:
            return 0

        hs = self.get_horas_dia(weekday)
        if hs > 0:
            return hs

        texto_map = {
            0: self.dia_lunes,
            1: self.dia_martes,
            2: self.dia_miercoles,
            3: self.dia_jueves,
            4: self.dia_viernes,
        }
        txt = (texto_map.get(weekday) or "").strip().upper()
        if "X" in txt:
            return 1

        match = re.search(r"\d+", txt)
        if match:
            return int(match.group())

        return 0

    @property
    def renglones_planilla(self):
        return self.renglones_mensuales
