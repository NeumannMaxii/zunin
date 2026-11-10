"""
Motor de Reglas de Negocio y Validaciones para Licencias Docentes.
Ticket 17.1: Validación de Régimen de Revista (TIT, INT, SUP).
Ticket 17.2: Validación de Antigüedad Mínima y Recorte de Topes.
"""

import datetime
from typing import Any, Iterable, Optional, Set, Tuple, Union
import unicodedata
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

REGIMEN_TIT = "TIT"
REGIMEN_INT = "INT"
REGIMEN_SUP = "SUP"

REGIMEN_CHOICES = [
    (REGIMEN_TIT, "Titular (TIT)"),
    (REGIMEN_INT, "Interino (INT)"),
    (REGIMEN_SUP, "Suplente (SUP)"),
]

REGIMEN_MAP = {
    "TIT": REGIMEN_TIT,
    "TITULAR": REGIMEN_TIT,
    "INT": REGIMEN_INT,
    "INTERINO": REGIMEN_INT,
    "SUP": REGIMEN_SUP,
    "SUPLENTE": REGIMEN_SUP,
}

REGIMEN_NOMBRES = {
    REGIMEN_TIT: "Titular",
    REGIMEN_INT: "Interino",
    REGIMEN_SUP: "Suplente",
}

TODOS_LOS_REGIMENES = {REGIMEN_TIT, REGIMEN_INT, REGIMEN_SUP}

# Constantes Ticket 17.2: Reglas de Antigüedad Ley 647-E
TOPE_ENFERMEDAD_INTERINO_MENOR_4_MESES = 10
TOPE_ENFERMEDAD_SUPLENTE_MENOR_4_MESES = 5
MESES_MINIMOS_ENFERMEDAD_COMPLETA = 4


def normalizar_regimen(valor: Any) -> Optional[str]:
    """
    Normaliza un valor de régimen / situación de revista a códigos estándar:
    'TIT', 'INT' o 'SUP'.
    Soporta variantes como 'TITULAR', 'INTERINO', 'SUPLENTE' o cadenas en minúscula.
    """
    if valor is None:
        return None
    val_clean = str(valor).strip().upper()
    if not val_clean:
        return None
    return REGIMEN_MAP.get(val_clean)


def _extraer_revista_cargo(cargo: Any) -> Tuple[Optional[str], str]:
    """Extrae la situación de revista y representación de un cargo o cargo_id."""
    if cargo is None:
        return None, ""
    if isinstance(cargo, int) or (isinstance(cargo, str) and str(cargo).isdigit()):
        from apps.personal.models import CargoDocente

        cargo_obj = CargoDocente.objects.filter(pk=int(cargo)).first()
        if cargo_obj:
            rev = getattr(cargo_obj, "situacion_revista", None)
            return rev, f" para el cargo '{cargo_obj}'"
        return None, ""
    revista = getattr(cargo, "situacion_revista", None)
    return revista, f" para el cargo '{cargo}'"


def obtener_regimenes_permitidos(tipo_licencia: Any) -> Set[str]:
    """
    Determina el conjunto de regímenes ('TIT', 'INT', 'SUP') para los que
    el tipo de licencia especificado se encuentra normativamente habilitado
    (Ticket 17.1).
    """
    if tipo_licencia is None:
        return set(TODOS_LOS_REGIMENES)

    # 1. Analizar situacion_revista_aplicable si está presente
    revista_aplicable = getattr(tipo_licencia, "situacion_revista_aplicable", None)
    regimen_campo = getattr(tipo_licencia, "regimen", None)

    permitidos: Set[str] = set()

    if revista_aplicable:
        for item in str(revista_aplicable).split(","):
            norm = normalizar_regimen(item)
            if norm:
                permitidos.add(norm)

        # Si definió un conjunto específico distinto de todos (ej: solo 'TIT' o 'INT')
        if permitidos and permitidos != TODOS_LOS_REGIMENES:
            return permitidos

        # Si situacion_revista_aplicable contenía el default genérico 'TIT,INT,SUP'
        # pero el campo regimen especifica un régimen particular (ej: INT o SUP),
        # priorizar la especificidad del régimen.
        if regimen_campo:
            norm_reg = normalizar_regimen(regimen_campo)
            if norm_reg and norm_reg in [REGIMEN_INT, REGIMEN_SUP]:
                return {norm_reg}

        if permitidos:
            return permitidos

    # 2. Si situacion_revista_aplicable no estaba seteada, usar regimen
    if regimen_campo:
        norm_reg = normalizar_regimen(regimen_campo)
        if norm_reg:
            return {norm_reg}

    # 3. Fallback estatutario universal
    return set(TODOS_LOS_REGIMENES)


