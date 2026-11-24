"""
Servicios de negocio para apps.asistencia.
Implementa Ticket 3.8: Directiva de Transaccionalidad Atómica en Carga Masiva,
Justificaciones por Lote (Ticket 7), y Consulta Avanzada (Ticket 12.6).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from apps.asistencia.models import RegistroAsistencia
from apps.core.audit import audit_save
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia


def rectificar_planillas_por_fechas(fechas, usuario=None):
    """
    Regla de Integridad Histórica (RN-03):
    Si alguno de los meses de las fechas indicadas ya cuenta con renglones
    en RenglonPlanillaMensual, marca los renglones previos del período como
    desactualizados (preservando historial y números de instrumento) y regenera
    los renglones vigentes del mes.

    Retorna una lista ordenada de tuplas (mes, anio) rectificadas.
    """
    from apps.licencias.services import generar_planilla_mes

    periodos = sorted(
        {(f.month, f.year) for f in fechas if f is not None},
        key=lambda item: (item[1], item[0]),
    )
    if not periodos:
        return []

    def _rectificar():
        periodos_rectificados = []
        for mes, anio in periodos:
            planillas_mes = RenglonPlanillaMensual.objects.filter(
                mes=mes, anio=anio
            )
            if planillas_mes.exists():
                planillas_mes.filter(desactualizada=False).update(
                    desactualizada=True
                )
                generar_planilla_mes(mes=mes, anio=anio, usuario=usuario)
                periodos_rectificados.append((mes, anio))
        return periodos_rectificados

    if connection.in_atomic_block:
        return _rectificar()
    with transaction.atomic():
        return _rectificar()


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

            if registros_justificados:
                rectificar_planillas_por_fechas(
                    [reg.fecha for reg in registros_justificados],
                    usuario=usuario,
                )

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
        for token in term.split():
            queryset = queryset.filter(
                Q(docente__dni__icontains=token)
                | Q(docente__apellido__icontains=token)
                | Q(docente__nombre__icontains=token)
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


def generar_excel_parte_diario(
    fecha, grilla, feriado=None, turno_filtro=None, carrera_filtro=None
):
    """
    Genera un libro openpyxl con el Parte Diario de Asistencia de Bedelía
    (Ticket 19.5).
    Formato planilla institucional con membrete, metadatos, grilla con colores
    pasteles sobrios según estado/marca, y bloque de totales.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Parte Diario {fecha.strftime('%d-%m-%Y')}"
    ws.views.sheetView[0].showGridLines = True

    color_banner_fill = "0F766E"  # Emerald oscuro institucional
    color_border = "CBD5E1"       # Slate 300

    thin_border = Border(
        left=Side(style="thin", color=color_border),
        right=Side(style="thin", color=color_border),
        top=Side(style="thin", color=color_border),
        bottom=Side(style="thin", color=color_border),
    )

    # 1. Membrete Institucional
    ws.merge_cells("A1:M1")
    cell_title = ws["A1"]
    cell_title.value = (
        "IESETyFP - INSTITUTO DE EDUCACIÓN SUPERIOR DE EDUCACIÓN "
        "TÉCNICA Y FORMACIÓN PROFESIONAL"
    )
    cell_title.font = Font(
        name="Calibri", size=13, bold=True, color="FFFFFF"
    )
    cell_title.fill = PatternFill(
        start_color=color_banner_fill,
        end_color=color_banner_fill,
        fill_type="solid",
    )
    cell_title.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.merge_cells("A2:M2")
    cell_sub = ws["A2"]
    cell_sub.value = (
        "PARTE DIARIO DE ASISTENCIA Y NOVEDADES DOCENTES - BEDELÍA"
    )
    cell_sub.font = Font(name="Calibri", size=10, bold=True, color="334155")
    cell_sub.fill = PatternFill(
        start_color="F8FAFC", end_color="F8FAFC", fill_type="solid"
    )
    cell_sub.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # 2. Metadatos
    dias_semana = [
        "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
    ]
    dia_txt = dias_semana[fecha.weekday()]
    turnos_dict = {"MANANA": "Mañana", "TARDE": "Tarde", "NOCHE": "Noche"}
    turno_txt = turnos_dict.get(turno_filtro, "Todos los turnos")
    carrera_txt = str(carrera_filtro) if carrera_filtro else "Todas las carreras"
    feriado_txt = (
        f" | [DÍA NO LABORABLE / FERIADO: {feriado.descripcion}]"
        if feriado
        else ""
    )

    ws.merge_cells("A3:M3")
    cell_meta = ws["A3"]
    cell_meta.value = (
        f"Fecha: {fecha.strftime('%d/%m/%Y')} ({dia_txt}) | "
        f"Turno: {turno_txt} | Carrera: {carrera_txt}{feriado_txt}"
    )
    cell_meta.font = Font(name="Calibri", size=9, bold=True, color="475569")
    cell_meta.fill = PatternFill(
        start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"
    )
    cell_meta.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 18

    # Fila 4 vacía
    ws.row_dimensions[4].height = 8

    # 3. Encabezados de Columna
    headers = [
        ("N°", 5, "center"),
        ("Turno", 11, "center"),
        ("Carrera", 28, "left"),
        ("Año / Com.", 12, "center"),
        ("Espacio Curricular / Materia", 32, "left"),
        ("Docente (Apellido y Nombre)", 30, "left"),
        ("DNI", 12, "center"),
        ("Revista", 10, "center"),
        ("Hs Cát.", 9, "center"),
        ("Estado", 13, "center"),
        ("Marca", 9, "center"),
        ("Licencia / Novedad", 28, "left"),
        ("Observaciones", 24, "left"),
    ]

    header_font = Font(name="Calibri", size=9.5, bold=True, color="0F172A")
    header_fill = PatternFill(
        start_color="E2E8F0", end_color="E2E8F0", fill_type="solid"
    )

    for col_idx, (h_title, _, h_align) in enumerate(headers, start=1):
        c = ws.cell(row=5, column=col_idx, value=h_title)
        c.font = header_font
        c.fill = header_fill
        c.border = thin_border
        c.alignment = Alignment(
            horizontal=h_align, vertical="center", wrap_text=True
        )

    ws.row_dimensions[5].height = 24

    fill_pr = PatternFill(
        start_color="F0FDF4", end_color="F0FDF4", fill_type="solid"
    )
    fill_i = PatternFill(
        start_color="FEF2F2", end_color="FEF2F2", fill_type="solid"
    )
    fill_lic = PatternFill(
        start_color="EFF6FF", end_color="EFF6FF", fill_type="solid"
    )
    fill_p = PatternFill(
        start_color="FEFCE8", end_color="FEFCE8", fill_type="solid"
    )
    fill_white = PatternFill(
        start_color="FFFFFF", end_color="FFFFFF", fill_type="solid"
    )

    fila_num = 6
    tot_pr = 0
    tot_i = 0
    tot_lic = 0
    tot_p = 0

    for idx, item in enumerate(grilla, start=1):
        cargo = item["cargo"]
        doc = item["docente"]
        reg = item.get("registro")
        lic_activa = item.get("licencia_activa")
        materia = cargo.materia
        carrera = (
            materia.carrera
            if materia and materia.carrera
            else cargo.carrera_ref
        )

        if reg:
            estado_txt = reg.get_estado_display()
            marca_txt = reg.marca_diaria or (
                "PR" if reg.estado == "PRESENTE" else ""
            )
            lic_obj = reg.tipo_licencia
            obs_txt = reg.observaciones or ""
        elif lic_activa:
            estado_txt = "Licencia"
            marca_txt = "LIC"
            lic_obj = lic_activa.tipo_licencia
            obs_txt = f"Licencia Activa #{lic_activa.pk}"
        else:
            estado_txt = "Presente"
            marca_txt = "PR"
            lic_obj = None
            obs_txt = ""

        if marca_txt == "PR":
            tot_pr += 1
            row_fill = fill_pr
        elif marca_txt in ("I", "INA"):
            tot_i += 1
            row_fill = fill_i
        elif marca_txt in ("LIC", "LIC.", "LT"):
            tot_lic += 1
            row_fill = fill_lic
        elif marca_txt in ("P", "PERM"):
            tot_p += 1
            row_fill = fill_p
        else:
            tot_pr += 1
            row_fill = fill_white

        carrera_nombre = carrera.nombre if carrera else "-"
        anio_com = (
            f"{materia.anio}° ({materia.get_comision_display()})"
            if materia
            else "-"
        )
        materia_nombre = (
            materia.nombre
            if materia
            else (
                cargo.cargo_catalogo.descripcion
                if cargo.cargo_catalogo
                else "Cargo Docente"
            )
        )
        horas = item.get("horas_dia", 0)

        lic_desc = ""
        if lic_obj:
            art_str = f"Art. {lic_obj.articulo} - " if lic_obj.articulo else ""
            lic_desc = f"{art_str}{lic_obj.codigo} ({lic_obj.descripcion})"
        elif lic_activa and lic_activa.tipo_licencia:
            tl = lic_activa.tipo_licencia
            art_str = f"Art. {tl.articulo} - " if tl.articulo else ""
            lic_desc = f"{art_str}{tl.codigo} ({tl.descripcion})"

        row_data = [
            (idx, "center"),
            (cargo.get_turno_display() or "-", "center"),
            (carrera_nombre, "left"),
            (anio_com, "center"),
            (materia_nombre, "left"),
            (f"{doc.apellido}, {doc.nombre}", "left"),
            (doc.dni, "center"),
            (cargo.get_situacion_revista_display(), "center"),
            (horas, "center"),
            (estado_txt, "center"),
            (marca_txt, "center"),
            (lic_desc, "left"),
            (obs_txt, "left"),
        ]

        for col_idx, (val, align) in enumerate(row_data, start=1):
            cell = ws.cell(row=fila_num, column=col_idx, value=val)
            cell.font = Font(
                name="Calibri", size=9, bold=(col_idx in (5, 6, 11))
            )
            cell.fill = row_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal=align, vertical="center")

        ws.row_dimensions[fila_num].height = 20
        fila_num += 1

    # Fila vacía
    fila_num += 1

    # 4. Bloque de Totales y Resumen Estadístico
    ws.merge_cells(f"B{fila_num}:D{fila_num}")
    ws[f"B{fila_num}"] = "RESUMEN DEL PARTE DIARIO"
    ws[f"B{fila_num}"].font = Font(
        name="Calibri", size=10, bold=True, color="0F172A"
    )
    ws[f"B{fila_num}"].fill = PatternFill(
        start_color="E2E8F0", end_color="E2E8F0", fill_type="solid"
    )
    ws[f"B{fila_num}"].alignment = Alignment(
        horizontal="center", vertical="center"
    )

    totales = [
        ("Total Clases / Cargos:", len(grilla), "FFFFFF"),
        ("Presentes (PR):", tot_pr, "DCFCE7"),
        ("Inasistencias (I):", tot_i, "FEE2E2"),
        ("Licencias (LIC / LT):", tot_lic, "E0E7FF"),
        ("Permisos (P):", tot_p, "FEF3C7"),
    ]

    fila_tot = fila_num + 1
    for label, val, bg_color in totales:
        ws.cell(row=fila_tot, column=2, value=label).font = Font(
            name="Calibri", size=9, bold=True
        )
        ws.cell(row=fila_tot, column=2).alignment = Alignment(
            horizontal="left", vertical="center"
        )
        ws.cell(row=fila_tot, column=2).border = thin_border

        c_val = ws.cell(row=fila_tot, column=3, value=val)
        c_val.font = Font(name="Calibri", size=9.5, bold=True)
        c_val.fill = PatternFill(
            start_color=bg_color, end_color=bg_color, fill_type="solid"
        )
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        c_val.border = thin_border
        fila_tot += 1

    # 5. Sección de Firmas de Bedelía
    firma_row = max(fila_tot + 2, fila_num + 4)
    ws.merge_cells(f"F{firma_row}:H{firma_row}")
    ws[f"F{firma_row}"] = "____________________________________"
    ws[f"F{firma_row}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"F{firma_row+1}:H{firma_row+1}")
    ws[f"F{firma_row+1}"] = "Firma y Aclaración Bedel de Turno"
    ws[f"F{firma_row+1}"].font = Font(name="Calibri", size=8.5, italic=True)
    ws[f"F{firma_row+1}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"J{firma_row}:L{firma_row}")
    ws[f"J{firma_row}"] = "____________________________________"
    ws[f"J{firma_row}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"J{firma_row+1}:L{firma_row+1}")
    ws[f"J{firma_row+1}"] = "Sello y Recepción Secretaría / Rectoría"
    ws[f"J{firma_row+1}"].font = Font(name="Calibri", size=8.5, italic=True)
    ws[f"J{firma_row+1}"].alignment = Alignment(horizontal="center")

    # Ajuste de ancho de columnas
    for col_idx, (_, col_w, _) in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col_w

    return wb
