"""
Management command y utilidades de importación CSV de legajos docentes y cargos.
Implementa Ticket 3.8: Sincronización Dual de fechas históricas y parseo robusto.
"""

import csv
import datetime
import io
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


FORMATOS_FECHA = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%Y/%m/%d",
)


def parsear_fecha(valor):
    """
    Intenta parsear un valor a un objeto datetime.date.
    Acepta strings, datetime.date o datetime.datetime.
    Retorna None si no es una fecha válida.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor

    cadena = str(valor).strip()
    if not cadena:
        return None

    for fmt in FORMATOS_FECHA:
        try:
            return datetime.datetime.strptime(cadena, fmt).date()
        except ValueError:
            continue
    return None


def parsear_fecha_desde(valor):
    """
    Parsea la columna 'DESDE':
    - Si el valor es una fecha válida: (datetime.date, cadena_original)
    - Si contiene 'SIN INICIO' o está vacío: (None, 'SIN INICIO')
    - Si es otra cadena no parseable: (None, cadena_original)
    """
    if valor is None:
        return None, "SIN INICIO"

    cadena = str(valor).strip()
    if not cadena or cadena.upper() in ["SIN INICIO", "SIN_INICIO"]:
        return None, "SIN INICIO"

    f_dt = parsear_fecha(cadena)
    if f_dt is not None:
        return f_dt, cadena

    return None, cadena


def parsear_fecha_hasta(valor):
    """
    Parsea la columna 'HASTA' con Sincronización Dual (Ticket 3.8):
    - Si el valor es una fecha válida (ej: '15/03/2026'):
      fecha_baja = datetime.date Y hasta_texto = '15/03/2026'.
    - Si contiene 'SIN TERMINO', 'SIN TÉRMINO' o está vacío:
      fecha_baja = None Y hasta_texto = 'SIN TÉRMINO'.
    - Si contiene otra cadena no parseable:
      fecha_baja = None Y hasta_texto = cadena_original.
    """
    if valor is None:
        return None, "SIN TÉRMINO"

    cadena = str(valor).strip()
    cadena_upper = cadena.upper()

    if not cadena or "SIN TERMINO" in cadena_upper or "SIN TÉRMINO" in cadena_upper:
        return None, "SIN TÉRMINO"

    f_dt = parsear_fecha(cadena)
    if f_dt is not None:
        return f_dt, cadena

    return None, cadena


def importar_legajos_csv(archivo_o_contenido, usuario=None, delimitador=None):
    """
    Importa legajos y cargos docentes desde un archivo CSV o contenido string/IO.
    Garantiza la sincronización dual de 'DESDE'/'HASTA' y ejecución atómica.
    Retorna un diccionario con las estadísticas del proceso.
    """
    if isinstance(archivo_o_contenido, str):
        if os.path.exists(archivo_o_contenido):
            with open(archivo_o_contenido, mode="r", encoding="utf-8-sig") as f:
                contenido = f.read()
        else:
            contenido = archivo_o_contenido
        f_in = io.StringIO(contenido)
    elif hasattr(archivo_o_contenido, "read"):
        data = archivo_o_contenido.read()
        if isinstance(data, bytes):
            data = data.decode("utf-8-sig", errors="replace")
        f_in = io.StringIO(data)
    else:
        raise ValueError("El archivo o contenido proporcionado no es válido.")

    # Detección automática del delimitador si no se especificó
    if delimitador is None:
        sample = f_in.read(2048)
        f_in.seek(0)
        delimitador = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(f_in, delimiter=delimitador)

    docentes_creados = 0
    cargos_creados = 0
    filas_procesadas = 0

    with transaction.atomic():
        for row in reader:
            filas_procesadas += 1
            clean_row = {
                (k or "").strip().upper(): (v or "").strip()
                for k, v in row.items()
            }

            dni = (
                clean_row.get("DNI")
                or clean_row.get("DOCUMENTO")
                or clean_row.get("LEGAJO")
            )
            if not dni:
                continue

            apellido = clean_row.get("APELLIDO", "Sin Apellido")
            nombre = clean_row.get("NOMBRE", "Sin Nombre")
            sexo = clean_row.get("SEXO", "M").upper()
            if sexo not in ["M", "F", "X"]:
                sexo = "M"

            docente, created = Docente.objects.get_or_create(
                dni=dni,
                defaults={
                    "apellido": apellido,
                    "nombre": nombre,
                    "sexo": sexo,
                    "creado_por": usuario,
                },
            )
            if created:
                docentes_creados += 1
            else:
                if apellido and apellido != "Sin Apellido":
                    docente.apellido = apellido
                if nombre and nombre != "Sin Nombre":
                    docente.nombre = nombre
                if usuario:
                    docente.modificado_por = usuario
                docente.save()

            # Sincronización dual de fechas DESDE y HASTA
            desde_val = (
                clean_row.get("DESDE")
                or clean_row.get("FECHA_DESDE")
                or clean_row.get("FECHA_ALTA")
            )
            hasta_val = (
                clean_row.get("HASTA")
                or clean_row.get("FECHA_HASTA")
                or clean_row.get("FECHA_BAJA")
            )

            fecha_alta, desde_texto = parsear_fecha_desde(desde_val)
            fecha_baja, hasta_texto = parsear_fecha_hasta(hasta_val)

            situacion = (
                clean_row.get("SITUACION_REVISTA")
                or clean_row.get("SITUACION")
                or "INTERINO"
            ).upper()
            if situacion not in [
                "TITULAR",
                "INTERINO",
                "SUPLENTE",
                "TIT",
                "INT",
                "SUP",
            ]:
                situacion = "INTERINO"

            nombre_materia = (
                clean_row.get("MATERIA")
                or clean_row.get("ESPACIO_CURRICULAR")
                or clean_row.get("ASIGNATURA")
            )
            materia = None
            if nombre_materia:
                codigo_espacio = (
                    clean_row.get("CODIGO_ESPACIO")
                    or clean_row.get("CODIGO_MATERIA")
                    or f"MAT_{docente.dni}_{filas_procesadas}"
                )
                materia, _ = EspacioCurricular.objects.get_or_create(
                    codigo=codigo_espacio,
                    defaults={
                        "nombre": nombre_materia,
                        "carrera": clean_row.get(
                            "CARRERA", "Tecnicatura Superior"
                        ),
                        "anio": 1,
                    },
                )

            def _int(val_str):
                return int(val_str) if val_str and val_str.isdigit() else 0

            horas_lunes = _int(clean_row.get("HORAS_LUNES")) or _int(
                clean_row.get("LUNES")
            )
            horas_martes = _int(clean_row.get("HORAS_MARTES")) or _int(
                clean_row.get("MARTES")
            )
            horas_miercoles = _int(clean_row.get("HORAS_MIERCOLES")) or _int(
                clean_row.get("MIERCOLES")
            )
            horas_jueves = _int(clean_row.get("HORAS_JUEVES")) or _int(
                clean_row.get("JUEVES")
            )
            horas_viernes = _int(clean_row.get("HORAS_VIERNES")) or _int(
                clean_row.get("VIERNES")
            )

            CargoDocente.objects.create(
                docente=docente,
                materia=materia,
                situacion_revista=situacion,
                codigo_cargo=clean_row.get("CODIGO_CARGO", ""),
                resolucion=clean_row.get("RESOLUCION", ""),
                fecha_alta=fecha_alta,
                desde_texto=desde_texto,
                fecha_baja=fecha_baja,
                hasta_texto=hasta_texto,
                horas_lunes=horas_lunes,
                horas_martes=horas_martes,
                horas_miercoles=horas_miercoles,
                horas_jueves=horas_jueves,
                horas_viernes=horas_viernes,
                creado_por=usuario,
            )
            cargos_creados += 1

    return {
        "docentes_creados": docentes_creados,
        "cargos_creados": cargos_creados,
        "filas_procesadas": filas_procesadas,
    }


# Alias para compatibilidad de importación
importar_csv = importar_legajos_csv


class Command(BaseCommand):
    help = (
        "Importa legajos docentes y cargos desde un archivo CSV aplicando "
        "la sincronización dual de fechas 'DESDE' y 'HASTA' (Ticket 3.8)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Ruta al archivo CSV con los legajos y cargos a importar.",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        self.stdout.write(f"Iniciando importación desde '{csv_file}'...")
        try:
            stats = importar_legajos_csv(csv_file)
            msg = (
                f"Importación exitosa: {stats['docentes_creados']} docentes creados, "
                f"{stats['cargos_creados']} cargos asignados a partir de "
                f"{stats['filas_procesadas']} filas procesadas."
            )
            self.stdout.write(self.style.SUCCESS(msg))
        except Exception as e:
            raise CommandError(f"Error durante la importación CSV: {e}")