def es_regimen_compatible(
    tipo_licencia: Any,
    situacion_revista: Optional[str] = None,
    cargo: Optional[Any] = None,
) -> bool:
    """
    Evalúa si un tipo de licencia es compatible con la situación de revista dada
    o con el régimen del cargo docente (Ticket 17.1).
    """
    if tipo_licencia is None:
        return True

    revista = situacion_revista
    if not revista and cargo is not None:
        revista, _ = _extraer_revista_cargo(cargo)

    # Si no se suministró ni cargo ni situación de revista, no se restringe
    if not revista:
        return True

    regimen_norm = normalizar_regimen(revista)
    if not regimen_norm:
        return False

    permitidos = obtener_regimenes_permitidos(tipo_licencia)
    return regimen_norm in permitidos


def validar_regimen_revista(
    tipo_licencia: Any,
    situacion_revista: Optional[str] = None,
    cargo: Optional[Any] = None,
) -> bool:
    """
    Aplica la regla de negocio del Ticket 17.1:
    Bloquea con ValidationError si se intenta registrar una licencia incompatible
    con el régimen del cargo docente.
    """
    if tipo_licencia is None:
        return True

    revista = situacion_revista
    cargo_str = ""
    if not revista and cargo is not None:
        revista, cargo_str = _extraer_revista_cargo(cargo)

    if not revista:
        return True

    regimen_norm = normalizar_regimen(revista)
    if not regimen_norm:
        raise ValidationError(
            f"Situación de revista '{revista}' no reconocida. Se espera TIT, INT o SUP."
        )

    permitidos = obtener_regimenes_permitidos(tipo_licencia)
    if regimen_norm not in permitidos:
        nombres_permitidos = [REGIMEN_NOMBRES.get(r, r) for r in sorted(permitidos)]
        permitidos_str = ", ".join(nombres_permitidos)
        regimen_cargo_str = REGIMEN_NOMBRES.get(regimen_norm, regimen_norm)
        cod_lic = getattr(tipo_licencia, "codigo", str(tipo_licencia))

        raise ValidationError(
            f"El tipo de licencia '{cod_lic}' no es aplicable{cargo_str} a cargos "
            f"en situación de revista {regimen_cargo_str} ({regimen_norm}). "
            f"Régimen permitido: {permitidos_str}."
        )

    return True


def filtrar_tipos_licencia_por_regimen(
    queryset: Optional[QuerySet] = None,
    situacion_revista: Optional[Union[str, Iterable[str]]] = None,
    cargo: Optional[Any] = None,
) -> QuerySet:
    """
    Filtra un QuerySet de TipoLicencia para retornar únicamente aquellos tipos
    aplicables a la situación de revista o cargo suministrado (Ticket 17.1).
    """
    from apps.licencias.models import TipoLicencia

    if queryset is None:
        queryset = TipoLicencia.objects.filter(activo=True)

    revista = situacion_revista
    if not revista and cargo is not None:
        revista, _ = _extraer_revista_cargo(cargo)

    if not revista:
        return queryset

    if isinstance(revista, (list, tuple, set)):
        regimenes = [normalizar_regimen(r) for r in revista if normalizar_regimen(r)]
    else:
        norm = normalizar_regimen(revista)
        regimenes = [norm] if norm else []

    if not regimenes:
        return queryset

    # Construir filtro de compatibilidad ORM:
    # 1. situacion_revista_aplicable contiene el régimen buscado
    # 2. O su campo regimen coincide con el régimen buscado
    q_cond = Q()
    for reg in regimenes:
        q_cond |= Q(situacion_revista_aplicable__icontains=reg) | Q(regimen=reg)

    return queryset.filter(q_cond).distinct()


