"""
Management command y utilidades de importación CSV de legajos docentes y cargos.
Implementa Ticket 3 (Importador CSV idempotente) y Ticket 3.8 (Sincronización Dual).
"""

import csv
import datetime
import io
import os
import re
import unicodedata
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

MAPA_SITUACION_REVISTA = {
    "TITULAR": "TIT",
    "INTERINO": "INT",
    "SUPLENTE": "SUP",
    "TIT": "TIT",
    "INT": "INT",
    "SUP": "SUP",
}


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


def _normalizar_header(header):
    """Normaliza encabezados de columnas eliminando acentos, espacios y símbolos."""
    if not header:
        return ""
    limpio = unicodedata.normalize("NFKD", str(header).strip())
    limpio = limpio.encode("ASCII", "ignore").decode("utf-8").lower()
    limpio = re.sub(r"[\s\-_]+", "_", limpio)
    return limpio


def _parse_horas_dia(raw_val):
    """
    Parsea las horas cátedra de un día de la semana.
    Retorna tupla: (horas_int, texto_dia).
    """
    if raw_val is None:
        return 0, ""
    val_str = str(raw_val).strip()
    if not val_str or val_str in ["-", "0"]:
        return 0, ""
    if "X" in val_str.upper():
        return 1, "X"
    match = re.search(r"\d+", val_str)
    if match:
        horas = int(match.group())
        return horas, val_str
    return 0, val_str


def _normalizar_dni(raw_dni):
    """Limpia puntos, guiones y espacios del DNI."""
    if raw_dni is None:
        return ""
    return re.sub(r"[^\w]", "", str(raw_dni)).strip()


