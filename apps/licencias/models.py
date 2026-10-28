"""
Modelos del módulo de Licencias y Planillas Mensuales para el IESETyFP.
Gestiona el catálogo de licencias estatutarias y la consolidación de novedades.
"""

import datetime
import unicodedata
from django.apps import apps
from django.conf import settings
from django.db import models
from apps.core.models import AuditoriaModel


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
        db_table = "gestion_asistencia_tipolicencia"

    def __str__(self):
        goce = "C/Goce" if self.goce_haberes else "S/Goce"
        art = f"{self.articulo} " if self.articulo else ""
        return f"{art}({self.codigo}) - {self.descripcion} [{goce}]".strip()

    def save(self, *args, **kwargs):
        if not self.goce_haberes and self.forma_pago == "CON_GOCE":
            self.forma_pago = "SIN_GOCE"
        else:
            self.goce_haberes = self.forma_pago == "CON_GOCE"
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


class RenglonPlanillaMensual(AuditoriaModel):
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
        "personal.Docente",
        on_delete=models.PROTECT,
        related_name="renglones_mensuales",
        verbose_name="Docente",
    )
    cargo = models.ForeignKey(
        "personal.CargoDocente",
        on_delete=models.PROTECT,
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

    class Meta:
        verbose_name = "Renglón de Planilla Mensual"
        verbose_name_plural = "Renglones de Planilla Mensual"
        db_table = "gestion_asistencia_renglonplanillamensual"
        ordering = ["anio", "mes", "numero_instrumento", "docente__apellido"]
        indexes = [
            models.Index(fields=["anio", "mes"]),
        ]

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
        Docente = apps.get_model("personal", "Docente")
        DiaNoLaborable = apps.get_model("asistencia", "DiaNoLaborable")

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