# =============================================================================
# TICKET 17.2: MOTOR DE CÁLCULO DE ANTIGÜEDAD Y RECORTE DE TOPES
# =============================================================================

def calcular_antiguedad_meses(
    fecha_alta: Any,
    fecha_referencia: Optional[Any] = None,
) -> int:
    """
    Calcula los meses completos de antigüedad transcurridos desde fecha_alta
    hasta fecha_referencia (Ticket 17.2).
    Si fecha_referencia es anterior a fecha_alta, retorna 0.
    """
    if not fecha_alta:
        return 0

    from apps.licencias.calculador import parse_date_safe

    alta = parse_date_safe(fecha_alta)
    ref = (
        parse_date_safe(fecha_referencia)
        if fecha_referencia
        else datetime.date.today()
    )

    if ref < alta:
        return 0

    meses = (ref.year - alta.year) * 12 + (ref.month - alta.month)
    if ref.day < alta.day:
        meses -= 1

    return max(0, meses)


def obtener_fecha_alta_docente(
    docente: Optional[Any] = None,
    cargo: Optional[Any] = None,
) -> Optional[datetime.date]:
    """
    Determina la fecha de alta en el establecimiento para el cálculo de antigüedad:
    1. Si se provee cargo con fecha_alta, se prioriza.
    2. Si se provee docente (o deducido del cargo), busca la fecha_alta más temprana
       entre todos sus cargos en el establecimiento.
    3. Si no posee cargos con fecha_alta, utiliza fecha_creacion del docente.
    """
    from apps.licencias.calculador import parse_date_safe

    if cargo is not None:
        if isinstance(cargo, int) or (isinstance(cargo, str) and str(cargo).isdigit()):
            from apps.personal.models import CargoDocente

            cargo = CargoDocente.objects.filter(pk=int(cargo)).first()

        if cargo and getattr(cargo, "fecha_alta", None):
            return parse_date_safe(cargo.fecha_alta)

        if not docente and cargo and getattr(cargo, "docente", None):
            docente = cargo.docente

    if docente is not None:
        if isinstance(docente, int) or (
            isinstance(docente, str) and str(docente).isdigit()
        ):
            from apps.personal.models import Docente

            docente = Docente.objects.filter(pk=int(docente)).first()

        if docente:
            if hasattr(docente, "fecha_alta_establecimiento"):
                fa = docente.fecha_alta_establecimiento()
                if fa:
                    return parse_date_safe(fa)

            cargos_rel = getattr(docente, "cargos", None)
            if cargos_rel is not None:
                primer_cargo = (
                    cargos_rel.filter(fecha_alta__isnull=False)
                    .order_by("fecha_alta")
                    .first()
                )
                if primer_cargo and primer_cargo.fecha_alta:
                    return parse_date_safe(primer_cargo.fecha_alta)

            if getattr(docente, "fecha_creacion", None):
                fc = docente.fecha_creacion
                return fc.date() if hasattr(fc, "date") else fc

    return None


def calcular_antiguedad_docente(
    docente: Optional[Any] = None,
    cargo: Optional[Any] = None,
    fecha_referencia: Optional[Any] = None,
) -> int:
    """
    Calcula la antigüedad en meses de un docente en el establecimiento
    a una fecha de referencia determinada (Ticket 17.2).
    """
    alta = obtener_fecha_alta_docente(docente=docente, cargo=cargo)
    if not alta:
        return 0
    return calcular_antiguedad_meses(alta, fecha_referencia=fecha_referencia)


