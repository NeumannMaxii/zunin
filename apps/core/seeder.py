"""
Módulo seeder para población de datos de demostración y testing (Ticket 3).
Crea catálogos institucionales, docentes, cargos y un mes completo de
registros de asistencia diarios (Octubre 2026) con marcas 'P', 'I' y 'LIC'.
"""

import datetime
from django.db import transaction
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.licencias.models import TipoLicencia
from apps.licencias.services import generar_planilla_mes
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    TipoAutorizacion,
)


def poblar_datos_demo(usuario=None, reset=False, generar_planilla=False):
    """
    Puebla la base de datos con información base y un mes completo de prueba
    (Octubre 2026) de forma idempotente.
    """
    resumen = {
        "carreras": 0,
        "cargos_catalogo": 0,
        "tipos_autorizacion": 0,
        "tipos_licencia": 0,
        "dias_no_laborables": 0,
        "espacios": 0,
        "docentes": 0,
        "cargos_docente": 0,
        "asistencias_creadas": 0,
        "asistencias_actualizadas": 0,
        "renglones_planilla": 0,
    }

    with transaction.atomic():
        if reset:
            RegistroAsistencia.objects.filter(
                fecha__year=2026, fecha__month=10
            ).delete()

        # -------------------------------------------------------------
        # 1. Catálogos Base
        # -------------------------------------------------------------
        carreras_data = [
            (
                "TSDS",
                "Tecnicatura Superior en Desarrollo de Software",
            ),
            (
                "TSIA",
                "Tecnicatura Superior en Inteligencia Artificial",
            ),
            (
                "TSSI",
                "Tecnicatura Superior en Redes y Seguridad Informática",
            ),
        ]
        for cod, nom in carreras_data:
            _, created = Carrera.objects.get_or_create(
                codigo=cod,
                defaults={"nombre": nom, "activo": True},
            )
            if created:
                resumen["carreras"] += 1

        cargos_cat_data = [
            ("PROF-TIT", "Profesor Titular"),
            ("PROF-INT", "Profesor Interino"),
            ("AUX-DOC", "Auxiliar Docente de Bedelía"),
        ]
        for cod, desc in cargos_cat_data:
            _, created = CargoCatalogo.objects.get_or_create(
                codigo=cod,
                defaults={"descripcion": desc, "activo": True},
            )
            if created:
                resumen["cargos_catalogo"] += 1

        tipos_aut_data = [
            "RESOLUCIÓN",
            "DISPOSICIÓN",
        ]
        for nom in tipos_aut_data:
            _, created = TipoAutorizacion.objects.get_or_create(
                nombre=nom,
                defaults={"activo": True},
            )
            if created:
                resumen["tipos_autorizacion"] += 1

        tipos_lic_data = [
            {
                "codigo": "LIC-340A",
                "articulo": "Art. 340-A",
                "descripcion": "Enfermedad de Corto Tratamiento",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 30,
                "cuadro_mensual": "IL-01",
                "hoja_pdf": "1-2",
            },
            {
                "codigo": "LIC-340B",
                "articulo": "Art. 340-B",
                "descripcion": "Afección de Largo Tratamiento",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 180,
                "cuadro_mensual": "IL-01",
                "hoja_pdf": "1-2",
            },
            {
                "codigo": "LIC-340D",
                "articulo": "Art. 340-D",
                "descripcion": "Atención Familiar Enfermo",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 20,
                "cuadro_mensual": "IL-01",
                "hoja_pdf": "1-2",
            },
            {
                "codigo": "LIC-341",
                "articulo": "Art. 341",
                "descripcion": "Licencia por Maternidad",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 135,
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
            },
            {
                "codigo": "LIC-343",
                "articulo": "Art. 343",
                "descripcion": "Matrimonio",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 10,
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
            },
            {
                "codigo": "LIC-344",
                "articulo": "Art. 344",
                "descripcion": "Duelo Familiar",
                "categoria": "LICENCIA",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 5,
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
            },
            {
                "codigo": "LIC-345",
                "articulo": "Art. 345",
                "descripcion": "Exámenes o Perfeccionamiento Docente",
                "categoria": "PERMISO",
                "forma_pago": "CON_GOCE",
                "goce_haberes": True,
                "tope_anual": 28,
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
            },
            {
                "codigo": "LIC-346",
                "articulo": "Art. 346",
                "descripcion": "Razones Particulares",
                "categoria": "PERMISO",
                "forma_pago": "SIN_GOCE",
                "goce_haberes": False,
                "tope_anual": 6,
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
            },
        ]
        lic_objs = {}
        for ldata in tipos_lic_data:
            lic, created = TipoLicencia.objects.get_or_create(
                codigo=ldata["codigo"],
                defaults=ldata,
            )
            lic_objs[ldata["codigo"]] = lic
            if created:
                resumen["tipos_licencia"] += 1

        # Feriado oficial de Octubre 2026: 12 de Octubre
        feriado_oct12, created = DiaNoLaborable.objects.get_or_create(
            fecha=datetime.date(2026, 10, 12),
            defaults={
                "tipo": "FERIADO",
                "descripcion": "Día del Respeto a la Diversidad Cultural",
                "creado_por": usuario,
            },
        )
        if created:
            resumen["dias_no_laborables"] += 1

        # -------------------------------------------------------------
        # 2. Espacios Curriculares
        # -------------------------------------------------------------
        espacios_data = [
            {
                "codigo": "DS-101",
                "nombre": "Programación I",
                "carrera": "Tecnicatura Superior en Desarrollo de Software",
                "anio": 1,
            },
            {
                "codigo": "DS-201",
                "nombre": "Programación II",
                "carrera": "Tecnicatura Superior en Desarrollo de Software",
                "anio": 2,
            },
            {
                "codigo": "DS-202",
                "nombre": "Bases de Datos",
                "carrera": "Tecnicatura Superior en Desarrollo de Software",
                "anio": 2,
            },
            {
                "codigo": "DS-301",
                "nombre": "Práctica Profesionalizante III",
                "carrera": "Tecnicatura Superior en Desarrollo de Software",
                "anio": 3,
            },
            {
                "codigo": "IA-101",
                "nombre": "Matemática Aplicada a IA",
                "carrera": "Tecnicatura Superior en Inteligencia Artificial",
                "anio": 1,
            },
        ]
        espacio_objs = {}
        for edata in espacios_data:
            esp, created = EspacioCurricular.objects.get_or_create(
                codigo=edata["codigo"],
                defaults=edata,
            )
            espacio_objs[edata["codigo"]] = esp
            if created:
                resumen["espacios"] += 1

        # -------------------------------------------------------------
        # 3. Docentes y Cargos
        # -------------------------------------------------------------
        docentes_data = [
            {
                "dni": "20111222",
                "apellido": "Acosta",
                "nombre": "Valeria",
                "sexo": "F",
                "contacto": "valeria.acosta@iesetyfp.edu.ar",
                "cargos": [
                    {
                        "codigo_cargo": "CARGO-20111222-DS101",
                        "materia": espacio_objs["DS-101"],
                        "situacion_revista": "TIT",
                        "horas_lunes": 4,
                        "dia_lunes": "4 hs",
                        "horas_miercoles": 4,
                        "dia_miercoles": "4 hs",
                        "resolucion": "Res. 101/24",
                    }
                ],
            },
            {
                "dni": "21222333",
                "apellido": "Benítez",
                "nombre": "Carlos",
                "sexo": "M",
                "contacto": "carlos.benitez@iesetyfp.edu.ar",
                "cargos": [
                    {
                        "codigo_cargo": "CARGO-21222333-DS201",
                        "materia": espacio_objs["DS-201"],
                        "situacion_revista": "INT",
                        "horas_martes": 3,
                        "dia_martes": "3 hs",
                        "horas_jueves": 3,
                        "dia_jueves": "3 hs",
                        "resolucion": "Res. 202/24",
                    }
                ],
            },
            {
                "dni": "22333444",
                "apellido": "Castillo",
                "nombre": "Mariana",
                "sexo": "F",
                "contacto": "mariana.castillo@iesetyfp.edu.ar",
                "cargos": [
                    {
                        "codigo_cargo": "CARGO-22333444-DS202",
                        "materia": espacio_objs["DS-202"],
                        "situacion_revista": "TIT",
                        "horas_lunes": 3,
                        "dia_lunes": "3 hs",
                        "horas_viernes": 3,
                        "dia_viernes": "3 hs",
                        "resolucion": "Res. 303/24",
                    }
                ],
            },
            {
                "dni": "23444555",
                "apellido": "Domínguez",
                "nombre": "Roberto",
                "sexo": "M",
                "contacto": "roberto.dominguez@iesetyfp.edu.ar",
                "cargos": [
                    {
                        "codigo_cargo": "CARGO-23444555-DS301",
                        "materia": espacio_objs["DS-301"],
                        "situacion_revista": "TIT",
                        "horas_miercoles": 4,
                        "dia_miercoles": "4 hs",
                        "horas_jueves": 4,
                        "dia_jueves": "4 hs",
                        "resolucion": "Res. 404/24",
                    }
                ],
            },
            {
                "dni": "24555666",
                "apellido": "Espínola",
                "nombre": "Silvia",
                "sexo": "F",
                "contacto": "silvia.espinola@iesetyfp.edu.ar",
                "cargos": [
                    {
                        "codigo_cargo": "CARGO-24555666-IA101",
                        "materia": espacio_objs["IA-101"],
                        "situacion_revista": "INT",
                        "horas_lunes": 2,
                        "dia_lunes": "2 hs",
                        "horas_martes": 2,
                        "dia_martes": "2 hs",
                        "horas_jueves": 2,
                        "dia_jueves": "2 hs",
                        "resolucion": "Res. 505/24",
                    }
                ],
            },
        ]

        docente_map = {}
        for ddata in docentes_data:
            docente, created = Docente.objects.update_or_create(
                dni=ddata["dni"],
                defaults={
                    "apellido": ddata["apellido"],
                    "nombre": ddata["nombre"],
                    "sexo": ddata["sexo"],
                    "contacto": ddata["contacto"],
                    "activo": True,
                },
            )
            docente_map[ddata["dni"]] = docente
            if created:
                resumen["docentes"] += 1

            for cdata in ddata["cargos"]:
                cargo_defs = {
                    "materia": cdata["materia"],
                    "situacion_revista": cdata["situacion_revista"],
                    "horas_lunes": cdata.get("horas_lunes", 0),
                    "horas_martes": cdata.get("horas_martes", 0),
                    "horas_miercoles": cdata.get("horas_miercoles", 0),
                    "horas_jueves": cdata.get("horas_jueves", 0),
                    "horas_viernes": cdata.get("horas_viernes", 0),
                    "dia_lunes": cdata.get("dia_lunes", ""),
                    "dia_martes": cdata.get("dia_martes", ""),
                    "dia_miercoles": cdata.get("dia_miercoles", ""),
                    "dia_jueves": cdata.get("dia_jueves", ""),
                    "dia_viernes": cdata.get("dia_viernes", ""),
                    "resolucion": cdata.get("resolucion", ""),
                    "desde_texto": "SIN INICIO",
                    "hasta_texto": "SIN TERMINO",
                    "activo": True,
                }
                _, c_created = CargoDocente.objects.update_or_create(
                    docente=docente,
                    codigo_cargo=cdata["codigo_cargo"],
                    defaults=cargo_defs,
                )
                if c_created:
                    resumen["cargos_docente"] += 1

        # -------------------------------------------------------------
        # 4. Generar 1 mes completo de asistencia diaria (Octubre 2026)
        # -------------------------------------------------------------
        # Días hábiles de Octubre 2026 (del 1 al 31, excluyendo fines de semana
        # y el feriado del 12/10/2026).
        dias_mes = []
        for dia in range(1, 32):
            f = datetime.date(2026, 10, dia)
            if f.weekday() < 5 and f != datetime.date(2026, 10, 12):
                dias_mes.append(f)

        # Matriz de novedades para el mes de Octubre 2026:
        # 1. Valeria Acosta: Licencia por enfermedad (LIC-340A) del 19 al 21
        # 2. Carlos Benítez: Inasistencias ('I') el 08/10 y 27/10
        # 3. Mariana Castillo: Licencia por duelo (LIC-344) del 14 al 16
        # 4. Roberto Domínguez: Asistencia perfecta ('P') todo el mes
        # 5. Silvia Espínola: Permiso exámenes ('P' justificado) el 06/10 e 'I' el 22/10

        for fecha_actual in dias_mes:
            for dni, docente in docente_map.items():
                estado = "PRESENTE"
                marca = "P"
                tipo_lic = None
                justifica = True

                if dni == "20111222":  # Acosta
                    f_ini = datetime.date(2026, 10, 19)
                    f_fin = datetime.date(2026, 10, 21)
                    if f_ini <= fecha_actual <= f_fin:
                        estado = "LICENCIA"
                        marca = "LIC"
                        tipo_lic = lic_objs["LIC-340A"]
                elif dni == "21222333":  # Benítez
                    if fecha_actual in [
                        datetime.date(2026, 10, 8),
                        datetime.date(2026, 10, 27),
                    ]:
                        estado = "AUSENTE"
                        marca = "I"
                        justifica = False
                elif dni == "22333444":  # Castillo
                    f_ini = datetime.date(2026, 10, 14)
                    f_fin = datetime.date(2026, 10, 16)
                    if f_ini <= fecha_actual <= f_fin:
                        estado = "LICENCIA"
                        marca = "LIC"
                        tipo_lic = lic_objs["LIC-344"]
                elif dni == "24555666":  # Espínola
                    if fecha_actual == datetime.date(2026, 10, 6):
                        estado = "JUSTIFICADO"
                        marca = "P"
                        tipo_lic = lic_objs["LIC-345"]
                    elif fecha_actual == datetime.date(2026, 10, 22):
                        estado = "AUSENTE"
                        marca = "I"
                        justifica = False

                asistencia_defaults = {
                    "estado": estado,
                    "marca_diaria": marca,
                    "tipo_licencia": tipo_lic,
                    "justifica": justifica,
                    "oficina": "1452",
                    "anio_planilla": 2026,
                }
                if usuario:
                    asistencia_defaults["modificado_por"] = usuario

                _, a_created = RegistroAsistencia.objects.update_or_create(
                    docente=docente,
                    fecha=fecha_actual,
                    defaults=asistencia_defaults,
                )
                if a_created:
                    resumen["asistencias_creadas"] += 1
                else:
                    resumen["asistencias_actualizadas"] += 1

        # 5. Opcional: Generar planilla mensual para demo
        if generar_planilla:
            renglones = generar_planilla_mes(
                mes=10, anio=2026, usuario=usuario
            )
            resumen["renglones_planilla"] = len(renglones)

    return resumen
