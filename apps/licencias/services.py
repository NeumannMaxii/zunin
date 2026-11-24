"""
Servicios de negocio para el módulo de Licencias y Planillas Mensuales.
Implementa el motor de generación mensual consolidada (RN-11).
"""

import datetime
import re
import unicodedata
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from apps.core.audit import audit_save
from apps.licencias.calculador import (  # noqa: F401
    CalculoFechasLicencia,
    MotorCalculoLicencia,
    UNIDAD_CORRIDOS,
    UNIDAD_HABILES,
    calcular_fecha_reintegro,
    calcular_fechas_licencia,
    contar_dias_corridos,
    contar_dias_habiles,
    es_dia_habil,
    normalizar_unidad,
    obtener_siguiente_dia_habil,
)
from apps.licencias.validaciones import (  # noqa: F401
    ESTADOS_LICENCIA_ACTIVAS,
    ESTADOS_LICENCIA_INACTIVAS,
    MESES_MINIMOS_ENFERMEDAD_COMPLETA,
    REGIMEN_CHOICES,
    REGIMEN_INT,
    REGIMEN_SUP,
    REGIMEN_TIT,
    TOPE_ENFERMEDAD_INTERINO_MENOR_4_MESES,
    TOPE_ENFERMEDAD_SUPLENTE_MENOR_4_MESES,
    buscar_licencias_solapadas,
    calcular_antiguedad_docente,
    calcular_antiguedad_meses,
    calcular_saldo_licencia,
    es_licencia_enfermedad_comun,
    es_regimen_compatible,
    evaluar_impacto_licencia_por_revista,
    filtrar_tipos_licencia_por_regimen,
    normalizar_regimen,
    obtener_fecha_alta_docente,
    obtener_rango_periodo_tope,
    obtener_regimenes_permitidos,
    obtener_tope_efectivo_licencia,
    validar_antiguedad_minima,
    validar_control_saldos_y_topes,
    validar_regimen_revista,
    validar_solapamiento_licencias,
    validar_solicitud_licencia,
)


def extraer_numero_y_anio_disposicion(texto):
    """
    Ticket 19.3: Extrae la secuencia numérica y el año de un texto que represente
    una Disposición Interna institucional (ej: '014/2026', 'Disp. 055/26',
    'Disposición 014/2026', '015/2026').

    Retorna (numero: int, anio: int) o (None, None) si no es un formato válido.
    """
    if not texto:
        return None, None

    texto_str = str(texto).strip()
    # Si contiene 'res' o 'resoluci' (Resolución externa ministerial), ignorar
    if re.search(r"\b(res|resoluci[oó]n)\b", texto_str, re.IGNORECASE):
        return None, None

    # Patrón general: número seguido de / y año de 2 o 4 dígitos
    match = re.search(r"(\d+)\s*/\s*(\d{2,4})", texto_str)
    if not match:
        return None, None

    num_int = int(match.group(1))
    anio_raw = match.group(2)
    if len(anio_raw) == 2:
        anio_int = 2000 + int(anio_raw)
    else:
        anio_int = int(anio_raw)

    return num_int, anio_int


def obtener_max_disposicion_existente(anio=None):
    """
    Ticket 19.3: Determina el número correlativo más alto registrado
    para el año consultando RenglonPlanillaMensual, LicenciaOtorgada,
    RegistroAsistencia y NumeradorDisposicion.
    """
    target_anio = anio or datetime.date.today().year
    max_num = 0

    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")
    LicenciaOtorgada = apps.get_model("licencias", "LicenciaOtorgada")
    NumeradorDisposicion = apps.get_model("licencias", "NumeradorDisposicion")

    # 1. RenglonPlanillaMensual
    inst_renglones = (
        RenglonPlanillaMensual.objects.filter(anio=target_anio)
        .exclude(numero_instrumento__isnull=True)
        .exclude(numero_instrumento="")
        .values_list("numero_instrumento", flat=True)
    )
    for s in inst_renglones:
        n, a = extraer_numero_y_anio_disposicion(s)
        if n and (a == target_anio or a == target_anio % 100):
            if n > max_num:
                max_num = n

    # 2. LicenciaOtorgada
    inst_licencias = (
        LicenciaOtorgada.objects.filter(fecha_desde__year=target_anio)
        .exclude(instrumento_legal__isnull=True)
        .exclude(instrumento_legal="")
        .values_list("instrumento_legal", flat=True)
    )
    for s in inst_licencias:
        n, a = extraer_numero_y_anio_disposicion(s)
        if n and (a == target_anio or a == target_anio % 100):
            if n > max_num:
                max_num = n

    # 3. NumeradorDisposicion
    num_obj = NumeradorDisposicion.objects.filter(anio=target_anio).first()
    if num_obj and num_obj.ultimo_numero > max_num:
        max_num = num_obj.ultimo_numero

    return max_num


def obtener_siguiente_correlativo_disposicion(
    anio=None,
    reservar=False,
    usuario=None,
):
    """
    Ticket 19.3: Retorna el siguiente número secuencial NNN/AAAA para
    Disposiciones Internas institucionales, garantizando resolución
    atómica con bloqueo concurrente (select_for_update).
    """
    target_anio = anio or datetime.date.today().year
    NumeradorDisposicion = apps.get_model("licencias", "NumeradorDisposicion")

    with transaction.atomic():
        numerador, _ = NumeradorDisposicion.objects.select_for_update().get_or_create(
            anio=target_anio,
            defaults={"ultimo_numero": 0},
        )
        max_existente = obtener_max_disposicion_existente(target_anio)
        if max_existente > numerador.ultimo_numero:
            numerador.ultimo_numero = max_existente
            audit_save(numerador, user=usuario, created=False)

        siguiente = numerador.ultimo_numero + 1
        if reservar:
            numerador.ultimo_numero = siguiente
            audit_save(numerador, user=usuario, created=False)

    return f"{siguiente:03d}/{target_anio}"