def importar_legajos_csv(
    archivo_o_contenido,
    usuario=None,
    delimitador=None,
    encoding="utf-8-sig",
    delimiter=None,
):
    """
    Importa legajos y cargos docentes desde un archivo CSV o stream.
    Garantiza sincronización dual, idempotencia y ejecución atómica.
    """
    sep = delimiter or delimitador

    if isinstance(archivo_o_contenido, str):
        if os.path.exists(archivo_o_contenido):
            with open(archivo_o_contenido, mode="r", encoding=encoding) as f:
                contenido = f.read()
        else:
            contenido = archivo_o_contenido
        f_in = io.StringIO(contenido)
    elif hasattr(archivo_o_contenido, "read"):
        data = archivo_o_contenido.read()
        if isinstance(data, bytes):
            data = data.decode(encoding, errors="replace")
        f_in = io.StringIO(data)
    else:
        raise ValueError("El archivo o contenido proporcionado no es válido.")

    if sep is None:
        sample = f_in.read(2048)
        f_in.seek(0)
        sep = ";" if sample.count(";") >= sample.count(",") else ","

    resumen = {
        "total_filas": 0,
        "filas_procesadas": 0,
        "filas_omitidas": 0,
        "docentes_creados": 0,
        "docentes_actualizados": 0,
        "cargos_creados": 0,
        "cargos_actualizados": 0,
        "errores": [],
    }

    reader = csv.reader(f_in, delimiter=sep)
    try:
        raw_headers = next(reader)
    except StopIteration:
        return resumen

    headers_norm = [_normalizar_header(h) for h in raw_headers]
    idx_map = {}
    for idx, h in enumerate(headers_norm):
        if h in ["dni", "documento", "nro_documento", "legajo", "num_doc"]:
            idx_map.setdefault("dni", idx)
        elif h in ["apellido", "apellidos"]:
            idx_map.setdefault("apellido", idx)
        elif h in ["nombre", "nombres"]:
            idx_map.setdefault("nombre", idx)
        elif h in [
            "docente",
            "apellido_y_nombre",
            "nombre_y_apellido",
            "agente",
            "personal",
        ]:
            idx_map.setdefault("docente_completo", idx)
        elif h in [
            "situacion_revista",
            "situacion_de_revista",
            "situacion",
            "revista",
            "sit_revista",
        ]:
            idx_map.setdefault("situacion_revista", idx)
        elif h in [
            "materia",
            "espacio_curricular",
            "asignatura",
            "espacio",
            "nombre_materia",
        ]:
            idx_map.setdefault("materia", idx)
        elif h in [
            "codigo_espacio",
            "codigo_materia",
            "codigo_asignatura",
            "cod_materia",
        ]:
            idx_map.setdefault("codigo_materia", idx)
        elif h in ["carrera", "tecnicatura"]:
            idx_map.setdefault("carrera", idx)
        elif h in ["anio", "ano", "curso"]:
            idx_map.setdefault("anio", idx)
        elif h in ["horas_lunes", "lunes", "hs_lunes", "dia_lunes", "lu"]:
            idx_map.setdefault("horas_lunes", idx)
        elif h in ["horas_martes", "martes", "hs_martes", "dia_martes", "ma"]:
            idx_map.setdefault("horas_martes", idx)
        elif h in [
            "horas_miercoles",
            "miercoles",
            "hs_miercoles",
            "dia_miercoles",
            "mi",
        ]:
            idx_map.setdefault("horas_miercoles", idx)
        elif h in ["horas_jueves", "jueves", "hs_jueves", "dia_jueves", "ju"]:
            idx_map.setdefault("horas_jueves", idx)
        elif h in ["horas_viernes", "viernes", "hs_viernes", "dia_viernes", "vi"]:
            idx_map.setdefault("horas_viernes", idx)
        elif h in ["codigo_cargo", "cod_cargo", "cargo"]:
            idx_map.setdefault("codigo_cargo", idx)
        elif h in ["resolucion", "norma", "instrumento"]:
            idx_map.setdefault("resolucion", idx)
        elif h in ["desde", "desde_texto", "fecha_desde", "fecha_alta"]:
            idx_map.setdefault("desde", idx)
        elif h in ["hasta", "hasta_texto", "fecha_hasta", "fecha_baja"]:
            idx_map.setdefault("hasta", idx)
        elif h in ["sexo", "genero"]:
            idx_map.setdefault("sexo", idx)
        elif h in ["contacto", "email", "correo", "telefono", "celular"]:
            idx_map.setdefault("contacto", idx)

    with transaction.atomic():
        for num_fila, row in enumerate(reader, start=2):
            if not row or not any(field.strip() for field in row):
                continue

            resumen["total_filas"] += 1

            def get_val(key, default=""):
                if key in idx_map and idx_map[key] < len(row):
                    return row[idx_map[key]].strip()
                return default

            dni = _normalizar_dni(get_val("dni"))
            if not dni:
                resumen["filas_omitidas"] += 1
                resumen["errores"].append(f"Fila {num_fila}: DNI ausente o inválido.")
                continue

            apellido = get_val("apellido")
            nombre = get_val("nombre")
            if not apellido or not nombre:
                docente_comp = get_val("docente_completo")
                if docente_comp:
                    if "," in docente_comp:
                        partes = docente_comp.split(",", 1)
                        apellido = partes[0].strip()
                        nombre = partes[1].strip()
                    else:
                        partes = docente_comp.rsplit(" ", 1)
                        apellido = partes[0].strip()
                        nombre = partes[1].strip() if len(partes) > 1 else ""

            if not apellido or not nombre:
                resumen["filas_omitidas"] += 1
                resumen["errores"].append(
                    f"Fila {num_fila}: Apellido o Nombre ausente."
                )
                continue

            # Situación de revista
            revista_raw = get_val("situacion_revista").upper().strip()
            if "situacion_revista" in idx_map:
                if not revista_raw or revista_raw not in MAPA_SITUACION_REVISTA:
                    resumen["filas_omitidas"] += 1
                    resumen["errores"].append(
                        f"Fila {num_fila}: Situación de revista inválida "
                        f"('{revista_raw}'). Se omite fila."
                    )
                    continue
                revista_norm = MAPA_SITUACION_REVISTA[revista_raw]
            else:
                revista_norm = "INT"

            sexo_raw = get_val("sexo", "M").upper()
            sexo = sexo_raw if sexo_raw in ["M", "F", "X"] else "M"
            contacto = get_val("contacto")

            docente_defaults = {
                "apellido": apellido,
                "nombre": nombre,
                "sexo": sexo,
                "activo": True,
            }
            if contacto:
                docente_defaults["contacto"] = contacto
            if usuario:
                docente_defaults["modificado_por"] = usuario

            docente, d_created = Docente.objects.update_or_create(
                dni=dni,
                defaults=docente_defaults,
            )
            if d_created:
                resumen["docentes_creados"] += 1
                if usuario:
                    docente.creado_por = usuario
                    docente.save(update_fields=["creado_por"])
            else:
                resumen["docentes_actualizados"] += 1

            # Espacio curricular
            materia_nombre = get_val("materia")
            codigo_materia = get_val("codigo_materia")
            carrera_nombre = (
                get_val("carrera")
                or "Tecnicatura Superior en Desarrollo de Software"
            )
            anio_str = get_val("anio", "1")
            try:
                anio_val = int(re.search(r"\d+", anio_str).group())
            except (AttributeError, ValueError):
                anio_val = 1

            espacio = None
            if codigo_materia:
                cod_limpio = codigo_materia.upper().strip()
                espacio, _ = EspacioCurricular.objects.get_or_create(
                    codigo=cod_limpio,
                    defaults={
                        "nombre": materia_nombre or cod_limpio,
                        "carrera": carrera_nombre,
                        "anio": anio_val,
                    },
                )
            elif materia_nombre:
                espacio = EspacioCurricular.objects.filter(
                    nombre__iexact=materia_nombre
                ).first()
                if not espacio:
                    slug_base = (
                        re.sub(r"[^A-Z0-9]", "", materia_nombre.upper())[:10]
                        or "ESP"
                    )
                    codigo_gen = f"{slug_base}-01"
                    idx_gen = 1
                    while EspacioCurricular.objects.filter(
                        codigo=codigo_gen
                    ).exists():
                        idx_gen += 1
                        codigo_gen = f"{slug_base}-{idx_gen:02d}"
                    espacio = EspacioCurricular.objects.create(
                        codigo=codigo_gen,
                        nombre=materia_nombre,
                        carrera=carrera_nombre,
                        anio=anio_val,
                    )

            # Horas semanales
            hl, dl = _parse_horas_dia(get_val("horas_lunes"))
            hma, dma = _parse_horas_dia(get_val("horas_martes"))
            hmi, dmi = _parse_horas_dia(get_val("horas_miercoles"))
            hj, dj = _parse_horas_dia(get_val("horas_jueves"))
            hv, dv = _parse_horas_dia(get_val("horas_viernes"))

            # Fechas con sincronización dual (Ticket 3.8)
            desde_val = get_val("desde")
            hasta_val = get_val("hasta")
            fecha_alta, desde_texto = parsear_fecha_desde(desde_val)
            fecha_baja, hasta_texto = parsear_fecha_hasta(hasta_val)

            codigo_cargo = get_val("codigo_cargo")
            resolucion = get_val("resolucion")

            if not codigo_cargo:
                cod_m = espacio.codigo if espacio else "GENERAL"
                codigo_cargo = f"CARGO-{dni}-{cod_m}"

            cargo_defaults = {
                "materia": espacio,
                "situacion_revista": revista_norm,
                "horas_lunes": hl,
                "horas_martes": hma,
                "horas_miercoles": hmi,
                "horas_jueves": hj,
                "horas_viernes": hv,
                "dia_lunes": dl,
                "dia_martes": dma,
                "dia_miercoles": dmi,
                "dia_jueves": dj,
                "dia_viernes": dv,
                "fecha_alta": fecha_alta,
                "desde_texto": desde_texto,
                "fecha_baja": fecha_baja,
                "hasta_texto": hasta_texto,
                "activo": True,
            }
            if resolucion:
                cargo_defaults["resolucion"] = resolucion
            if usuario:
                cargo_defaults["modificado_por"] = usuario

            cargo, c_created = CargoDocente.objects.update_or_create(
                docente=docente,
                codigo_cargo=codigo_cargo,
                defaults=cargo_defaults,
            )
            if c_created:
                resumen["cargos_creados"] += 1
                if usuario:
                    cargo.creado_por = usuario
                    cargo.save(update_fields=["creado_por"])
            else:
                resumen["cargos_actualizados"] += 1

            resumen["filas_procesadas"] += 1

    return resumen


