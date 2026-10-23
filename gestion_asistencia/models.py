"""
Modelos relacionales para el Sistema de Bedelía del IESETyFP.
Gestiona el cuerpo docente, espacios curriculares, asignación de cargos,
catálogos de referencia, licencias y el registro diario de asistencia.
"""

import datetime
import re
import unicodedata
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
        ("IL-01", "IL-01 - Licencias por Enfermedad (Hojas 1-2)"),
        (
            "IL-02",
            "IL-02 - Inasistencias, Permisos y Licencias Especiales (Hojas 3-6)",
        ),
        ("DL-01", "DL-01 - Licencias por Enfermedad (Compatibilidad)"),
        ("DL-02", "DL-02 - Inasistencias y Permisos (Compatibilidad)"),
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
        default="IL-02",
        verbose_name="Cuadro Mensual",
    )
    hoja_pdf = models.CharField(
        max_length=20,
        blank=True,
        default="1-2",
        help_text="Hoja del catálogo PDF oficial: 1-2 para IL-01, 3-6 para IL-02",
        verbose_name="Hoja en PDF Oficial",
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

    @classmethod
    def autocompletar_por_articulo(cls, articulo_str):
        """
        RF-15, RN-04, RN-05: Recibe una referencia de artículo estatutario
        y retorna un diccionario con el código (COD.LIC.), descripción y
        cuadro mensual ('IL-01' o 'IL-02').
        """
        if not articulo_str:
            return {
                "codigo": "",
                "descripcion": "",
                "cuadro": "IL-02",
            }

        art_clean = str(articulo_str).strip()
        coincidencia = (
            cls.objects.filter(articulo__iexact=art_clean).first()
            or cls.objects.filter(articulo__icontains=art_clean).first()
            or cls.objects.filter(codigo__iexact=art_clean).first()
        )
        if coincidencia:
            cuadro = (
                "IL-01"
                if coincidencia.cuadro_mensual in ["IL-01", "DL-01"]
                else "IL-02"
            )
            return {
                "codigo": coincidencia.codigo,
                "descripcion": coincidencia.descripcion,
                "cuadro": cuadro,
            }

        norm = (
            art_clean.upper()
            .replace("ART.", "")
            .replace("ART", "")
            .replace("ARTÍCULO", "")
            .replace("ARTICULO", "")
            .replace(" ", "")
            .replace("_", "-")
        )

        catalogo = {
            "340": {
                "codigo": "LIC-340",
                "descripcion": "Licencia por Enfermedad",
                "cuadro": "IL-01",
            },
            "340-A": {
                "codigo": "LIC-340A",
                "descripcion": "Enfermedad de Corto Tratamiento",
                "cuadro": "IL-01",
            },
            "340A": {
                "codigo": "LIC-340A",
                "descripcion": "Enfermedad de Corto Tratamiento",
                "cuadro": "IL-01",
            },
            "340-B": {
                "codigo": "LIC-340B",
                "descripcion": "Afección de Largo Tratamiento",
                "cuadro": "IL-01",
            },
            "340B": {
                "codigo": "LIC-340B",
                "descripcion": "Afección de Largo Tratamiento",
                "cuadro": "IL-01",
            },
            "340-C": {
                "codigo": "LIC-340C",
                "descripcion": (
                    "Accidente de Trabajo / Enfermedad Profesional"
                ),
                "cuadro": "IL-01",
            },
            "340C": {
                "codigo": "LIC-340C",
                "descripcion": (
                    "Accidente de Trabajo / Enfermedad Profesional"
                ),
                "cuadro": "IL-01",
            },
            "340-D": {
                "codigo": "LIC-340D",
                "descripcion": "Atención Familiar Enfermo",
                "cuadro": "IL-01",
            },
            "340D": {
                "codigo": "LIC-340D",
                "descripcion": "Atención Familiar Enfermo",
                "cuadro": "IL-01",
            },
            "341": {
                "codigo": "LIC-341",
                "descripcion": "Licencia por Maternidad",
                "cuadro": "IL-02",
            },
            "342": {
                "codigo": "LIC-342",
                "descripcion": "Nacimiento de Hijo / Adopción",
                "cuadro": "IL-02",
            },
            "343": {
                "codigo": "LIC-343",
                "descripcion": "Matrimonio",
                "cuadro": "IL-02",
            },
            "344": {
                "codigo": "LIC-344",
                "descripcion": "Duelo Familiar",
                "cuadro": "IL-02",
            },
            "345": {
                "codigo": "LIC-345",
                "descripcion": "Exámenes o Perfeccionamiento Docente",
                "cuadro": "IL-02",
            },
            "346": {
                "codigo": "LIC-346",
                "descripcion": "Razones Particulares",
                "cuadro": "IL-02",
            },
            "347": {
                "codigo": "LIC-347",
                "descripcion": "Permiso Especial",
                "cuadro": "IL-02",
            },
        }

        if norm in catalogo:
            return catalogo[norm].copy()

        es_enfermedad = "340" in norm or "ENF" in norm or "SALUD" in norm
        cuadro_inf = "IL-01" if es_enfermedad else "IL-02"
        cod_lic = f"LIC-{norm}" if norm else "LIC-ESP"
        return {
            "codigo": cod_lic,
            "descripcion": f"Licencia Art. {art_clean}",
            "cuadro": cuadro_inf,
        }


def autocompletar_por_articulo(articulo_str):
    """
    Helper funcional para autocompletar código, descripción y cuadro
    según la referencia estatutaria del artículo.
    """
    return TipoLicencia.autocompletar_por_articulo(articulo_str)


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


class RenglonPlanillaMensual(models.Model):
    """
    Renglón consolidado de la planilla mensual de novedades docentes (IL-01 / IL-02).
    Desglosa por materia y horas las licencias e inasistencias de cada docente
    para la asignación de instrumentos legales correlativos
    (RF-12 a RF-16, RN-10 y RN-11).
    """

    CUADRO_CHOICES = [
        ("IL-01", "IL-01 - Enfermedad"),
        ("IL-02", "IL-02 - Otras Causales"),
    ]
    TIPO_INSTRUMENTO_CHOICES = [
        ("DISPOSICION", "Disposición Interna IESETyFP"),
        ("RESOLUCION", "Resolución Ministerial M.E.C.C.y T."),
    ]

    docente = models.ForeignKey(
        Docente,
        on_delete=models.CASCADE,
        related_name="renglones_mensuales",
        verbose_name="Docente",
    )
    cargo = models.ForeignKey(
        CargoDocente,
        on_delete=models.CASCADE,
        related_name="renglones_mensuales",
        help_text="RF-12: Desglose obligatorio por materia/cargo",
        verbose_name="Cargo / Materia",
    )
    tipo_licencia = models.ForeignKey(
        TipoLicencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renglones_mensuales",
        verbose_name="Tipo de Licencia",
    )
    cuadro = models.CharField(
        max_length=10,
        choices=CUADRO_CHOICES,
        default="IL-02",
        verbose_name="Cuadro Mensual",
    )
    mes = models.PositiveSmallIntegerField(
        verbose_name="Mes",
    )
    anio = models.PositiveIntegerField(
        default=2026,
        verbose_name="Año",
    )
    oficina = models.CharField(
        max_length=20,
        default="1452",
        verbose_name="Oficina",
    )
    desde = models.DateField(
        verbose_name="Fecha Desde",
    )
    hasta = models.DateField(
        verbose_name="Fecha Hasta",
    )
    horas_afectadas = models.PositiveIntegerField(
        default=0,
        help_text=(
            "RF-13: Horas cátedra que correspondía dictar en los días afectados"
        ),
        verbose_name="Horas Afectadas",
    )
    marca_origen = models.CharField(
        max_length=15,
        default="I",
        verbose_name="Marca de Origen",
    )
    tipo_instrumento = models.CharField(
        max_length=20,
        choices=TIPO_INSTRUMENTO_CHOICES,
        default="DISPOSICION",
        verbose_name="Tipo de Instrumento",
    )
    numero_instrumento = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=(
            "RN-11: Único número de disposición para todas las materias "
            "afectadas del docente en el mismo bloque"
        ),
        verbose_name="Número de Instrumento",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renglones_creados",
        verbose_name="Creado por",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renglones_modificados",
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

    @property
    def creado_el(self):
        return self.creado_en

    @property
    def modificado_el(self):
        return self.actualizado_en

    class Meta:
        verbose_name = "Renglón de Planilla Mensual"
        verbose_name_plural = "Renglones de Planilla Mensual"
        ordering = ["anio", "mes", "numero_instrumento", "docente__apellido"]

    def __str__(self):
        return (
            f"[{self.cuadro}] {self.docente.nombre_completo} - "
            f"{self.cargo} ({self.horas_afectadas} hs) - {self.numero_instrumento}"
        )

    @classmethod
    def generar_planilla_mes(cls, mes, anio, usuario=None):
        """
        RF-12 a RF-16, RN-10 y RN-11:
        Genera la planilla mensual consolidada desglosada por materia y horas.
        1. Agrupa los registros diarios continuos por docente en bloques temporales.
        2. Desglosa un renglón por cada cargo/materia que el docente debía dictar
           esos días, acumulando las horas cátedra correspondientes.
        3. Asigna un único N° de Disposición correlativo por docente/bloque,
           ordenando alfabéticamente los agentes por apellido.
        """
        cls.objects.filter(mes=mes, anio=anio).delete()

        docentes_qs = (
            Docente.objects.filter(
                asistencias__fecha__year=anio,
                asistencias__fecha__month=mes,
            )
            .filter(
                models.Q(
                    asistencias__estado__in=[
                        "AUSENTE",
                        "LICENCIA",
                        "JUSTIFICADO",
                    ]
                )
                | models.Q(
                    asistencias__marca_diaria__in=[
                        "I",
                        "INA",
                        "LIC",
                        "LIC.",
                        "LT",
                        "PERM",
                    ]
                )
                | (
                    models.Q(asistencias__marca_diaria="P")
                    & ~models.Q(asistencias__estado="PRESENTE")
                )
            )
            .distinct()
        )

        def clave_ordenamiento(doc):
            norm_apellido = (
                unicodedata.normalize("NFKD", doc.apellido or "")
                .encode("ASCII", "ignore")
                .decode("utf-8")
                .lower()
            )
            norm_nombre = (
                unicodedata.normalize("NFKD", doc.nombre or "")
                .encode("ASCII", "ignore")
                .decode("utf-8")
                .lower()
            )
            return (norm_apellido, norm_nombre, doc.dni or "")

        docentes = list(docentes_qs)
        docentes.sort(key=clave_ordenamiento)

        correlativo = 1
        renglones_creados = []

        for docente in docentes:
            asistencias_qs = (
                docente.asistencias.filter(
                    fecha__year=anio,
                    fecha__month=mes,
                )
                .filter(
                    models.Q(
                        estado__in=["AUSENTE", "LICENCIA", "JUSTIFICADO"]
                    )
                    | models.Q(
                        marca_diaria__in=[
                            "I",
                            "INA",
                            "LIC",
                            "LIC.",
                            "LT",
                            "PERM",
                        ]
                    )
                    | (
                        models.Q(marca_diaria="P")
                        & ~models.Q(estado="PRESENTE")
                    )
                )
                .order_by("fecha")
            )

            bloques = []
            current_block = None

            for reg in asistencias_qs:
                r_desde = reg.fecha
                r_hasta = reg.fecha_hasta if reg.fecha_hasta else reg.fecha
                tipo_lic = reg.tipo_licencia
                cuadro = (
                    "IL-01"
                    if (
                        tipo_lic
                        and tipo_lic.cuadro_mensual in ["IL-01", "DL-01"]
                    )
                    else "IL-02"
                )

                if current_block is None:
                    current_block = {
                        "desde": r_desde,
                        "hasta": r_hasta,
                        "tipo_licencia": tipo_lic,
                        "cuadro": cuadro,
                        "marca_origen": reg.marca_diaria,
                        "cargo_fijado": reg.cargo,
                        "registros": [reg],
                    }
                else:
                    es_compatible = (
                        current_block["tipo_licencia"] == tipo_lic
                        and current_block["cuadro"] == cuadro
                        and current_block["marca_origen"] == reg.marca_diaria
                    )

                    es_contiguo = False
                    if (
                        r_desde
                        <= current_block["hasta"] + datetime.timedelta(days=1)
                    ):
                        es_contiguo = True
                    else:
                        dia = current_block["hasta"] + datetime.timedelta(
                            days=1
                        )
                        todos_no_habiles = True
                        while dia < r_desde:
                            if (
                                dia.weekday() < 5
                                and not DiaNoLaborable.objects.filter(
                                    fecha=dia
                                ).exists()
                            ):
                                todos_no_habiles = False
                                break
                            dia += datetime.timedelta(days=1)
                        if todos_no_habiles:
                            es_contiguo = True

                    if es_compatible and es_contiguo:
                        if r_hasta > current_block["hasta"]:
                            current_block["hasta"] = r_hasta
                        if reg.cargo and not current_block["cargo_fijado"]:
                            current_block["cargo_fijado"] = reg.cargo
                        current_block["registros"].append(reg)
                    else:
                        bloques.append(current_block)
                        current_block = {
                            "desde": r_desde,
                            "hasta": r_hasta,
                            "tipo_licencia": tipo_lic,
                            "cuadro": cuadro,
                            "marca_origen": reg.marca_diaria,
                            "cargo_fijado": reg.cargo,
                            "registros": [reg],
                        }

            if current_block is not None:
                bloques.append(current_block)

            for bloque in bloques:
                num_disp = f"{correlativo:03d}/{anio}"
                correlativo += 1

                for reg in bloque["registros"]:
                    reg.numero_disposicion = num_disp
                    reg.save(update_fields=["numero_disposicion"])

                if bloque["cargo_fijado"]:
                    cargos_a_evaluar = [bloque["cargo_fijado"]]
                else:
                    cargos_a_evaluar = list(
                        docente.cargos.filter(activo=True)
                    )

                cargos_con_horas = []
                for cargo in cargos_a_evaluar:
                    total_horas = 0
                    dia_cursor = bloque["desde"]
                    while dia_cursor <= bloque["hasta"]:
                        total_horas += cargo.obtener_horas_en_fecha(dia_cursor)
                        dia_cursor += datetime.timedelta(days=1)

                    if total_horas > 0:
                        cargos_con_horas.append((cargo, total_horas))

                if not cargos_con_horas and cargos_a_evaluar:
                    cargos_con_horas.append((cargos_a_evaluar[0], 0))

                for cargo, horas in cargos_con_horas:
                    renglon = cls.objects.create(
                        docente=docente,
                        cargo=cargo,
                        tipo_licencia=bloque["tipo_licencia"],
                        cuadro=bloque["cuadro"],
                        mes=mes,
                        anio=anio,
                        oficina="1452",
                        desde=bloque["desde"],
                        hasta=bloque["hasta"],
                        horas_afectadas=horas,
                        marca_origen=bloque["marca_origen"],
                        tipo_instrumento="DISPOSICION",
                        numero_instrumento=num_disp,
                        creado_por=usuario,
                        modificado_por=usuario,
                    )
                    renglones_creados.append(renglon)

        return renglones_creados
