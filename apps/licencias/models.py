"""
Modelos del módulo de Licencias y Planillas Mensuales para el IESETyFP.
Gestiona el catálogo de licencias estatutarias y la consolidación de novedades.
"""

import datetime
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import AuditoriaModel


class TipoLicencia(models.Model):
    """
    Régimen legal de licencias docentes según el estatuto o reglamentación
    institucional del IESETyFP.
    """

    CATEGORIA_CHOICES = [
        ("Ordinaria", "Ordinaria"),
        ("Extraordinaria", "Extraordinaria"),
        ("Permiso", "Permiso"),
        ("LICENCIA", "Licencia"),
        ("INASISTENCIA", "Inasistencia"),
    ]
    REGIMEN_CHOICES = [
        ("TIT", "Titular (TIT)"),
        ("INT", "Interino (INT)"),
        ("SUP", "Suplente (SUP)"),
    ]
    FORMA_GOCE_CHOICES = [
        ("100%", "100%"),
        ("50%", "50%"),
        ("Sin goce", "Sin goce"),
        ("Escala", "Escala"),
    ]
    UNIDAD_CHOICES = [
        ("Corridos", "Corridos"),
        ("Hábiles", "Hábiles"),
        ("Laborables", "Laborables"),
        ("Horas", "Horas"),
    ]
    PERIODO_TOPE_CHOICES = [
        ("Año calendario", "Año calendario"),
        ("Año escolar", "Año escolar"),
        ("Decenio", "Decenio"),
        ("Sin tope", "Sin tope"),
        ("Hecho", "Hecho"),
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

    UNIDAD_HABILES = "HABILES"
    UNIDAD_CORRIDOS = "CORRIDOS"

    codigo = models.CharField(max_length=30, unique=True, verbose_name="Código")
    regimen = models.CharField(
        max_length=10,
        choices=REGIMEN_CHOICES,
        default="TIT",
        blank=True,
        null=True,
        verbose_name="Régimen",
        help_text="Situación de revista: TIT, INT, SUP",
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
        max_length=30,
        choices=CATEGORIA_CHOICES,
        default="Ordinaria",
        verbose_name="Categoría",
        help_text="Categoría: Ordinaria, Extraordinaria, Permiso",
    )
    forma_goce = models.CharField(
        max_length=20,
        choices=FORMA_GOCE_CHOICES,
        default="100%",
        blank=True,
        null=True,
        verbose_name="Forma de Goce",
        help_text="Forma de goce: 100%, 50%, Sin goce, Escala",
    )
    forma_pago = models.CharField(
        max_length=25,
        choices=FORMA_PAGO_CHOICES,
        default="CON_GOCE",
        verbose_name="Forma de Pago",
    )
    goce_haberes = models.BooleanField(default=True, verbose_name="Goce de Haberes")
    duracion_maxima = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración Máxima",
        help_text="Duración máxima permitida en la unidad especificada.",
    )
    unidad = models.CharField(
        max_length=20,
        choices=UNIDAD_CHOICES,
        default="Corridos",
        blank=True,
        null=True,
        verbose_name="Unidad",
        help_text="Unidad: Corridos, Hábiles, Laborables, Horas",
    )
    periodo_tope = models.CharField(
        max_length=30,
        choices=PERIODO_TOPE_CHOICES,
        default="Año calendario",
        blank=True,
        null=True,
        verbose_name="Período Tope",
        help_text="Período tope: Año calendario, Año escolar, Decenio, Sin tope, Hecho",
    )
    antiguedad_minima_meses = models.PositiveIntegerField(
        default=0,
        verbose_name="Antigüedad Mínima (Meses)",
        help_text="Antigüedad docente mínima requerida en meses.",
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
        """Compatibilidad con referencias previas a creado_el."""
        return self.creado_en

    @property
    def modificado_el(self):
        """Compatibilidad con referencias previas a modificado_el."""
        return self.actualizado_en

    @property
    def unidad_calculo(self):
        """
        Unidad normalizada ('HABILES' o 'CORRIDOS') para el motor de cálculo
        (Ticket 16.2).
        """
        from apps.licencias.calculador import normalizar_unidad

        return normalizar_unidad(tipo_licencia=self)

    def calcular_fechas(self, fecha_desde, dias=None, fecha_hasta=None, feriados=None):
        """
        Calcula fecha de finalización y reintegro según la unidad estatutaria del tipo.
        (Ticket 16.2).
        """
        from apps.licencias.calculador import calcular_fechas_licencia

        return calcular_fechas_licencia(
            fecha_desde=fecha_desde,
            dias=dias,
            fecha_hasta=fecha_hasta,
            tipo_licencia=self,
            feriados=feriados,
        )

    def es_aplicable_a_regimen(self, situacion_revista=None, cargo=None):
        """
        Verifica si este tipo de licencia es aplicable al régimen de revista
        especificado o al régimen del cargo docente (Ticket 17.1).
        """
        from apps.licencias.validaciones import es_regimen_compatible

        return es_regimen_compatible(
            tipo_licencia=self,
            situacion_revista=situacion_revista,
            cargo=cargo,
        )

    def obtener_regimenes_permitidos(self):
        """
        Retorna el conjunto de códigos de régimen ('TIT', 'INT', 'SUP')
        admitidos normativamente para esta licencia (Ticket 17.1).
        """
        from apps.licencias.validaciones import obtener_regimenes_permitidos

        return obtener_regimenes_permitidos(self)

    def obtener_tope_efectivo(self, cargo=None, docente=None, fecha_referencia=None):
        """
        Retorna el tope efectivo y su posible recorte por antigüedad en el
        establecimiento para el docente / cargo (Ticket 17.2).
        """
        from apps.licencias.validaciones import obtener_tope_efectivo_licencia

        return obtener_tope_efectivo_licencia(
            tipo_licencia=self,
            cargo=cargo,
            docente=docente,
            fecha_referencia=fecha_referencia,
        )

    class Meta:
        verbose_name = "Tipo de Licencia"
        verbose_name_plural = "Tipos de Licencias"
        ordering = ["codigo"]
        db_table = "gestion_asistencia_tipolicencia"

    def __str__(self):
        goce = "C/Goce" if self.goce_haberes else "S/Goce"
        art = f"{self.articulo} " if self.articulo else ""
        return f"{art}({self.codigo}) - {self.descripcion} [{goce}]".strip()

    def save(self, *args, **kwargs):
        if self.forma_goce in ["Sin goce", "SIN_GOCE"]:
            self.goce_haberes = False
            self.forma_pago = "SIN_GOCE"
        elif self.forma_goce == "50%":
            self.goce_haberes = True
            self.forma_pago = "CINCUENTA_PORCIENTO"
        elif self.forma_goce in ["100%", "Escala", "ESCALA"]:
            self.goce_haberes = True
            self.forma_pago = "CON_GOCE"
        elif not self.goce_haberes and self.forma_pago == "CON_GOCE":
            self.forma_pago = "SIN_GOCE"
            if not self.forma_goce:
                self.forma_goce = "Sin goce"
        elif self.forma_pago == "CON_GOCE":
            self.goce_haberes = True
            if not self.forma_goce:
                self.forma_goce = "100%"
        elif self.forma_pago == "CINCUENTA_PORCIENTO":
            self.goce_haberes = True
            if not self.forma_goce:
                self.forma_goce = "50%"

        if not self.regimen and self.situacion_revista_aplicable:
            primer_reg = self.situacion_revista_aplicable.split(",")[0].strip()
            self.regimen = primer_reg if primer_reg in ["TIT", "INT", "SUP"] else "TIT"

        if self.duracion_maxima is not None:
            if not self.tope_anual:
                self.tope_anual = self.duracion_maxima
            if not self.cantidad_duracion:
                if self.unidad == "Horas":
                    self.cantidad_duracion = (
                        f"{self.duracion_maxima} hora diaria"
                        if self.duracion_maxima == 1
                        else f"{self.duracion_maxima} horas diarias"
                    )
                elif self.unidad == "Hábiles":
                    self.cantidad_duracion = f"{self.duracion_maxima} días hábiles"
                elif self.unidad == "Laborables":
                    self.cantidad_duracion = f"{self.duracion_maxima} días laborales"
                else:
                    self.cantidad_duracion = f"{self.duracion_maxima} días corridos"

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
                "descripcion": ("Accidente de Trabajo / Enfermedad Profesional"),
                "cuadro": "IL-01",
            },
            "340C": {
                "codigo": "LIC-340C",
                "descripcion": ("Accidente de Trabajo / Enfermedad Profesional"),
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


class RenglonPlanillaQuerySet(models.QuerySet):
    """QuerySet personalizado para RenglonPlanillaMensual (Ticket 10.4)."""

    def vigentes(self):
        """Retorna únicamente los renglones vigentes (desactualizada=False)."""
        return self.filter(desactualizada=False)

    def desactualizados(self):
        """Retorna los renglones desactualizados (desactualizada=True)."""
        return self.filter(desactualizada=True)


class RenglonPlanillaManager(models.Manager.from_queryset(RenglonPlanillaQuerySet)):
    """
    Custom Manager para RenglonPlanillaMensual (Ticket 10.4).
    Permite filtrar renglones vigentes o desactualizados.
    """

    def vigentes(self):
        return self.get_queryset().vigentes()

    def desactualizados(self):
        return self.get_queryset().desactualizados()


class RenglonPlanillaMensual(AuditoriaModel):
    """
    Renglón consolidado de la planilla mensual de novedades docentes (IL-01 / IL-02).
    Desglosa por materia y horas las licencias e inasistencias de cada docente
    para la asignación de instrumentos legales correlativos
    (RF-12 a RF-16, RN-10 y RN-11).
    """

    objects = RenglonPlanillaManager()

    CUADRO_CHOICES = [
        ("IL-01", "IL-01 - Enfermedad"),
        ("IL-02", "IL-02 - Otras Causales"),
    ]
    TIPO_INSTRUMENTO_CHOICES = [
        ("DISPOSICION", "Disposición Interna IESETyFP"),
        ("RESOLUCION", "Resolución Ministerial M.E.C.C.y T."),
    ]

    docente = models.ForeignKey(
        "personal.Docente",
        on_delete=models.PROTECT,
        related_name="renglones_mensuales",
        verbose_name="Docente",
    )
    cargo = models.ForeignKey(
        "personal.CargoDocente",
        on_delete=models.PROTECT,
        related_name="renglones_mensuales",
        help_text="Desglose obligatorio por materia/cargo",
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
        default=getattr(settings, "DEFAULT_OFICINA_CODE", "1452"),
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
        help_text=("Horas cátedra que correspondía dictar en los días afectados"),
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
            "Único número de disposición para todas las materias "
            "afectadas del docente en el mismo bloque"
        ),
        verbose_name="Número de Instrumento",
    )
    desactualizada = models.BooleanField(
        default=False,
        verbose_name="Planilla Desactualizada",
        help_text=(
            "Se marca en True cuando ingresan justificaciones o "
            "novedades posteriores a la emisión inicial de la planilla."
        ),
    )

    class Meta:
        verbose_name = "Renglón de Planilla Mensual"
        verbose_name_plural = "Renglones de Planilla Mensual"
        db_table = "gestion_asistencia_renglonplanillamensual"
        ordering = ["anio", "mes", "numero_instrumento", "docente__apellido"]
        indexes = [
            models.Index(fields=["anio", "mes"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["docente", "cargo", "mes", "anio", "desde", "hasta"],
                condition=models.Q(desactualizada=False),
                name="unique_renglon_docente_cargo_periodo_fechas",
            )
        ]

    def __str__(self):
        return (
            f"[{self.cuadro}] {self.docente.nombre_completo} - "
            f"{self.cargo} ({self.horas_afectadas} hs) - {self.numero_instrumento}"
        )

    @property
    def total_dias(self):
        """Calcula los días calendario abarcados por el renglón."""
        if self.desde and self.hasta:
            return (self.hasta - self.desde).days + 1
        return 1

    @classmethod
    def generar_planilla_mes(cls, mes, anio, usuario=None):
        """
        RF-12 a RF-16, RN-10 y RN-11:
        Genera la planilla mensual consolidada desglosada por materia y horas.
        Delega al servicio especializado en apps.licencias.services.
        """
        from .services import generar_planilla_mes as generar_servicio

        return generar_servicio(mes=mes, anio=anio, usuario=usuario)


class LicenciaOtorgada(AuditoriaModel):
    """
    Registra formalmente las solicitudes y otorgamientos de licencias
    vinculadas a docentes y cargos institucionales (Ticket 16.1).
    """

    ESTADO_CHOICES = [
        ("SOLICITADA", "Solicitada"),
        ("OTORGADA", "Otorgada"),
        ("APROBADA", "Aprobada"),
        ("RECHAZADA", "Rechazada"),
        ("FINALIZADA", "Finalizada"),
        ("CANCELADA", "Cancelada"),
        ("ANULADA", "Anulada"),
    ]

    docente = models.ForeignKey(
        "personal.Docente",
        on_delete=models.PROTECT,
        related_name="licencias_otorgadas",
        verbose_name="Docente",
    )
    cargo = models.ForeignKey(
        "personal.CargoDocente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="licencias_otorgadas",
        verbose_name="Cargo Docente",
        help_text="Cargo docente específico al que aplica la licencia.",
    )
    tipo_licencia = models.ForeignKey(
        TipoLicencia,
        on_delete=models.PROTECT,
        related_name="licencias_otorgadas",
        verbose_name="Tipo de Licencia",
    )
    fecha_solicitud = models.DateField(
        default=datetime.date.today,
        verbose_name="Fecha de Solicitud",
    )
    fecha_desde = models.DateField(
        verbose_name="Fecha Desde",
    )
    fecha_hasta_prevista = models.DateField(
        verbose_name="Fecha Hasta Prevista",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="OTORGADA",
        verbose_name="Estado",
    )
    porcentaje_goce = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        verbose_name="Porcentaje de Goce",
        help_text="Porcentaje de haberes (ej: 100.00, 50.00, 0.00).",
    )
    instrumento_legal = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Instrumento Legal",
        help_text="Acto administrativo que otorga la licencia (ej: Resol. 1234/26).",
    )
    observaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Observaciones",
    )

    class Meta:
        verbose_name = "Licencia Otorgada"
        verbose_name_plural = "Licencias Otorgadas"
        ordering = ["-fecha_desde", "-creado_en"]
        indexes = [
            models.Index(fields=["docente", "estado"]),
            models.Index(fields=["fecha_desde", "fecha_hasta_prevista"]),
        ]

    def __init__(self, *args, **kwargs):
        self._sincronizar_asistencia = kwargs.pop("sincronizar_asistencia", True)
        super().__init__(*args, **kwargs)

    def __str__(self):
        cargo_str = f" - {self.cargo}" if self.cargo else ""
        return (
            f"Licencia {self.tipo_licencia.codigo if self.tipo_licencia else 'S/T'} "
            f"para {self.docente} ({self.fecha_desde} a {self.fecha_hasta_prevista})"
            f"{cargo_str}"
        )

    @property
    def dias_duracion_prevista(self):
        """Calcula los días calendario previstos para la licencia."""
        if self.fecha_desde and self.fecha_hasta_prevista:
            return (self.fecha_hasta_prevista - self.fecha_desde).days + 1
        return 0

    def clean(self):
        """
        Valida que el tipo de licencia sea compatible con la situación de revista
        del cargo docente (Ticket 17.1) y que el cargo pertenezca al docente.
        """
        super().clean()
        from django.core.exceptions import ValidationError

        tipo_lic = None
        if hasattr(self, "tipo_licencia_id") and self.tipo_licencia_id:
            try:
                tipo_lic = self.tipo_licencia
            except Exception:
                tipo_lic = None

        cargo = None
        if hasattr(self, "cargo_id") and self.cargo_id:
            try:
                cargo = self.cargo
            except Exception:
                cargo = None

        docente = None
        if hasattr(self, "docente_id") and self.docente_id:
            try:
                docente = self.docente
            except Exception:
                docente = None

        if tipo_lic and cargo:
            from apps.licencias.validaciones import validar_regimen_revista

            validar_regimen_revista(
                tipo_licencia=tipo_lic,
                cargo=cargo,
            )

        if tipo_lic:
            from apps.licencias.validaciones import validar_antiguedad_minima

            validar_antiguedad_minima(
                tipo_licencia=tipo_lic,
                docente=docente,
                cargo=cargo,
                fecha_desde=getattr(self, "fecha_desde", None),
                fecha_hasta=getattr(self, "fecha_hasta_prevista", None),
            )

        if (
            cargo
            and getattr(self, "fecha_desde", None)
            and getattr(self, "fecha_hasta_prevista", None)
        ):
            from apps.licencias.validaciones import validar_solapamiento_licencias

            validar_solapamiento_licencias(
                cargo=cargo,
                fecha_desde=self.fecha_desde,
                fecha_hasta=self.fecha_hasta_prevista,
                instancia_actual=self,
                docente=docente,
            )

        if tipo_lic and (
            getattr(self, "fecha_desde", None)
            or getattr(self, "fecha_hasta_prevista", None)
        ):
            from apps.licencias.validaciones import (
                validar_control_saldos_y_topes,
            )

            validar_control_saldos_y_topes(
                tipo_licencia=tipo_lic,
                docente=docente,
                cargo=cargo,
                fecha_desde=getattr(self, "fecha_desde", None),
                fecha_hasta=getattr(self, "fecha_hasta_prevista", None),
                instancia_actual=self,
            )

        if docente and cargo and cargo.docente != docente:
            raise ValidationError(
                f"El cargo '{cargo}' no pertenece al docente {docente}."
            )

        if (
            getattr(self, "fecha_desde", None)
            and getattr(self, "fecha_hasta_prevista", None)
            and self.fecha_hasta_prevista < self.fecha_desde
        ):
            raise ValidationError(
                {
                    "fecha_hasta_prevista": (
                        "La fecha hasta prevista no puede ser anterior "
                        "a la fecha desde."
                    )
                }
            )

    def save(self, *args, **kwargs):
        sincronizar = kwargs.pop(
            "sincronizar_asistencia", getattr(self, "_sincronizar_asistencia", True)
        )
        self.clean()
        if isinstance(self.porcentaje_goce, str):
            val = self.porcentaje_goce.replace("%", "").strip()
            if val.lower() in ["sin goce", "sin_goce"]:
                self.porcentaje_goce = Decimal("0.00")
            else:
                try:
                    self.porcentaje_goce = Decimal(val)
                except Exception:
                    self.porcentaje_goce = Decimal("100.00")
        elif self.porcentaje_goce is None:
            if self.tipo_licencia and self.tipo_licencia.forma_goce == "50%":
                self.porcentaje_goce = Decimal("50.00")
            elif self.tipo_licencia and self.tipo_licencia.forma_goce in [
                "Sin goce",
                "SIN_GOCE",
            ]:
                self.porcentaje_goce = Decimal("0.00")
            else:
                self.porcentaje_goce = Decimal("100.00")

        super().save(*args, **kwargs)

        if (
            sincronizar
            and getattr(self, "fecha_desde", None)
            and getattr(self, "fecha_hasta_prevista", None)
        ):
            if self.estado in ("OTORGADA", "APROBADA"):
                self.sincronizar_asistencia()
            elif self.estado in ("CANCELADA", "ANULADA", "RECHAZADA"):
                self.revertir_asistencia()

    def sincronizar_asistencia(self, usuario=None):
        """
        Sincroniza la licencia con los registros diarios de asistencia (Ticket 18.1).
        """
        from apps.licencias.services import sincronizar_licencia_con_asistencia

        return sincronizar_licencia_con_asistencia(self, usuario=usuario)

    def revertir_asistencia(self, usuario=None):
        """
        Revierte las marcas de asistencia asociadas a esta licencia (Ticket 18.1).
        """
        from apps.licencias.services import revertir_licencia_en_asistencia

        return revertir_licencia_en_asistencia(self, usuario=usuario)

    def aprobar(self, usuario=None):
        """
        Aprueba la licencia y sincroniza automáticamente las marcas diarias
        (Ticket 18.1).
        """
        from apps.licencias.services import aprobar_licencia

        return aprobar_licencia(self, usuario=usuario)

    def anular(self, usuario=None, motivo=""):
        """
        Anula la licencia y revierte automáticamente las marcas diarias (Ticket 18.1).
        """
        from apps.licencias.services import anular_licencia

        return anular_licencia(self, usuario=usuario, motivo=motivo)

    def calcular_fechas(self, feriados=None):
        """
        Calcula las fechas, días consumidos y reintegro usando el motor
        de cálculo (Ticket 16.2).
        """
        from apps.licencias.calculador import calcular_fechas_licencia

        return calcular_fechas_licencia(
            fecha_desde=self.fecha_desde,
            fecha_hasta=self.fecha_hasta_prevista,
            tipo_licencia=self.tipo_licencia,
            feriados=feriados,
        )

    def calcular_reintegro(self, feriados=None):
        """
        Calcula la fecha de reintegro efectiva posterior a la fecha de finalización
        prevista (Ticket 16.2).
        """
        from apps.licencias.calculador import calcular_fecha_reintegro

        return calcular_fecha_reintegro(self.fecha_hasta_prevista, feriados=feriados)
