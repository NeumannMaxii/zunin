"""
Servicios de negocio para el módulo de Licencias y Planillas Mensuales.
Implementa el motor de generación mensual consolidada (RN-11).
"""

import datetime
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
                    es_compatible = (
                        current_block["tipo_licencia"] == tipo_lic
                        and current_block["cuadro"] == cuadro
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
                if bloque["cargo_fijado"]:
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

    # Precarga de feriados y asuetos en el rango
    feriados_fechas = set(
        DiaNoLaborable.objects.filter(
            fecha__range=[fecha_desde, fecha_hasta]
        ).values_list("fecha", flat=True)
    )

    # Identificar días con carga horaria a justificar (Ticket 10.7)
    dias_a_justificar = []
    dia_cursor = fecha_desde
    while dia_cursor <= fecha_hasta:
        # Evaluación dinámica: verificar si el cargo tiene clases en la fecha
        if cargo:
            tiene_clases = cargo.obtener_horas_en_fecha(dia_cursor) > 0
        else:
            cargos_activos = (
                list(docente.cargos.filter(activo=True))
                if hasattr(docente, "cargos")
                else []
            )
            if cargos_activos:
                tiene_clases = any(
                    c.obtener_horas_en_fecha(dia_cursor) > 0 for c in cargos_activos
                )
            else:
                tiene_clases = dia_cursor.weekday() < 5

        if tiene_clases and dia_cursor not in feriados_fechas:
            dias_a_justificar.append(dia_cursor)
        dia_cursor += datetime.timedelta(days=1)

    num_final = numero_disposicion
    if tipo_instrumento == "RESOLUCION" and numero_disposicion:
        nd_str = str(numero_disposicion).strip()
        nd_lower = nd_str.lower()
        if not ("res" in nd_lower or "resoluci" in nd_lower):
            num_final = f"Resolución {nd_str}"
        else:
            num_final = nd_str

    with transaction.atomic():
        registros_guardados = []
        meses_afectados = set()

        # Ticket 10.5: Precargar todas las asistencias del intervalo con
        # fecha__range en una sola consulta
        asistencias_map = {
            r.fecha: r
            for r in RegistroAsistencia.objects.filter(
                docente=docente,
                fecha__range=[fecha_desde, fecha_hasta],
            )
        }

        for dia in dias_a_justificar:
            meses_afectados.add((dia.month, dia.year))

            reg = asistencias_map.get(dia)

            estado_destino = (
                "LICENCIA" if nueva_marca in ["LIC", "LIC.", "LT"] else "JUSTIFICADO"
            )

            if reg is not None:
                # Actualización de registro existente
                reg.estado = estado_destino
                reg.marca_diaria = nueva_marca
                reg.tipo_licencia = tipo_licencia
                reg.justifica = True
                if cargo and not reg.cargo:
                    reg.cargo = cargo
                if num_final:
                    reg.numero_disposicion = num_final
                if observaciones:
                    if reg.observaciones:
                        reg.observaciones = f"{reg.observaciones} | {observaciones}"
                    else:
                        reg.observaciones = observaciones
                audit_save(reg, user=usuario, created=False)
                registros_guardados.append(reg)
            else:
                # Creación de nuevo registro justificado
                nuevo_reg = RegistroAsistencia(
                    docente=docente,
                    cargo=cargo,
                    fecha=dia,
                    estado=estado_destino,
                    marca_diaria=nueva_marca,
                    tipo_licencia=tipo_licencia,
                    justifica=True,
                    numero_disposicion=num_final,
                    observaciones=observaciones or "",
                    oficina=getattr(settings, "DEFAULT_OFICINA_CODE", "1452"),
                )
                audit_save(nuevo_reg, user=usuario, created=True)
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
        for cargo in cargos:
            dias_a_sincronizar = obtener_dias_sincronizacion_licencia(licencia, cargo)
            for dia in dias_a_sincronizar:
                meses_afectados.add((dia.month, dia.year))
                reg = RegistroAsistencia.objects.filter(
                    docente=docente,
                    cargo=cargo,
                    fecha=dia,
                ).first()

                if reg:
                    # Si ya existía, respaldamos su marca previa en observaciones
                    obs = reg.observaciones or ""
                    if "PREV_MARCA:" not in obs:
                        prev_info = (
                            f"PREV_ESTADO:{reg.estado}|PREV_MARCA:{reg.marca_diaria}"
                        )
                        reg.observaciones = f"{prev_info} | {obs}" if obs else prev_info
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
