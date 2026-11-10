"""
Servicios de negocio para apps.asistencia.
Implementa Ticket 3.8: Directiva de Transaccionalidad Atómica en Carga Masiva,
Justificaciones por Lote (Ticket 7), y Consulta Avanzada (Ticket 12.6).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from apps.asistencia.models import RegistroAsistencia
from apps.core.audit import audit_save
from apps.licencias.models import TipoLicencia


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
                        item.get("asistencia") or item.get("registro") or item.get("id")
                    )
                    nueva_marca = item.get("nueva_marca") or item.get("marca")
                    tipo_licencia = item.get("tipo_licencia")
                elif isinstance(item, (tuple, list)):
                    if len(item) < 2:
                        raise ValidationError(
                            "Cada elemento de tipo lista/tupla debe incluir "
                            "registro de asistencia y nueva marca."
                        )
                    asistencia = item[0]
                    nueva_marca = item[1]
                    tipo_licencia = item[2] if len(item) > 2 else None
                else:
                    raise ValidationError(
                        f"Formato de item de justificación no válido: {type(item)}."
                    )

                if isinstance(asistencia, str) and asistencia.strip().isdigit():
                    asistencia = int(asistencia.strip())

                if isinstance(asistencia, int):
                    asistencia_id = asistencia
                    asistencia = RegistroAsistencia.objects.filter(
                        pk=asistencia_id
                    ).first()
                    if asistencia is None:
                        raise ValidationError(
                            f"El registro de asistencia #{asistencia_id} no existe."
                        )
                elif not isinstance(asistencia, RegistroAsistencia):
                    raise ValidationError(
                        "Debe especificar un registro de asistencia válido."
                    )

                if isinstance(tipo_licencia, int) or (
                    isinstance(tipo_licencia, str) and tipo_licencia.strip()
                ):
                    tl_val = str(tipo_licencia).strip()
                    if isinstance(tipo_licencia, int) or tl_val.isdigit():
                        tl_obj = TipoLicencia.objects.filter(pk=int(tl_val)).first()
                    else:
                        tl_obj = TipoLicencia.objects.filter(
                            codigo__iexact=tl_val
                        ).first()
                    if tl_obj is None:
                        raise ValidationError(
                            f"Tipo de licencia no encontrado: '{tipo_licencia}'."
                        )
                    tipo_licencia = tl_obj
                elif isinstance(tipo_licencia, str) and not tipo_licencia.strip():
                    tipo_licencia = None

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


def filtrar_asistencias_multicriterio(
    queryset=None,
    fecha_desde=None,
    fecha_hasta=None,
    dni_o_apellido=None,
    dni=None,
    apellido=None,
    estado=None,
    marca=None,
    marca_diaria=None,
    estado_marca=None,
    materia=None,
    materia_id=None,
):
    """
    Filtra registros de asistencia combinando múltiples criterios (Ticket 12.6):
    - fecha_desde, fecha_hasta: Rango de fechas inclusivo.
    - dni_o_apellido, dni, apellido: Búsqueda sobre Docente.
    - estado, marca, marca_diaria, estado_marca: Búsqueda sobre estado o marca diaria.
    - materia, materia_id: Búsqueda sobre CargoDocente -> EspacioCurricular.
    """
    if queryset is None:
        queryset = RegistroAsistencia.objects.all()

    # 1. Rango de fechas
    if isinstance(fecha_desde, str):
        parsed = parse_date(fecha_desde)
        if parsed:
            fecha_desde = parsed
    if isinstance(fecha_hasta, str):
        parsed = parse_date(fecha_hasta)
        if parsed:
            fecha_hasta = parsed

    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)

    # 2. DNI o Apellido del Docente
    if dni_o_apellido and str(dni_o_apellido).strip():
        term = str(dni_o_apellido).strip()
        queryset = queryset.filter(
            Q(docente__dni__icontains=term)
            | Q(docente__apellido__icontains=term)
            | Q(docente__nombre__icontains=term)
        )
    if dni and str(dni).strip():
        queryset = queryset.filter(docente__dni__icontains=str(dni).strip())
    if apellido and str(apellido).strip():
        queryset = queryset.filter(docente__apellido__icontains=str(apellido).strip())

    # 3. Estado de Asistencia
    estado_val = estado or estado_marca
    if estado_val and str(estado_val).strip():
        e = str(estado_val).strip()
        estados_validos = dict(RegistroAsistencia.ESTADO_CHOICES)
        marcas_validas = dict(RegistroAsistencia.MARCA_DIARIA_CHOICES)
        if e in estados_validos:
            queryset = queryset.filter(estado=e)
        elif e in marcas_validas:
            queryset = queryset.filter(marca_diaria=e)
        else:
            queryset = queryset.filter(
                Q(estado__icontains=e) | Q(marca_diaria__icontains=e)
            )

    # 4. Marca Diaria
    marca_val = marca or marca_diaria
    if marca_val and str(marca_val).strip():
        m = str(marca_val).strip()
        marcas_validas = dict(RegistroAsistencia.MARCA_DIARIA_CHOICES)
        estados_validos = dict(RegistroAsistencia.ESTADO_CHOICES)
        if m in marcas_validas:
            queryset = queryset.filter(marca_diaria=m)
        elif m in estados_validos:
            queryset = queryset.filter(estado=m)
        else:
            queryset = queryset.filter(
                Q(marca_diaria__icontains=m) | Q(estado__icontains=m)
            )

    # 5. Materia / Espacio Curricular
    if materia_id:
        queryset = queryset.filter(cargo__materia_id=materia_id)
    elif materia is not None and (hasattr(materia, "pk") or str(materia).strip()):
        if hasattr(materia, "pk"):
            queryset = queryset.filter(cargo__materia=materia)
        elif isinstance(materia, int):
            queryset = queryset.filter(
                Q(cargo__materia_id=materia)
                | Q(cargo__materia__nombre__icontains=str(materia))
            )
        else:
            mat_str = str(materia).strip()
            if mat_str.isdigit():
                queryset = queryset.filter(
                    Q(cargo__materia_id=int(mat_str))
                    | Q(cargo__materia__nombre__icontains=mat_str)
                    | Q(cargo__materia__codigo__icontains=mat_str)
                )
            else:
                queryset = queryset.filter(
                    Q(cargo__materia__nombre__icontains=mat_str)
                    | Q(cargo__materia__codigo__icontains=mat_str)
                )

    return queryset


# Alias semánticos
cargar_asistencia_masiva = guardar_asistencia_diaria_masiva
procesar_justificaciones_lote = justificar_lote_asistencias
consultar_asistencias_multicriterio = filtrar_asistencias_multicriterio
consultar_asistencias = filtrar_asistencias_multicriterio