def es_licencia_enfermedad_comun(tipo_licencia: Any) -> bool:
    """
    Determina si un tipo de licencia corresponde a salud / enfermedad común
    sujeta a escala de antigüedad (Art. 308, 330, 339 o afección común).
    """
    if tipo_licencia is None:
        return False
    texto = (
        f"{getattr(tipo_licencia, 'codigo', '')} "
        f"{getattr(tipo_licencia, 'articulo', '')} "
        f"{getattr(tipo_licencia, 'descripcion', '')}"
    ).lower()
    norm = unicodedata.normalize("NFKD", texto)
    texto_sin_tilde = "".join([c for c in norm if not unicodedata.combining(c)])

    es_articulo = any(art in texto for art in ["308", "330", "339"])
    es_desc = (
        "enfermedad comun" in texto_sin_tilde
        or "afeccion comun" in texto_sin_tilde
    )
    return es_articulo or es_desc


def obtener_tope_efectivo_licencia(
    tipo_licencia: Any,
    cargo: Optional[Any] = None,
    docente: Optional[Any] = None,
    fecha_referencia: Optional[Any] = None,
) -> dict:
    """
    Calcula el tope efectivo en días para una licencia docente aplicando
    las restricciones de antigüedad estatutarias (Ticket 17.2).

    Si un interino/suplente posee < 4 meses de antigüedad, recorta la
    enfermedad común a 10 días (interino) o 5 días (suplente).
    """
    # 1. Determinar régimen del cargo o del tipo de licencia
    regimen = None
    if cargo is not None:
        revista, _ = _extraer_revista_cargo(cargo)
        regimen = normalizar_regimen(revista)
    if not regimen and tipo_licencia:
        regimen = normalizar_regimen(getattr(tipo_licencia, "regimen", None))
    if not regimen:
        regimen = REGIMEN_TIT

    # 2. Antigüedad en el establecimiento
    antiguedad = calcular_antiguedad_docente(
        docente=docente, cargo=cargo, fecha_referencia=fecha_referencia
    )

    es_enf = es_licencia_enfermedad_comun(tipo_licencia)
    tope_normal = getattr(tipo_licencia, "duracion_maxima", None) or getattr(
        tipo_licencia, "tope_anual", None
    )

    # 3. Restricción de Antigüedad < 4 meses en Interinos y Suplentes (Ticket 17.2)
    if es_enf and antiguedad < MESES_MINIMOS_ENFERMEDAD_COMPLETA:
        if regimen == REGIMEN_INT:
            tope_reducido = TOPE_ENFERMEDAD_INTERINO_MENOR_4_MESES  # 10 días
            return {
                "tope_dias": tope_reducido,
                "tope_reducido": True,
                "antiguedad_meses": antiguedad,
                "regimen": regimen,
                "es_enfermedad_comun": True,
                "motivo": (
                    f"Interino con {antiguedad} meses de antigüedad (< 4 meses): "
                    f"tope de enfermedad común reducido a {tope_reducido} días."
                ),
            }
        elif regimen == REGIMEN_SUP:
            tope_reducido = TOPE_ENFERMEDAD_SUPLENTE_MENOR_4_MESES  # 5 días
            return {
                "tope_dias": tope_reducido,
                "tope_reducido": True,
                "antiguedad_meses": antiguedad,
                "regimen": regimen,
                "es_enfermedad_comun": True,
                "motivo": (
                    f"Suplente con {antiguedad} meses de antigüedad (< 4 meses): "
                    f"tope de enfermedad común reducido a {tope_reducido} días."
                ),
            }

    return {
        "tope_dias": tope_normal,
        "tope_reducido": False,
        "antiguedad_meses": antiguedad,
        "regimen": regimen,
        "es_enfermedad_comun": es_enf,
        "motivo": "Aplica tope estatutario estándar.",
    }


