"""
Servicios de negocio para el módulo de Licencias y Planillas Mensuales.
Implementa el motor de generación mensual consolidada (RN-11).
"""

import datetime
import unicodedata
from django.apps import apps
from django.db import models, transaction


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
    RenglonPlanillaMensual = apps.get_model(
        "licencias", "RenglonPlanillaMensual"
    )

    with transaction.atomic():
        # 1. Precarga de días no laborables en un set en memoria
        dias_no_laborables = set(
            DiaNoLaborable.objects.values_list("fecha", flat=True)
        )

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

            # 4. Agrupamiento de bloques contiguos (Adyacencia)
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
                                and dia not in dias_no_laborables
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

            # 5. Generación de renglones por bloque
            for bloque in bloques:
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
                        # Validación de vigencia del cargo día por día
                        if cargo.es_designacion_vigente(dia_cursor):
                            total_horas += cargo.obtener_horas_en_fecha(
                                dia_cursor
                            )
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
                cargos_a_crear = []
                for cargo, horas in cargos_con_horas:
                    renglon_existente = RenglonPlanillaMensual.objects.filter(
                        docente=docente,
                        cargo=cargo,
                        mes=mes,
                        anio=anio,
                        desde=bloque["desde"],
                        hasta=bloque["hasta"],
                    ).first()

                    if renglon_existente:
                        renglones_resultado.append(renglon_existente)
                        continue

                    cargos_a_crear.append((cargo, horas))

                # Si todos los renglones ya existían para este bloque, continuar
                if not cargos_a_crear:
                    continue

                num_disp = f"{correlativo:03d}/{anio}"
                correlativo += 1

                for reg in bloque["registros"]:
                    reg.numero_disposicion = num_disp
                    reg.save(update_fields=["numero_disposicion"])

                for cargo, horas in cargos_a_crear:
                    renglon = RenglonPlanillaMensual.objects.create(
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
                    renglones_resultado.append(renglon)

        return renglones_resultado