def confirmar_correlativo_disposicion(
    numero_str_o_int,
    anio=None,
    usuario=None,
):
    """
    Ticket 19.3: Actualiza de forma atómica el último correlativo asignado
    en NumeradorDisposicion si el número provisto es superior.
    """
    target_anio = anio
    num_int = None

    if isinstance(numero_str_o_int, int):
        num_int = numero_str_o_int
    elif isinstance(numero_str_o_int, str):
        n, a = extraer_numero_y_anio_disposicion(numero_str_o_int)
        num_int = n
        if a and not target_anio:
            target_anio = a

    if not num_int:
        return

    target_anio = target_anio or datetime.date.today().year
    NumeradorDisposicion = apps.get_model("licencias", "NumeradorDisposicion")

    with transaction.atomic():
        numerador, _ = NumeradorDisposicion.objects.select_for_update().get_or_create(
            anio=target_anio,
            defaults={"ultimo_numero": 0},
        )
        if num_int > numerador.ultimo_numero:
            numerador.ultimo_numero = num_int
            audit_save(numerador, user=usuario, created=False)


def verificar_disposicion_duplicada(
    numero_str,
    anio=None,
    excluir_licencia_id=None,
    excluir_renglon_id=None,
):
    """
    Ticket 19.3: Comprueba si un número de Disposición Interna ingresado
    manualmente ya existe en el año indicado.
    """
    num_int, anio_extraido = extraer_numero_y_anio_disposicion(numero_str)
    if not num_int:
        return {
            "duplicado": False,
            "mensaje": (
                "Formato de instrumento externo no sujeto a "
                "correlativo interno."
            ),
            "numero": None,
            "anio": anio,
        }

    target_anio = anio_extraido or anio or datetime.date.today().year
    variantes_busqueda = [
        f"{num_int:03d}/{target_anio}",
        f"{num_int}/{target_anio}",
        f"{num_int:03d}/{str(target_anio)[2:]}",
        f"{num_int}/{str(target_anio)[2:]}",
    ]

    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")
    LicenciaOtorgada = apps.get_model("licencias", "LicenciaOtorgada")

    # 1. Comprobar en Licencias Otorgadas
    qs_lic = LicenciaOtorgada.objects.filter(
        fecha_desde__year=target_anio,
    ).exclude(estado__in=["CANCELADA", "ANULADA", "RECHAZADA"])
    if excluir_licencia_id:
        qs_lic = qs_lic.exclude(pk=excluir_licencia_id)

    q_filtro = models.Q()
    for var in variantes_busqueda:
        q_filtro |= models.Q(instrumento_legal__icontains=var)
    lic_dup = qs_lic.filter(q_filtro).first()
    if lic_dup:
        return {
            "duplicado": True,
            "mensaje": (
                f"El número {numero_str} ya fue asignado en {target_anio} a la "
                f"Licencia #{lic_dup.pk} ({lic_dup.docente})."
            ),
            "numero": num_int,
            "anio": target_anio,
        }

    # 2. Comprobar en Renglones de Planilla Mensual
    qs_reng = RenglonPlanillaMensual.objects.filter(anio=target_anio)
    if excluir_renglon_id:
        qs_reng = qs_reng.exclude(pk=excluir_renglon_id)

    q_reng = models.Q()
    for var in variantes_busqueda:
        q_reng |= models.Q(numero_instrumento__icontains=var)
    reng_dup = qs_reng.filter(q_reng).first()
    if reng_dup:
        return {
            "duplicado": True,
            "mensaje": (
                f"El número {numero_str} ya fue asignado en la Planilla "
                f"{reng_dup.mes}/{target_anio} a {reng_dup.docente}."
            ),
            "numero": num_int,
            "anio": target_anio,
        }

    return {
        "duplicado": False,
        "mensaje": f"Número {num_int:03d}/{target_anio} disponible.",
        "numero": num_int,
        "anio": target_anio,
    }


