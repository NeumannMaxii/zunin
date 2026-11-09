"""
Servicios de negocio del módulo Core para el sistema Zunin.
Ticket 12 (RF-18): Panel de Alertas Preventivas de Inasistencias.
"""

from django.db.models import (
    Case,
    CharField,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Q,
    Value,
    When,
)
from apps.personal.models import Docente


def obtener_panel_alertas_docentes(limite_legal=15, anio=None, solo_alertas=False):
    """
    Ticket 12 (RF-18): Calcula el porcentaje de inasistencia docente respecto al
    límite legal anual (tope normativo) utilizando annotate con ExpressionWrapper
    para evitar consultas N+1 e iteraciones sobre la base de datos.

    Fórmula: (Faltas 'I' / Límite Legal Anual) * 100

    Umbrales Visuales:
    - Porcentaje >= 70% (y <= 100%) -> PRECAUCION (Alerta Naranja)
    - Porcentaje > 100% -> CRITICO (Alerta Roja)
    - Porcentaje < 70% -> NORMAL

    Retorna un QuerySet de Docente anotado con:
    - faltas_count (int)
    - porcentaje (float)
    - nivel_alerta ('NORMAL', 'PRECAUCION', 'CRITICO')
    """
    if limite_legal is None or limite_legal <= 0:
        limite_legal = 15

    filtro_asistencias = Q(asistencias__marca_diaria__in=["I", "INA"]) | Q(
        asistencias__estado="AUSENTE", asistencias__justifica=False
    )
    if anio is not None:
        filtro_asistencias &= Q(asistencias__fecha__year=anio)

    queryset = (
        Docente.objects.filter(activo=True)
        .annotate(
            faltas_count=Count("asistencias", filter=filtro_asistencias),
        )
        .annotate(
            porcentaje=ExpressionWrapper(
                F("faltas_count") * 100.0 / float(limite_legal),
                output_field=FloatField(),
            )
        )
        .annotate(
            nivel_alerta=Case(
                When(porcentaje__gt=100.0, then=Value("CRITICO")),
                When(porcentaje__gte=70.0, then=Value("PRECAUCION")),
                default=Value("NORMAL"),
                output_field=CharField(),
            )
        )
        .order_by("-porcentaje", "apellido", "nombre")
    )

    if solo_alertas:
        queryset = queryset.filter(porcentaje__gte=70.0)

    return queryset
