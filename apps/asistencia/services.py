"""
Servicios de negocio para apps.asistencia.
Implementa Ticket 3.8: Directiva de Transaccionalidad Atómica en Carga Masiva (Ticket 5)
y Justificaciones por Lote (Ticket 7).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from apps.asistencia.models import RegistroAsistencia
from apps.core.audit import audit_save


def guardar_asistencia_diaria_masiva(lote_datos, usuario=None, request=None):
    """
    Carga Diaria Masiva de Asistencias (Ticket 5 y 3.8).
    Garantiza que todo el bucle de guardado se ejecute de manera atómica bajo
    'with transaction.atomic():' y registre auditoría con audit_save().

    Si cualquier fila del lote arroja ValidationError o IntegrityError:
    1. Se realiza rollback total inmediato (0 registros persistidos).
    2. Si 'request' está presente, se notifica con django.contrib.messages.error().
    3. Se relanza la excepción para trazabilidad y testing.
    """
    try:
        with transaction.atomic():
            registros_guardados = []
            for item in lote_datos:
                if isinstance(item, RegistroAsistencia):
                    instancia = item
                elif isinstance(item, dict):
                    instancia = RegistroAsistencia(**item)
                else:
                    raise ValidationError(
                        f"Elemento del lote no válido: tipo {type(item)} no soportado."
                    )

                created = instancia.pk is None
                audit_save(instancia, user=usuario, created=created)
                registros_guardados.append(instancia)

            return registros_guardados

    except (ValidationError, IntegrityError, Exception) as exc:
        if request is not None:
            messages.error(
                request,
                f"Error al procesar la carga masiva de asistencias: {exc}. "
                "Se revirtieron todas las operaciones y no se guardó ningún registro.",
            )
        raise exc


def justificar_lote_asistencias(lote_datos, usuario=None, request=None):
    """
    Justificaciones por Lote (Ticket 7 y 3.8).
    Garantiza transaccionalidad atómica bajo 'with transaction.atomic():'.

    Acepta una lista de items, donde cada item puede ser:
    - dict con claves 'asistencia' (o 'id'), 'nueva_marca', 'tipo_licencia'
    - tupla (asistencia_o_id, nueva_marca, tipo_licencia)

    Si cualquier fila arroja ValidationError o IntegrityError:
    1. Se realiza rollback total inmediato.
    2. Si 'request' está presente, se notifica con messages.error().
    3. Se relanza la excepción.
    """
    try:
        with transaction.atomic():
            registros_justificados = []
            for item in lote_datos:
                if isinstance(item, dict):
                    asistencia = (
                        item.get("asistencia")
                        or item.get("registro")
                        or item.get("id")
                    )
                    nueva_marca = item.get("nueva_marca") or item.get("marca")
                    tipo_licencia = item.get("tipo_licencia")
                elif isinstance(item, (tuple, list)):
                    asistencia = item[0]
                    nueva_marca = item[1]
                    tipo_licencia = item[2] if len(item) > 2 else None
                else:
                    raise ValidationError(
                        f"Formato de item de justificación no válido: {type(item)}."
                    )

                if isinstance(asistencia, int):
                    asistencia = RegistroAsistencia.objects.get(pk=asistencia)

                asistencia.justificar_con_formulario(
                    nueva_marca=nueva_marca,
                    tipo_licencia=tipo_licencia,
                    usuario=usuario,
                )
                registros_justificados.append(asistencia)

            return registros_justificados

    except (ValidationError, IntegrityError, Exception) as exc:
        if request is not None:
            messages.error(
                request,
                f"Error al procesar las justificaciones por lote: {exc}. "
                "Se revirtieron todos los cambios del lote.",
            )
        raise exc


# Alias semánticos
cargar_asistencia_masiva = guardar_asistencia_diaria_masiva
procesar_justificaciones_lote = justificar_lote_asistencias