def validar_antiguedad_minima(
    tipo_licencia: Any,
    docente: Optional[Any] = None,
    cargo: Optional[Any] = None,
    fecha_desde: Optional[Any] = None,
    fecha_hasta: Optional[Any] = None,
    dias: Optional[int] = None,
) -> bool:
    """
    Valida las restricciones de antigüedad mínima y recortes de tope (Ticket 17.2).

    Criterio de Aceptación:
    Un interino con 3 meses de antigüedad que solicita 11 días de enfermedad común
    ve su tope reducido a 10 días con bloqueo automático.
    """
    if tipo_licencia is None:
        return True

    from apps.licencias.calculador import parse_date_safe

    fecha_ref = parse_date_safe(fecha_desde) if fecha_desde else datetime.date.today()

    info_tope = obtener_tope_efectivo_licencia(
        tipo_licencia=tipo_licencia,
        cargo=cargo,
        docente=docente,
        fecha_referencia=fecha_ref,
    )

    antiguedad_meses = info_tope["antiguedad_meses"]
    tope_efectivo = info_tope["tope_dias"]
    es_reducido = info_tope["tope_reducido"]
    regimen = info_tope["regimen"]

    # Calcular cantidad de días solicitados
    dias_solicitados = None
    if dias is not None:
        dias_solicitados = int(dias)
    elif fecha_desde and fecha_hasta:
        f_desde = parse_date_safe(fecha_desde)
        f_hasta = parse_date_safe(fecha_hasta)
        if hasattr(tipo_licencia, "calcular_fechas"):
            calc = tipo_licencia.calcular_fechas(
                fecha_desde=f_desde, fecha_hasta=f_hasta
            )
            dias_solicitados = calc.dias_consumidos
        else:
            dias_solicitados = (f_hasta - f_desde).days + 1

    # Regla 1: Bloqueo automático ante superación del tope efectivo (reducido o normal)
    if dias_solicitados is not None and tope_efectivo is not None:
        if dias_solicitados > tope_efectivo:
            if es_reducido:
                regimen_str = REGIMEN_NOMBRES.get(regimen, regimen)
                raise ValidationError(
                    f"El docente posee {antiguedad_meses} meses de antigüedad en el "
                    f"establecimiento (menor a 4 meses requeridos para el régimen "
                    f"{regimen_str}). El tope para enfermedad común se encuentra "
                    f"reducido a {tope_efectivo} días. "
                    f"Se intentaron solicitar {dias_solicitados} días."
                )
            else:
                cod = getattr(tipo_licencia, "codigo", "")
                raise ValidationError(
                    f"La cantidad de días solicitados ({dias_solicitados}) excede "
                    f"el tope estatutario de {tope_efectivo} días para la licencia "
                    f"'{cod}'."
                )

    # Regla 2: Licencias generales con antiguedad_minima_meses obligatoria fija
    antiguedad_minima = getattr(tipo_licencia, "antiguedad_minima_meses", 0) or 0
    if antiguedad_minima > 0 and not info_tope["es_enfermedad_comun"]:
        if antiguedad_meses < antiguedad_minima:
            raise ValidationError(
                f"El tipo de licencia '{tipo_licencia.codigo}' exige una "
                f"antigüedad mínima de {antiguedad_minima} meses en el "
                f"establecimiento. El docente registra {antiguedad_meses} "
                f"meses a la fecha de inicio."
            )

    return True


def validar_solicitud_licencia(
    tipo_licencia: Any,
    docente: Optional[Any] = None,
    cargo: Optional[Any] = None,
    fecha_desde: Optional[Any] = None,
    fecha_hasta: Optional[Any] = None,
    dias: Optional[int] = None,
    situacion_revista: Optional[str] = None,
) -> bool:
    """
    Orquesta integralmente las validaciones de negocio de licencias:
    - Ticket 17.1: Régimen de revista (TIT, INT, SUP).
    - Ticket 17.2: Antigüedad mínima y tope reducido por antigüedad.
    """
    validar_regimen_revista(
        tipo_licencia=tipo_licencia,
        situacion_revista=situacion_revista,
        cargo=cargo,
    )
    validar_antiguedad_minima(
        tipo_licencia=tipo_licencia,
        docente=docente,
        cargo=cargo,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        dias=dias,
    )
    return True
