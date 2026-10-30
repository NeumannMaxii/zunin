"""
Servicio de importación masiva de Docentes y Cargos desde archivos CSV.
Ticket 3: Importador CSV y Seeder.
"""

import csv
import io
import re
import unicodedata
from django.db import transaction
from apps.personal.models import CargoDocente, Docente, EspacioCurricular

MAPA_SITUACION_REVISTA = {
    "TITULAR": "TIT",
    "INTERINO": "INT",
    "SUPLENTE": "SUP",
    "TIT": "TIT",
    "INT": "INT",
    "SUP": "SUP",
}


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


def importar_docentes_cargos_csv(
    archivo_o_ruta, usuario=None, encoding="utf-8-sig", delimiter=";"
):
    """
    Importa Docentes y CargoDocente desde un archivo o stream CSV.

    Especificaciones:
    - Encoding: utf-8-sig.
    - Delimitador: ';'
    - Mapeo de revista: TITULAR -> TIT, INTERINO -> INT, SUPLENTE -> SUP.
    - Omite filas inválidas (sin DNI, sin nombre o con revista inválida).
    - Idempotente: ejecutar múltiples veces no duplica Docentes ni CargoDocente.
    - Solo crea Docentes y CargoDocente (no crea asistencias).
    """
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

    if isinstance(archivo_o_ruta, (str, bytes)):
        f = open(archivo_o_ruta, mode="r", encoding=encoding)
        debe_cerrar = True
    elif isinstance(archivo_o_ruta, io.StringIO):
        f = archivo_o_ruta
        debe_cerrar = False
    elif isinstance(archivo_o_ruta, io.BytesIO):
        f = io.StringIO(archivo_o_ruta.read().decode(encoding))
        debe_cerrar = False
    else:
        # File-like object
        f = archivo_o_ruta
        debe_cerrar = False

    try:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return resumen

        headers_norm = [_normalizar_header(h) for h in raw_headers]

        # Mapeo de columnas a índices
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
                "codigo_materia",
                "codigo_espacio",
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
            elif h in ["desde_texto", "desde", "fecha_desde"]:
                idx_map.setdefault("desde_texto", idx)
            elif h in ["hasta_texto", "hasta", "fecha_hasta"]:
                idx_map.setdefault("hasta_texto", idx)
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

                # 1. Validar DNI
                dni = _normalizar_dni(get_val("dni"))
                if not dni:
                    resumen["filas_omitidas"] += 1
                    resumen["errores"].append(
                        f"Fila {num_fila}: DNI ausente o inválido."
                    )
                    continue

                # 2. Validar Apellido y Nombre
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

                # 3. Validar Situación de Revista
                revista_raw = get_val("situacion_revista").upper().strip()
                if not revista_raw or revista_raw not in MAPA_SITUACION_REVISTA:
                    resumen["filas_omitidas"] += 1
                    resumen["errores"].append(
                        f"Fila {num_fila}: Situación de revista inválida "
                        f"('{revista_raw}'). Se omite fila."
                    )
                    continue

                revista_norm = MAPA_SITUACION_REVISTA[revista_raw]

                # 4. Datos de Docente (update_or_create para idempotencia)
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

                # 5. Espacio Curricular (opcional)
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
                            re.sub(r"[^A-Z0-9]", "", materia_nombre.upper())[
                                :10
                            ]
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

                # 6. Mapear Horas diarias (Lunes a Viernes)
                hl, dl = _parse_horas_dia(get_val("horas_lunes"))
                hma, dma = _parse_horas_dia(get_val("horas_martes"))
                hmi, dmi = _parse_horas_dia(get_val("horas_miercoles"))
                hj, dj = _parse_horas_dia(get_val("horas_jueves"))
                hv, dv = _parse_horas_dia(get_val("horas_viernes"))

                # 7. CargoDocente (Idempotencia estricta)
                codigo_cargo = get_val("codigo_cargo")
                resolucion = get_val("resolucion")
                desde_texto = (
                    get_val("desde_texto", "SIN INICIO") or "SIN INICIO"
                )
                hasta_texto = (
                    get_val("hasta_texto", "SIN TERMINO") or "SIN TERMINO"
                )

                # Si no se suministra código de cargo, generar clave unívoca
                # por docente y materia
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
                    "desde_texto": desde_texto,
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

    finally:
        if debe_cerrar:
            f.close()

    return resumen