importar_csv = importar_legajos_csv
importar_docentes_cargos_csv = importar_legajos_csv


class Command(BaseCommand):
    help = (
        "Importa Docentes y Cargos desde un archivo CSV con encoding "
        "'utf-8-sig' y delimitador ';' de forma idempotente (Ticket 3 y 3.8)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "archivo_csv",
            nargs="?",
            default=None,
            type=str,
            help="Ruta al archivo CSV a importar.",
        )
        parser.add_argument(
            "--encoding",
            type=str,
            default="utf-8-sig",
            help="Codificación del archivo (predeterminado: utf-8-sig).",
        )
        parser.add_argument(
            "--delimiter",
            type=str,
            default=";",
            help="Delimitador de campos (predeterminado: ';').",
        )

    def handle(self, *args, **options):
        archivo_csv = options.get("archivo_csv") or options.get("csv_file")
        if not archivo_csv:
            raise CommandError("Debe especificar la ruta al archivo CSV.")

        if not os.path.exists(archivo_csv):
            raise CommandError(
                f"El archivo '{archivo_csv}' no existe o no fue encontrado."
            )

        encoding = options.get("encoding", "utf-8-sig")
        delimiter = options.get("delimiter", ";")

        self.stdout.write(
            self.style.NOTICE(f"Iniciando importación desde '{archivo_csv}'...")
        )

        try:
            resumen = importar_legajos_csv(
                archivo_csv,
                encoding=encoding,
                delimiter=delimiter,
            )
        except FileNotFoundError:
            raise CommandError(
                f"El archivo '{archivo_csv}' no existe o no fue encontrado."
            )
        except Exception as e:
            raise CommandError(f"Error durante la importación: {e}")

        filas_msg = (
            f"  - Filas procesadas: {resumen['filas_procesadas']} "
            f"de {resumen['total_filas']}\n"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Importación finalizada con éxito:\n"
                f"{filas_msg}"
                f"  - Filas omitidas: {resumen['filas_omitidas']}\n"
                f"  - Docentes creados: {resumen['docentes_creados']}\n"
                f"  - Docentes actualizados: {resumen['docentes_actualizados']}\n"
                f"  - Cargos creados: {resumen['cargos_creados']}\n"
                f"  - Cargos actualizados: {resumen['cargos_actualizados']}"
            )
        )
