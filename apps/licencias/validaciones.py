"""
Motor de Reglas de Negocio y Validaciones para Licencias Docentes.
Ticket 17.1: Validación de Régimen de Revista (TIT, INT, SUP).
"""

from typing import Any, Iterable, Optional, Set, Union
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


def _extraer_revista_cargo(cargo: Any) -> tuple[Optional[str], str]:
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
        # Resolver cargo si es entero (ID) o instancia de CargoDocente
        if isinstance(cargo, int) or (isinstance(cargo, str) and cargo.isdigit()):
            from apps.personal.models import CargoDocente

            cargo_obj = CargoDocente.objects.filter(pk=int(cargo)).first()
            if cargo_obj:
                revista = cargo_obj.situacion_revista
        else:
            revista = getattr(cargo, "situacion_revista", None)

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