def generar_planilla_mes(mes, anio, usuario=None):
    """
    Genera la planilla mensual consolidada desglosada por materia y horas (RN-11).

    Reglas de negocio aplicadas:
    1. Ejecución atómica mediante transaction.atomic().
    2. Precarga de días no laborables en un set para consultas en memoria O(1).
    3. Idempotencia: si el renglón ya existe para el docente/cargo/período en ese mes,
       se omite (continue) sin duplicar datos.
    4. Adyacencia: agrupa bloques contiguos de licencias del mismo tipo,
       considerando fines de semana y feriados.
    5. Validación de vigencia del cargo mediante
       cargo.es_designacion_vigente(dia_cursor).
    6. Contador anual de instrumentos: busca el máximo correlativo del año actual,
       iniciando en '001/YYYY' si no existen registros previos.
    """
    Docente = apps.get_model("personal", "Docente")
    DiaNoLaborable = apps.get_model("asistencia", "DiaNoLaborable")
    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")

    with transaction.atomic():
        # 1. Precarga de días no laborables en un set en memoria
        dias_no_laborables = set(DiaNoLaborable.objects.values_list("fecha", flat=True))

        # 2. Contador anual correlativo para el año indicado (Cross-year support)
        max_correlativo = 0
        instrumentos_existentes = (
            RenglonPlanillaMensual.objects.filter(anio=anio)
            .exclude(numero_instrumento__isnull=True)
            .exclude(numero_instrumento="")
            .values_list("numero_instrumento", flat=True)
        )
        for num_str in instrumentos_existentes:
            if "/" in num_str:
                parte_num = num_str.split("/")[0].strip()
                if parte_num.isdigit():
                    val = int(parte_num)
                    if val > max_correlativo:
                        max_correlativo = val

        correlativo = max_correlativo + 1

        # 3. Filtrar docentes con novedades de asistencia en el mes/año
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

        renglones_resultado = []

        for docente in docentes:
            asistencias_qs = (
                docente.asistencias.filter(
                    fecha__year=anio,
                    fecha__month=mes,
                )
                .filter(
                    models.Q(estado__in=["AUSENTE", "LICENCIA", "JUSTIFICADO"])
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
                    | (models.Q(marca_diaria="P") & ~models.Q(estado="PRESENTE"))
                )
                .order_by("fecha")
            )

            # 4. Agrupamiento de bloques contiguos (Adyacencia)
            bloques = []
            current_block = None

            for reg in asistencias_qs:
                r_desde = reg.fecha
                r_hasta = reg.fecha_hasta if reg.fecha_hasta else reg.fecha
                tipo_lic = reg.tipo_licencia
                cuadro = (
                    "IL-01"
                    if (tipo_lic and tipo_lic.cuadro_mensual in ["IL-01", "DL-01"])
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
                    # RN-06: Una inasistencia injustificada o falta simple se computa
                    # únicamente por el día puntual en que ocurrió. Las inasistencias
                    # solamente pueden ser por un día y no deben agruparse en bloques.
                    es_falta_simple = (
                        reg.marca_diaria in ["I", "INA"]
                        and reg.tipo_licencia is None
                        and not reg.justifica
                    )
                    current_es_falta_simple = (
                        current_block["marca_origen"] in ["I", "INA"]
                        and current_block["tipo_licencia"] is None
                    )

                    es_compatible = (
                        current_block["tipo_licencia"] == tipo_lic
                        and current_block["cuadro"] == cuadro
                        and not es_falta_simple
                        and not current_es_falta_simple
                    )

                    es_contiguo = False
                    if r_desde <= current_block["hasta"] + datetime.timedelta(days=1):
                        es_contiguo = True
                    else:
                        dia = current_block["hasta"] + datetime.timedelta(days=1)
                        todos_no_habiles = True
                        cargo_actual = current_block.get("cargo_fijado") or reg.cargo
                        while dia < r_desde:
                            if cargo_actual:
                                tiene_clases = (
                                    cargo_actual.obtener_horas_en_fecha(dia) > 0
                                )
                            else:
                                tiene_clases = dia.weekday() < 5

                            if tiene_clases and dia not in dias_no_laborables:
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

            # 5. Generación de renglones por bloque
            for bloque in bloques:
                cargos_registros = []
                for r in bloque["registros"]:
                    if r.cargo and r.cargo not in cargos_registros:
                        cargos_registros.append(r.cargo)

                if cargos_registros:
                    cargos_a_evaluar = list(cargos_registros)
                elif bloque["cargo_fijado"]:
                    cargos_a_evaluar = [bloque["cargo_fijado"]]
                else:
                    cargos_a_evaluar = list(docente.cargos.filter(activo=True))

                cargos_con_horas = []
                for cargo in cargos_a_evaluar:
                    total_horas = 0
                    dia_cursor = bloque["desde"]
                    while dia_cursor <= bloque["hasta"]:
                        # Validación de vigencia del cargo día por día
                        if cargo.es_designacion_vigente(dia_cursor):
                            total_horas += cargo.obtener_horas_en_fecha(dia_cursor)
                        dia_cursor += datetime.timedelta(days=1)

                    if total_horas > 0:
                        cargos_con_horas.append((cargo, total_horas))

                if not cargos_con_horas and cargos_a_evaluar:
                    cargos_vigentes = [
                        c
                        for c in cargos_a_evaluar
                        if c.es_designacion_vigente(bloque["desde"])
                        or c.es_designacion_vigente(bloque["hasta"])
                    ]
                    if cargos_vigentes:
                        cargos_con_horas.append((cargos_vigentes[0], 0))
                    elif cargos_a_evaluar:
                        cargos_con_horas.append((cargos_a_evaluar[0], 0))

                # Idempotencia (SKIP): verificar si el renglón ya existe
                # entre los vigentes (Ticket 10.4)
                cargos_a_crear = []
                for cargo, horas in cargos_con_horas:
                    renglon_existente = (
                        RenglonPlanillaMensual.objects.vigentes()
                        .filter(
                            docente=docente,
                            cargo=cargo,
                            mes=mes,
                            anio=anio,
                            desde=bloque["desde"],
                            hasta=bloque["hasta"],
                        )
                        .first()
                    )

                    if renglon_existente:
                        renglones_resultado.append(renglon_existente)
                        continue

                    cargos_a_crear.append((cargo, horas))

                # Si todos los renglones ya existían para este bloque, continuar
                if not cargos_a_crear:
                    continue

                # Determinar si el bloque contiene resoluciones ministeriales
                es_resolucion = False
                num_inst = None
                for reg in bloque["registros"]:
                    if reg.numero_disposicion:
                        nd_str = str(reg.numero_disposicion).strip()
                        nd_lower = nd_str.lower()
                        if (
                            "res" in nd_lower
                            or "resoluci" in nd_lower
                            or "m.e.c" in nd_lower
                        ):
                            es_resolucion = True
                            num_inst = nd_str
                            break

                if es_resolucion and num_inst:
                    tipo_inst = "RESOLUCION"
                    final_num = num_inst
                else:
                    tipo_inst = "DISPOSICION"
                    final_num = f"{correlativo:03d}/{anio}"
                    correlativo += 1

                for reg in bloque["registros"]:
                    reg.numero_disposicion = final_num
                    reg.save(update_fields=["numero_disposicion"])

                for cargo, horas in cargos_a_crear:
                    renglon = RenglonPlanillaMensual.objects.create(
                        docente=docente,
                        cargo=cargo,
                        tipo_licencia=bloque["tipo_licencia"],
                        cuadro=bloque["cuadro"],
                        mes=mes,
                        anio=anio,
                        oficina=getattr(settings, "DEFAULT_OFICINA_CODE", "1452"),
                        desde=bloque["desde"],
                        hasta=bloque["hasta"],
                        horas_afectadas=horas,
                        marca_origen=bloque["marca_origen"],
                        tipo_instrumento=tipo_inst,
                        numero_instrumento=final_num,
                        creado_por=usuario,
                        modificado_por=usuario,
                    )
                    renglones_resultado.append(renglon)

        if correlativo > max_correlativo + 1:
            confirmar_correlativo_disposicion(
                correlativo - 1,
                anio=anio,
                usuario=usuario,
            )

        return renglones_resultado


def procesar_justificacion_rango(
    docente,
    fecha_desde,
    fecha_hasta,
    nueva_marca,
    tipo_licencia=None,
    numero_disposicion=None,
    observaciones=None,
    cargo=None,
    usuario=None,
    tipo_instrumento="DISPOSICION",
):
    """
    Procesa la justificación diferida de inasistencias en un rango de fechas
    (Ticket 7 - RN-03).

    Reglas de negocio:
    1. Valida cronología del rango (fecha_hasta >= fecha_desde).
    2. Salta automáticamente fines de semana (sábados y domingos).
    3. Salta automáticamente feriados y días no laborables (DiaNoLaborable).
    4. Ejecución atómica total bajo `with transaction.atomic():`. Ante cualquier
       error o fallo se revierte el lote completo (0 registros persistidos).
    5. Integridad histórica (RN-03): si el mes ya cuenta con planilla mensual
       generada, NO se borran los renglones existentes. Se marcan como
       desactualizados y se fuerza la regeneración segura con los nuevos datos,
       preservando los números de instrumento asignados originalmente.
    """
    if not docente:
        raise ValidationError("Debe especificar el docente a justificar.")

    if not fecha_desde or not fecha_hasta:
        raise ValidationError(
            "Debe especificar tanto la fecha de inicio como la fecha de fin."
        )

    if fecha_hasta < fecha_desde:
        raise ValidationError(
            "La fecha de fin no puede ser anterior a la fecha de inicio."
        )

    if nueva_marca not in ["LIC", "LIC.", "LT", "P", "PERM"]:
        raise ValidationError(
            f"Marca no válida para justificación diferida: {nueva_marca}."
        )

    if nueva_marca in ["LIC", "LIC.", "LT"] and not tipo_licencia:
        raise ValidationError(
            "Debe especificar un Tipo de Licencia para justificar con Licencia."
        )

    DiaNoLaborable = apps.get_model("asistencia", "DiaNoLaborable")
    RegistroAsistencia = apps.get_model("asistencia", "RegistroAsistencia")
    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")
    CargoDocente = apps.get_model("personal", "CargoDocente")

    # Precarga de feriados y asuetos en el rango
    feriados_fechas = set(
        DiaNoLaborable.objects.filter(
            fecha__range=[fecha_desde, fecha_hasta]
        ).values_list("fecha", flat=True)
    )

    # Identificar días con carga horaria a justificar (Ticket 10.7 y Ticket 18.3)
    dias_a_justificar = []
    dia_cursor = fecha_desde

    registros_previos_fechas = set(
        RegistroAsistencia.objects.filter(
            docente=docente,
            fecha__range=[fecha_desde, fecha_hasta],
        ).values_list("fecha", flat=True)
    )

    cargos_activos_docente = (
        list(docente.cargos.filter(activo=True))
        if hasattr(docente, "cargos")
        else []
    )
    tiene_horas_configuradas = any(
        c.total_horas_semanales > 0 for c in cargos_activos_docente
    )

    while dia_cursor <= fecha_hasta:
        # Evaluación dinámica: verificar si el cargo tiene clases en la fecha
        if cargo:
            if getattr(cargo, "total_horas_semanales", 0) > 0:
                tiene_clases = cargo.obtener_horas_en_fecha(dia_cursor) > 0
            else:
                tiene_clases = dia_cursor.weekday() < 5
        else:
            if cargos_activos_docente and tiene_horas_configuradas:
                tiene_clases = any(
                    c.obtener_horas_en_fecha(dia_cursor) > 0
                    for c in cargos_activos_docente
                    if not hasattr(c, "es_designacion_vigente")
                    or c.es_designacion_vigente(dia_cursor)
                )
            else:
                tiene_clases = dia_cursor.weekday() < 5

        if (
            tiene_clases or (dia_cursor in registros_previos_fechas)
        ) and dia_cursor not in feriados_fechas:
            dias_a_justificar.append(dia_cursor)

        dia_cursor += datetime.timedelta(days=1)

    # Contingencia si el rango fue en días hábiles sin feriados
    if not dias_a_justificar and fecha_desde not in feriados_fechas:
        cursor_temp = fecha_desde
        while cursor_temp <= fecha_hasta:
            if cursor_temp.weekday() < 5 and cursor_temp not in feriados_fechas:
                dias_a_justificar.append(cursor_temp)
            cursor_temp += datetime.timedelta(days=1)

    num_final = numero_disposicion
    if tipo_instrumento == "RESOLUCION" and numero_disposicion:
        nd_str = str(numero_disposicion).strip()
        nd_lower = nd_str.lower()
        if not ("res" in nd_lower or "resoluci" in nd_lower):
            num_final = f"Resolución {nd_str}"
        else:
            num_final = nd_str
    elif tipo_instrumento == "DISPOSICION" and numero_disposicion:
        confirmar_correlativo_disposicion(
            num_final, anio=fecha_desde.year, usuario=usuario
        )

    with transaction.atomic():
        registros_guardados = []
        meses_afectados = set()

        # Ticket 18.3: Precargar asistencias del intervalo para el docente
        asistencias_existentes = list(
            RegistroAsistencia.objects.filter(
                docente=docente,
                fecha__range=[fecha_desde, fecha_hasta],
            )
        )
        asistencias_por_cargo_y_fecha = {
            (r.cargo_id, r.fecha): r for r in asistencias_existentes
        }
        asistencias_por_fecha = {}
        for r in asistencias_existentes:
            asistencias_por_fecha.setdefault(r.fecha, []).append(r)

        registros_usados_ids = set()

        for dia in dias_a_justificar:
            meses_afectados.add((dia.month, dia.year))

            if cargo is not None:
                cargos_a_procesar = [cargo]
            else:
                # Ticket 18.3: Consultar los cargos activos y vigentes del docente
                cargos_activos = list(docente.cargos.filter(activo=True))
                cargos_vigentes = [
                    c
                    for c in cargos_activos
                    if not hasattr(c, "es_designacion_vigente")
                    or c.es_designacion_vigente(dia)
                ]
                if not cargos_vigentes:
                    cargos_vigentes = cargos_activos

                # Filtrar los cargos que tengan horas asignadas en ese día puntual
                cargos_con_horas = [
                    c
                    for c in cargos_vigentes
                    if c.obtener_horas_en_fecha(dia) > 0
                ]
                if cargos_con_horas:
                    cargos_a_procesar = cargos_con_horas
                else:
                    # Si ningún cargo tiene horas ese día pero era día
                    # hábil a justificar: asignar al primer cargo activo
                    # (first_cargo) como contingencia.
                    first_cargo = (
                        cargos_vigentes[0]
                        if cargos_vigentes
                        else (
                            docente.cargos.first()
                            if hasattr(docente, "cargos")
                            else None
                        )
                    )
                    if not first_cargo:
                        first_cargo = CargoDocente.objects.create(
                            docente=docente,
                            situacion_revista="TIT",
                            activo=True,
                        )
                    cargos_a_procesar = [first_cargo]

            estado_destino = (
                "LICENCIA"
                if nueva_marca in ["LIC", "LIC.", "LT"]
                else "JUSTIFICADO"
            )

            for target_cargo in cargos_a_procesar:
                # Ticket 19.2: Evaluar si la situación de revista habilita la licencia
                cargo_aplica = True
                detalle_no_aplica = ""
                if nueva_marca in ["LIC", "LIC.", "LT"] and tipo_licencia:
                    eval_impacto = evaluar_impacto_licencia_por_revista(
                        docente=docente,
                        tipo_licencia=tipo_licencia,
                        fecha_desde=dia,
                        fecha_hasta=dia,
                        cargo=target_cargo,
                    )
                    if eval_impacto:
                        cargo_aplica = eval_impacto[0]["aplica"]
                        detalle_no_aplica = eval_impacto[0].get("detalle", "")

                if cargo_aplica:
                    estado_final = estado_destino
                    marca_final = nueva_marca
                    tipo_lic_final = tipo_licencia
                    justifica_final = True
                    obs_final = observaciones
                else:
                    estado_final = "AUSENTE"
                    marca_final = "I"
                    tipo_lic_final = None
                    justifica_final = False
                    tag_no_aplica = (
                        f"NO APLICA LICENCIA "
                        f"({target_cargo.get_situacion_revista_display()}): "
                        f"{detalle_no_aplica}"
                    )
                    obs_final = (
                        f"{observaciones} | {tag_no_aplica}"
                        if observaciones
                        else tag_no_aplica
                    )

                # Buscar registro existente exacto o pendiente de asignar
                reg = asistencias_por_cargo_y_fecha.get((target_cargo.id, dia))
                if reg is None:
                    candidatos = asistencias_por_fecha.get(dia, [])
                    for cand in candidatos:
                        if cand.pk not in registros_usados_ids:
                            reg = cand
                            break

                if reg is not None:
                    registros_usados_ids.add(reg.pk)
                    reg.cargo = target_cargo
                    reg.estado = estado_final
                    reg.marca_diaria = marca_final
                    reg.tipo_licencia = tipo_lic_final
                    reg.justifica = justifica_final
                    if num_final:
                        reg.numero_disposicion = num_final
                    if obs_final:
                        if reg.observaciones:
                            reg.observaciones = (
                                f"{reg.observaciones} | {obs_final}"
                            )
                        else:
                            reg.observaciones = obs_final
                    audit_save(reg, user=usuario, created=False)
                    registros_guardados.append(reg)
                else:
                    nuevo_reg = RegistroAsistencia(
                        docente=docente,
                        cargo=target_cargo,
                        fecha=dia,
                        estado=estado_final,
                        marca_diaria=marca_final,
                        tipo_licencia=tipo_lic_final,
                        justifica=justifica_final,
                        numero_disposicion=num_final,
                        observaciones=obs_final or "",
                        oficina=getattr(settings, "DEFAULT_OFICINA_CODE", "1452"),
                    )
                    audit_save(nuevo_reg, user=usuario, created=True)
                    registros_usados_ids.add(nuevo_reg.pk)
                    asistencias_por_cargo_y_fecha[(target_cargo.id, dia)] = nuevo_reg
                    asistencias_por_fecha.setdefault(dia, []).append(nuevo_reg)
                    registros_guardados.append(nuevo_reg)

        # Regla de Integridad Histórica RN-03:
        # Si un mes ya tiene planilla mensual consolidada emitida,
        # NO se deben borrar los renglones existentes. Se marcan como
        # desactualizados y se regenera la planilla de forma segura.
        for mes, anio in meses_afectados:
            planillas_mes = RenglonPlanillaMensual.objects.filter(mes=mes, anio=anio)
            if planillas_mes.exists():
                planillas_mes.update(desactualizada=True)
                generar_planilla_mes(mes=mes, anio=anio, usuario=usuario)

        return registros_guardados


procesar_justificacion_diferida = procesar_justificacion_rango


# =============================================================================
# Ticket 18.1: Sincronización Automática con Asistencia Diaria
# =============================================================================


def determinar_marca_licencia(tipo_licencia):
    """
    Determina la marca diaria para el registro de asistencia (LIC, LT, etc.)
    según el tipo de licencia (Ticket 18.1).
    """
    if not tipo_licencia:
        return "LIC"

    codigo = (getattr(tipo_licencia, "codigo", "") or "").upper()
    descripcion = (getattr(tipo_licencia, "descripcion", "") or "").upper()
    articulo = (
        (getattr(tipo_licencia, "articulo", "") or "")
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

    if "LT" in codigo or "LARGO TRATAMIENTO" in descripcion or "340B" in articulo:
        return "LT"

    return "LIC"


def obtener_dias_sincronizacion_licencia(licencia, cargo=None):
    """
    Retorna la lista de fechas comprendidas en la licencia que deben reflejarse
    en el parte diario de asistencia (Ticket 18.1).
    """
    if not licencia.fecha_desde or not licencia.fecha_hasta_prevista:
        return []

    if licencia.fecha_hasta_prevista < licencia.fecha_desde:
        return []

    DiaNoLaborable = apps.get_model("asistencia", "DiaNoLaborable")

    feriados_fechas = set(
        DiaNoLaborable.objects.filter(
            fecha__range=[licencia.fecha_desde, licencia.fecha_hasta_prevista]
        ).values_list("fecha", flat=True)
    )

    dias = []
    cursor = licencia.fecha_desde
    while cursor <= licencia.fecha_hasta_prevista:
        if cargo and getattr(cargo, "total_horas_semanales", 0) > 0:
            aplica = cargo.obtener_horas_en_fecha(cursor) > 0
        else:
            aplica = cursor.weekday() < 5

        if aplica and cursor not in feriados_fechas:
            dias.append(cursor)
        cursor += datetime.timedelta(days=1)

    # Si no se incluyó ningún día (ej: fin de semana o feriado en un test),
    # o si fecha_desde == fecha_hasta_prevista, incluimos los días del rango para
    # asegurar que la licencia otorgada se refleje en asistencia.
    if not dias:
        cursor = licencia.fecha_desde
        while cursor <= licencia.fecha_hasta_prevista:
            dias.append(cursor)
            cursor += datetime.timedelta(days=1)

    return dias


def sincronizar_licencia_con_asistencia(licencia, usuario=None):
    """
    Ticket 18.1: Actualiza automáticamente las marcas diarias en el módulo
    de asistencia diaria al aprobar u otorgar una licencia.
    Refleja 'LIC' o 'LT' según el tipo de licencia en todos los días comprendidos.
    """
    RegistroAsistencia = apps.get_model("asistencia", "RegistroAsistencia")
    CargoDocente = apps.get_model("personal", "CargoDocente")
    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")

    if not licencia.fecha_desde or not licencia.fecha_hasta_prevista:
        return []

    marca = determinar_marca_licencia(licencia.tipo_licencia)
    docente = licencia.docente

    # Determinar cargos a los que aplica
    if licencia.cargo:
        cargos = [licencia.cargo]
    else:
        cargos = list(docente.cargos.filter(activo=True))
        if not cargos:
            cargos = list(docente.cargos.all())
        if not cargos:
            cargos = [
                CargoDocente.objects.create(
                    docente=docente,
                    situacion_revista="TIT",
                    activo=True,
                )
            ]

    registros_actualizados = []
    meses_afectados = set()

    with transaction.atomic():
        # Ticket 19.2: Evaluar impacto normativo según situación de revista
        # de cada cargo
        evaluaciones = {
            ev["cargo_id"]: ev
            for ev in evaluar_impacto_licencia_por_revista(
                docente=docente,
                tipo_licencia=licencia.tipo_licencia,
                fecha_desde=licencia.fecha_desde,
                fecha_hasta=licencia.fecha_hasta_prevista,
                cargo=licencia.cargo,
            )
        }

        # Ticket 19.3: Asignar o confirmar correlativo si es Disposición Interna
        tipo_inst = getattr(licencia, "tipo_instrumento", "DISPOSICION")
        if tipo_inst == "DISPOSICION":
            if not licencia.instrumento_legal and licencia.fecha_desde:
                licencia.instrumento_legal = (
                    obtener_siguiente_correlativo_disposicion(
                        anio=licencia.fecha_desde.year,
                        reservar=True,
                        usuario=usuario,
                    )
                )
                licencia.__class__.objects.filter(pk=licencia.pk).update(
                    instrumento_legal=licencia.instrumento_legal
                )
            elif licencia.instrumento_legal and licencia.fecha_desde:
                confirmar_correlativo_disposicion(
                    licencia.instrumento_legal,
                    anio=licencia.fecha_desde.year,
                    usuario=usuario,
                )

        for cargo in cargos:
            dias_a_sincronizar = obtener_dias_sincronizacion_licencia(licencia, cargo)
            eval_cargo = evaluaciones.get(cargo.pk)
            cargo_aplica = eval_cargo["aplica"] if eval_cargo else True
            detalle_no_aplica = (
                eval_cargo.get("detalle", "") if eval_cargo else ""
            )

            for dia in dias_a_sincronizar:
                meses_afectados.add((dia.month, dia.year))
                reg = RegistroAsistencia.objects.filter(
                    docente=docente,
                    cargo=cargo,
                    fecha=dia,
                ).first()

                if cargo_aplica:
                    # Aplica la licencia con goce de haberes
                    if reg:
                        obs = reg.observaciones or ""
                        if "PREV_MARCA:" not in obs:
                            prev_info = (
                                f"PREV_ESTADO:{reg.estado}|"
                                f"PREV_MARCA:{reg.marca_diaria}"
                            )
                            reg.observaciones = (
                                f"{prev_info} | {obs}" if obs else prev_info
                            )
                        reg.estado = "LICENCIA"
                        reg.marca_diaria = marca
                        reg.tipo_licencia = licencia.tipo_licencia
                        reg.justifica = True
                        if licencia.instrumento_legal:
                            reg.numero_disposicion = licencia.instrumento_legal
                        if usuario:
                            reg.modificado_por = usuario
                        reg.save()
                        registros_actualizados.append(reg)
                    else:
                        nuevo_reg = RegistroAsistencia(
                            docente=docente,
                            cargo=cargo,
                            fecha=dia,
                            estado="LICENCIA",
                            marca_diaria=marca,
                            tipo_licencia=licencia.tipo_licencia,
                            justifica=True,
                            numero_disposicion=licencia.instrumento_legal or "",
                            observaciones=f"AUTO_SYNC_LICENCIA:{licencia.pk}",
                            creado_por=usuario or licencia.creado_por,
                        )
                        nuevo_reg.save()
                        registros_actualizados.append(nuevo_reg)
                else:
                    # Ticket 19.2: No aplica por situación de revista
                    tag_no_aplica = (
                        f"NO_APLICA_REVISTA:{cargo.situacion_revista}|"
                        f"LIC:{licencia.tipo_licencia.codigo}|{detalle_no_aplica}"
                    )
                    if reg:
                        reg.estado = "AUSENTE"
                        reg.marca_diaria = "I"
                        reg.tipo_licencia = None
                        reg.justifica = False
                        reg.observaciones = (
                            f"{reg.observaciones} | {tag_no_aplica}"
                            if reg.observaciones
                            else tag_no_aplica
                        )
                        if usuario:
                            reg.modificado_por = usuario
                        reg.save()
                        registros_actualizados.append(reg)
                    else:
                        nuevo_reg = RegistroAsistencia(
                            docente=docente,
                            cargo=cargo,
                            fecha=dia,
                            estado="AUSENTE",
                            marca_diaria="I",
                            tipo_licencia=None,
                            justifica=False,
                            numero_disposicion=licencia.instrumento_legal or "",
                            observaciones=tag_no_aplica,
                            creado_por=usuario or licencia.creado_por,
                        )
                        nuevo_reg.save()
                        registros_actualizados.append(nuevo_reg)

        # Regla de Integridad Histórica RN-03:
        for mes, anio in meses_afectados:
            planillas_mes = RenglonPlanillaMensual.objects.filter(mes=mes, anio=anio)
            if planillas_mes.exists():
                planillas_mes.update(desactualizada=True)
                generar_planilla_mes(mes=mes, anio=anio, usuario=usuario)

    return registros_actualizados


def revertir_licencia_en_asistencia(licencia, usuario=None):
    """
    Ticket 18.1: Revierte automáticamente las marcas diarias de asistencia
    ante la anulación o cancelación de una licencia.
    """
    RegistroAsistencia = apps.get_model("asistencia", "RegistroAsistencia")
    RenglonPlanillaMensual = apps.get_model("licencias", "RenglonPlanillaMensual")

    if not licencia.fecha_desde or not licencia.fecha_hasta_prevista:
        return []

    docente = licencia.docente
    registros_revertidos = []
    meses_afectados = set()

    with transaction.atomic():
        qs = RegistroAsistencia.objects.filter(
            docente=docente,
            fecha__range=[licencia.fecha_desde, licencia.fecha_hasta_prevista],
            tipo_licencia=licencia.tipo_licencia,
        )
        if licencia.cargo:
            qs = qs.filter(cargo=licencia.cargo)

        for reg in qs:
            meses_afectados.add((reg.fecha.month, reg.fecha.year))
            obs = reg.observaciones or ""
            # Verificar si tenía un estado previo respaldado
            if "PREV_ESTADO:" in obs and "PREV_MARCA:" in obs:
                import re

                m_est = re.search(r"PREV_ESTADO:([A-Za-z_]+)", obs)
                m_mar = re.search(r"PREV_MARCA:([A-Za-z0-9.]+)", obs)
                prev_est = m_est.group(1) if m_est else "AUSENTE"
                prev_mar = m_mar.group(1) if m_mar else "I"
                reg.estado = prev_est
                reg.marca_diaria = prev_mar
            else:
                reg.estado = "AUSENTE"
                reg.marca_diaria = "I"

            reg.tipo_licencia = None
            reg.justifica = False
            reg.numero_disposicion = ""
            if usuario:
                reg.modificado_por = usuario
            reg.save()
            registros_revertidos.append(reg)

        # Regla de Integridad Histórica RN-03:
        for mes, anio in meses_afectados:
            planillas_mes = RenglonPlanillaMensual.objects.filter(mes=mes, anio=anio)
            if planillas_mes.exists():
                planillas_mes.update(desactualizada=True)
                generar_planilla_mes(mes=mes, anio=anio, usuario=usuario)

    return registros_revertidos


def aprobar_licencia(licencia, usuario=None):
    """
    Ticket 18.1: Aprueba formalmente una licencia otorgada y sincroniza
    automáticamente sus marcas en el módulo de asistencia diaria.
    """
    with transaction.atomic():
        licencia.estado = "OTORGADA"
        if usuario:
            licencia.modificado_por = usuario
        licencia.save(sincronizar_asistencia=False)
        registros = sincronizar_licencia_con_asistencia(licencia, usuario=usuario)
    return registros


def anular_licencia(licencia, usuario=None, motivo=""):
    """
    Ticket 18.1: Anula una licencia otorgada y revierte automáticamente
    las marcas correspondientes en el módulo de asistencia diaria.
    """
    with transaction.atomic():
        licencia.estado = "CANCELADA"
        if motivo:
            licencia.observaciones = (
                f"{licencia.observaciones}\n[Anulación]: {motivo}"
                if licencia.observaciones
                else f"[Anulación]: {motivo}"
            )
        if usuario:
            licencia.modificado_por = usuario
        licencia.save(sincronizar_asistencia=False)
        registros = revertir_licencia_en_asistencia(licencia, usuario=usuario)
    return registros


def obtener_resumen_saldos_docente(docente, anio=None):
    """
    Ticket 18.2: Calcula y consolida el resumen de saldos estatutarios de
    un docente para el año calendario especificado (o año actual por defecto).
    """
    from apps.personal.models import Docente
    from apps.licencias.models import TipoLicencia, LicenciaOtorgada

    if isinstance(docente, int) or (
        isinstance(docente, str) and str(docente).isdigit()
    ):
        docente = Docente.objects.filter(pk=int(docente)).first()

    if not docente:
        return None

    anio_actual = anio or datetime.date.today().year
    fecha_ref = datetime.date(anio_actual, 6, 1)

    antiguedad_meses = calcular_antiguedad_docente(
        docente=docente, fecha_referencia=fecha_ref
    )

    cargos_activos = docente.cargos.filter(activo=True)
    regimenes_docente = set(
        c.situacion_revista for c in cargos_activos if c.situacion_revista
    )
    if not regimenes_docente:
        regimenes_docente = {REGIMEN_TIT}

    tipos_qs = (
        TipoLicencia.objects.filter(activo=True)
        .filter(
            models.Q(duracion_maxima__isnull=False)
            | models.Q(tope_anual__isnull=False)
            | models.Q(licencias_otorgadas__docente=docente)
        )
        .distinct()
        .order_by("codigo")
    )

    tipos_compatibles = []
    for tipo in tipos_qs:
        permitidos = obtener_regimenes_permitidos(tipo)
        if any(r in permitidos for r in regimenes_docente):
            tipos_compatibles.append(tipo)

    if not tipos_compatibles:
        tipos_compatibles = list(tipos_qs)

    resumen_causales = []
    total_dias_consumidos = 0

    for tipo in tipos_compatibles:
        cargo_ref = next(
            (c for c in cargos_activos if es_regimen_compatible(tipo, cargo=c)),
            cargos_activos.first(),
        )

        saldo_info = calcular_saldo_licencia(
            tipo_licencia=tipo,
            docente=docente,
            cargo=cargo_ref,
            fecha_referencia=fecha_ref,
        )

        dias_consumidos = saldo_info["dias_consumidos"]
        tope_maximo = saldo_info["tope_maximo"]
        saldo_disp = saldo_info["saldo_disponible"]
        total_dias_consumidos += dias_consumidos

        if tope_maximo is not None and tope_maximo > 0:
            porcentaje = min(100.0, round((dias_consumidos / tope_maximo) * 100, 1))
        else:
            porcentaje = 0.0

        if saldo_disp == 0:
            alerta = "danger"
        elif saldo_disp is not None and saldo_disp <= 5:
            alerta = "warning"
        else:
            alerta = "success"

        resumen_causales.append(
            {
                "tipo_id": tipo.pk,
                "codigo": tipo.codigo,
                "articulo": tipo.articulo or tipo.codigo,
                "descripcion": tipo.descripcion,
                "unidad": tipo.unidad or "Corridos",
                "periodo": saldo_info["periodo"],
                "tope_maximo": tope_maximo,
                "tope_reducido": saldo_info["tope_reducido"],
                "dias_consumidos": dias_consumidos,
                "saldo_disponible": saldo_disp,
                "porcentaje_consumido": porcentaje,
                "alerta_nivel": alerta,
                "licencias_count": saldo_info["licencias_consumidas_count"],
            }
        )

    licencias_activas_anio = LicenciaOtorgada.objects.filter(
        docente=docente,
        fecha_desde__year=anio_actual,
        estado__in=ESTADOS_LICENCIA_ACTIVAS,
    ).count()

    return {
        "docente": docente,
        "anio": anio_actual,
        "antiguedad_meses": antiguedad_meses,
        "cargos": list(cargos_activos),
        "resumen_causales": resumen_causales,
        "total_dias_consumidos": total_dias_consumidos,
        "total_licencias_otorgadas": licencias_activas_anio,
    }
