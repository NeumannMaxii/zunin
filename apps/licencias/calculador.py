"""
Motor de cálculo de fechas, unidades y días para el régimen de licencias.
Ticket 16.2: Cálculo automático de fecha de reintegro y días consumidos.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any, Iterable, List, Optional, Set, Union
from django.apps import apps
from django.core.exceptions import ValidationError

# Constantes oficiales de unidades de cálculo
UNIDAD_HABILES = "HABILES"
UNIDAD_CORRIDOS = "CORRIDOS"

UNIDADES_VALIDAS = {UNIDAD_HABILES, UNIDAD_CORRIDOS}


@dataclass
class CalculoFechasLicencia:
    """
    Estructura que encapsula el resultado integral del cómputo de una licencia.
    """

    fecha_desde: datetime.date
    fecha_hasta: datetime.date
    fecha_reintegro: datetime.date
    dias_consumidos: int
    dias_habiles: int
    dias_corridos: int
    unidad: str
    dias_feriados: List[datetime.date] = field(default_factory=list)
    fines_de_semana: int = 0

    def to_dict(self) -> dict:
        """Serializa el resultado a un diccionario primitivo para respuestas JSON."""
        return {
            "fecha_desde": self.fecha_desde.isoformat(),
            "fecha_hasta": self.fecha_hasta.isoformat(),
            "fecha_reintegro": self.fecha_reintegro.isoformat(),
            "dias_consumidos": self.dias_consumidos,
            "dias_habiles": self.dias_habiles,
            "dias_corridos": self.dias_corridos,
            "unidad": self.unidad,
            "dias_feriados": [f.isoformat() for f in self.dias_feriados],
            "fines_de_semana": self.fines_de_semana,
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


def parse_date_safe(val: Union[datetime.date, datetime.datetime, str]) -> datetime.date:
    """Convierte de forma segura strings ISO o datetimes a datetime.date."""
    if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            raise ValidationError("La fecha no puede estar vacía.")
        try:
            return datetime.date.fromisoformat(val_clean)
        except ValueError as exc:
            raise ValidationError(
                f"Formato de fecha inválido '{val_clean}'. Se espera YYYY-MM-DD."
            ) from exc
    raise ValidationError(f"Tipo de dato inválido para fecha: {type(val).__name__}.")


def normalizar_unidad(
    unidad: Optional[str] = None, tipo_licencia: Optional[Any] = None
) -> str:
    """
    Normaliza y determina la unidad de cómputo (HABILES o CORRIDOS).

    Prioridad:
    1. Si se proporciona `unidad` explícita, se normaliza.
    2. Si se proporciona `tipo_licencia`, se inspecciona su campo/propiedad `unidad`,
       o los textos en `cantidad_duracion` y `descripcion`.
    3. Si no se puede determinar, el valor por defecto estatutario es HABILES.
    """
    def _es_corrido(val: str) -> bool:
        t = val.upper()
        return "CORR" in t or "CALEND" in t

    def _es_habil(val: str) -> bool:
        t = val.upper()
        return "HAB" in t or "HÁB" in t or "LABOR" in t

    if unidad:
        u = str(unidad).strip()
        if _es_corrido(u):
            return UNIDAD_CORRIDOS
        if _es_habil(u):
            return UNIDAD_HABILES

    if tipo_licencia is not None:
        if hasattr(tipo_licencia, "unidad") and tipo_licencia.unidad:
            u = str(tipo_licencia.unidad).strip()
            if _es_corrido(u):
                return UNIDAD_CORRIDOS
            if _es_habil(u):
                return UNIDAD_HABILES

        cant = getattr(tipo_licencia, "cantidad_duracion", "") or ""
        desc = getattr(tipo_licencia, "descripcion", "") or ""
        combinado = f"{cant} {desc}".lower()
        if "corrido" in combinado or "calendario" in combinado:
            return UNIDAD_CORRIDOS
        if "habil" in combinado or "hábil" in combinado or "labor" in combinado:
            return UNIDAD_HABILES

    return UNIDAD_HABILES


def _obtener_feriados_set(
    feriados: Optional[Iterable[datetime.date]] = None,
    rango_desde: Optional[datetime.date] = None,
    rango_hasta: Optional[datetime.date] = None,
) -> Set[datetime.date]:
    """
    Normaliza el conjunto de feriados. Si no se especifican, consulta el modelo
    DiaNoLaborable si está disponible en apps de Django.
    """
    if feriados is not None:
        return {parse_date_safe(f) for f in feriados}

    try:
        DiaNoLaborable = apps.get_model("asistencia", "DiaNoLaborable")
        qs = DiaNoLaborable.objects.all()
        if rango_desde and rango_hasta:
            # Margen de seguridad de 30 días para calcular reintegro posterior
            margen_hasta = rango_hasta + datetime.timedelta(days=35)
            qs = qs.filter(fecha__range=[rango_desde, margen_hasta])
        return set(qs.values_list("fecha", flat=True))
    except Exception:
        return set()


def es_dia_habil(
    fecha: Union[datetime.date, str],
    feriados: Optional[Iterable[datetime.date]] = None,
) -> bool:
    """
    Evalúa si una fecha dada es día hábil/laborable.
    - Fines de semana (sábado=5, domingo=6) NO son hábiles.
    - Fechas registradas como feriado o día no laborable NO son hábiles.
    """
    f = parse_date_safe(fecha)
    if f.weekday() >= 5:
        return False

    feriados_set = _obtener_feriados_set(feriados, f, f)
    return f not in feriados_set


def obtener_siguiente_dia_habil(
    fecha: Union[datetime.date, str],
    feriados: Optional[Iterable[datetime.date]] = None,
) -> datetime.date:
    """
    Retorna el primer día hábil estrictamente posterior a `fecha`.
    Avanza día a día saltando fines de semana y feriados.
    """
    cursor = parse_date_safe(fecha) + datetime.timedelta(days=1)
    feriados_set = _obtener_feriados_set(
        feriados, cursor, cursor + datetime.timedelta(days=30)
    )

    while True:
        if cursor.weekday() < 5 and cursor not in feriados_set:
            return cursor
        cursor += datetime.timedelta(days=1)


def calcular_fecha_reintegro(
    fecha_hasta: Union[datetime.date, str],
    feriados: Optional[Iterable[datetime.date]] = None,
) -> datetime.date:
    """
    Calcula la fecha de reintegro laboral a partir del último día de la licencia.
    Alias semántico de `obtener_siguiente_dia_habil`.
    """
    return obtener_siguiente_dia_habil(fecha_hasta, feriados=feriados)


def contar_dias_corridos(
    fecha_desde: Union[datetime.date, str],
    fecha_hasta: Union[datetime.date, str],
) -> int:
    """Calcula la cantidad de días calendario entre dos fechas (inclusivas)."""
    f_desde = parse_date_safe(fecha_desde)
    f_hasta = parse_date_safe(fecha_hasta)
    if f_hasta < f_desde:
        raise ValidationError(
            "La fecha de fin no puede ser anterior a la fecha de inicio."
        )
    return (f_hasta - f_desde).days + 1


def contar_dias_habiles(
    fecha_desde: Union[datetime.date, str],
    fecha_hasta: Union[datetime.date, str],
    feriados: Optional[Iterable[datetime.date]] = None,
) -> int:
    """
    Calcula la cantidad de días hábiles entre dos fechas (inclusivas),
    omitiendo fines de semana y feriados.
    """
    f_desde = parse_date_safe(fecha_desde)
    f_hasta = parse_date_safe(fecha_hasta)
    if f_hasta < f_desde:
        raise ValidationError(
            "La fecha de fin no puede ser anterior a la fecha de inicio."
        )

    feriados_set = _obtener_feriados_set(feriados, f_desde, f_hasta)
    habiles = 0
    cursor = f_desde
    while cursor <= f_hasta:
        if cursor.weekday() < 5 and cursor not in feriados_set:
            habiles += 1
        cursor += datetime.timedelta(days=1)

    return habiles


def calcular_fechas_licencia(
    fecha_desde: Union[datetime.date, str],
    dias: Optional[int] = None,
    fecha_hasta: Optional[Union[datetime.date, str]] = None,
    unidad: Optional[str] = None,
    tipo_licencia: Optional[Any] = None,
    feriados: Optional[Iterable[datetime.date]] = None,
) -> CalculoFechasLicencia:
    """
    Motor central de cálculo de fechas de licencia y reintegro (Ticket 16.2).

    Permite:
    1. Si se provee `fecha_desde` y `dias`: calcula `fecha_hasta`, omitiendo fines
       de semana y feriados si `unidad == 'HABILES'`, o proyectando días corridos
       si `unidad == 'CORRIDOS'`.
    2. Si se provee `fecha_desde` y `fecha_hasta`: calcula los días consumidos
       según la unidad correspondiente.
    3. Determina siempre la fecha de reintegro (primer día hábil posterior
       a fecha_hasta).

    Criterio de Aceptación:
    Una licencia de 5 días hábiles que inicia un viernes calcula correctamente
    su finalización el jueves siguiente y su reintegro el viernes, saltando el
    fin de semana intermedio.
    """
    f_desde = parse_date_safe(fecha_desde)
    unidad_norm = normalizar_unidad(unidad=unidad, tipo_licencia=tipo_licencia)

    if dias is None and fecha_hasta is None:
        raise ValidationError(
            "Debe especificar la cantidad de días o la fecha de finalización."
        )

    if dias is not None:
        try:
            dias_int = int(dias)
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                f"La cantidad de días debe ser un número entero: {dias}."
            ) from exc

        if dias_int <= 0:
            raise ValidationError("La cantidad de días debe ser mayor a 0.")
    else:
        dias_int = None

    if fecha_hasta is not None:
        f_hasta_in = parse_date_safe(fecha_hasta)
        if f_hasta_in < f_desde:
            raise ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )
    else:
        f_hasta_in = None

    # Estimar horizonte temporal para precargar feriados
    margen_dias = (dias_int * 3) if dias_int else (f_hasta_in - f_desde).days + 20
    margen_dias = max(margen_dias, 60)
    horizonte_hasta = f_desde + datetime.timedelta(days=margen_dias)

    feriados_set = _obtener_feriados_set(feriados, f_desde, horizonte_hasta)

    # 1. Proyección a partir de cantidad de días solicitados
    if dias_int is not None and f_hasta_in is None:
        if unidad_norm == UNIDAD_CORRIDOS:
            f_hasta = f_desde + datetime.timedelta(days=dias_int - 1)
        else:
            # Unidad HABILES: acumular la cantidad exacta de días laborables
            cursor = f_desde
            habiles_acumulados = 0
            while True:
                if cursor.weekday() < 5 and cursor not in feriados_set:
                    habiles_acumulados += 1
                    if habiles_acumulados == dias_int:
                        f_hasta = cursor
                        break
                cursor += datetime.timedelta(days=1)
    else:
        # 2. Rango explícito suministrado
        f_hasta = f_hasta_in

    # Calcular estadísticas del período [f_desde, f_hasta]
    dias_corridos_total = (f_hasta - f_desde).days + 1
    dias_habiles_total = 0
    feriados_encontrados = []
    fines_semana_count = 0

    cursor = f_desde
    while cursor <= f_hasta:
        es_fds = cursor.weekday() >= 5
        es_fer = cursor in feriados_set

        if es_fds:
            fines_semana_count += 1
        elif es_fer:
            feriados_encontrados.append(cursor)
        else:
            dias_habiles_total += 1

        cursor += datetime.timedelta(days=1)

    # Días consumidos según la unidad del tipo
    if unidad_norm == UNIDAD_HABILES:
        dias_consumidos = dias_habiles_total
    else:
        dias_consumidos = dias_corridos_total

    # Fecha de reintegro: siempre el próximo día hábil posterior a fecha_hasta
    fecha_reintegro = obtener_siguiente_dia_habil(f_hasta, feriados=feriados_set)

    return CalculoFechasLicencia(
        fecha_desde=f_desde,
        fecha_hasta=f_hasta,
        fecha_reintegro=fecha_reintegro,
        dias_consumidos=dias_consumidos,
        dias_habiles=dias_habiles_total,
        dias_corridos=dias_corridos_total,
        unidad=unidad_norm,
        dias_feriados=feriados_encontrados,
        fines_de_semana=fines_semana_count,
    )


class MotorCalculoLicencia:
    """
    Clase orientada a objetos que encapsula el motor de cálculo de licencias.
    """

    UNIDAD_HABILES = UNIDAD_HABILES
    UNIDAD_CORRIDOS = UNIDAD_CORRIDOS

    @classmethod
    def es_dia_habil(
        cls,
        fecha: Union[datetime.date, str],
        feriados: Optional[Iterable[datetime.date]] = None,
    ) -> bool:
        return es_dia_habil(fecha, feriados=feriados)

    @classmethod
    def siguiente_dia_habil(
        cls,
        fecha: Union[datetime.date, str],
        feriados: Optional[Iterable[datetime.date]] = None,
    ) -> datetime.date:
        return obtener_siguiente_dia_habil(fecha, feriados=feriados)

    @classmethod
    def calcular_reintegro(
        cls,
        fecha_hasta: Union[datetime.date, str],
        feriados: Optional[Iterable[datetime.date]] = None,
    ) -> datetime.date:
        return calcular_fecha_reintegro(fecha_hasta, feriados=feriados)

    @classmethod
    def contar_habiles(
        cls,
        fecha_desde: Union[datetime.date, str],
        fecha_hasta: Union[datetime.date, str],
        feriados: Optional[Iterable[datetime.date]] = None,
    ) -> int:
        return contar_dias_habiles(fecha_desde, fecha_hasta, feriados=feriados)

    @classmethod
    def contar_corridos(
        cls,
        fecha_desde: Union[datetime.date, str],
        fecha_hasta: Union[datetime.date, str],
    ) -> int:
        return contar_dias_corridos(fecha_desde, fecha_hasta)

    @classmethod
    def calcular(
        cls,
        fecha_desde: Union[datetime.date, str],
        dias: Optional[int] = None,
        fecha_hasta: Optional[Union[datetime.date, str]] = None,
        unidad: Optional[str] = None,
        tipo_licencia: Optional[Any] = None,
        feriados: Optional[Iterable[datetime.date]] = None,
    ) -> CalculoFechasLicencia:
        return calcular_fechas_licencia(
            fecha_desde=fecha_desde,
            dias=dias,
            fecha_hasta=fecha_hasta,
            unidad=unidad,
            tipo_licencia=tipo_licencia,
            feriados=feriados,
        )
