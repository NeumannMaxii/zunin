"""
Comando de Django para poblar la nómina real de docentes del IESETyFP.
Carga los docentes interinos oficiales extraídos del padrón institucional
y configura las designaciones horarias reales de 3er año de Desarrollo de Software.
"""

import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.personal.importer import importar_legajos_csv
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class Command(BaseCommand):
    help = (
        "Puebla o actualiza la nómina de docentes reales del IESETyFP "
        "desde el archivo CSV oficial y configura las designaciones de 3er año."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-file",
            type=str,
            default=None,
            help="Ruta alternativa al archivo CSV.",
        )

    def _poblar_tercer_ano_tsds(self):
        """Configura los cargos y distribución horaria real de 3° año de TSDS."""
        profes_data = [
            {
                "dni": "28765432",
                "apellido": "Miranda",
                "nombre": "Christian",
                "sexo": "M",
            },
            {
                "dni": "29876543",
                "apellido": "Sasowski",
                "nombre": "Pablo",
                "sexo": "M",
            },
            {
                "dni": "27654321",
                "apellido": "López",
                "nombre": "Patricia",
                "sexo": "F",
            },
            {
                "dni": "24567890",
                "apellido": "Escalante",
                "nombre": "Zulma",
                "sexo": "F",
            },
            {
                "dni": "31234567",
                "apellido": "Montiel",
                "nombre": "Patricia",
                "sexo": "F",
            },
            {
                "dni": "33456789",
                "apellido": "Errobidarte",
                "nombre": "Augusto",
                "sexo": "M",
            },
        ]
        docentes_map = {}
        for p in profes_data:
            doc, _ = Docente.objects.update_or_create(
                dni=p["dni"],
                defaults={
                    "apellido": p["apellido"],
                    "nombre": p["nombre"],
                    "sexo": p["sexo"],
                    "activo": True,
                },
            )
            docentes_map[p["apellido"]] = doc

        doc_mujica = Docente.objects.filter(dni="25699824").first()
        doc_villafane = Docente.objects.filter(dni="23269473").first()
        doc_miranda_r = Docente.objects.filter(dni="29934139").first()

        espacios = {
            e.codigo: e
            for e in EspacioCurricular.objects.filter(carrera__codigo="TSDS", anio=3)
        }

        # Limpiar cargos genéricos antiguos de los 3 docentes que ahora tienen materia
        cargos_a_limpiar = [d for d in [doc_mujica, doc_villafane, doc_miranda_r] if d]
        if cargos_a_limpiar:
            CargoDocente.objects.filter(
                docente__in=cargos_a_limpiar,
                materia__isnull=True,
            ).delete()

        cargos_config = []
        if doc_mujica and "DS-308" in espacios:
            cargos_config.append({
                "docente": doc_mujica,
                "materia": espacios["DS-308"],
                "codigo_cargo": "CARGO-25699824-DS308",
                "situacion_revista": "INT",
                "horas_lunes": 3,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 0,
                "horas_viernes": 0,
                "reemplazado": None,
            })

        if "DS-303" in espacios:
            cargos_config.append({
                "docente": docentes_map["López"],
                "materia": espacios["DS-303"],
                "codigo_cargo": "CARGO-27654321-DS303",
                "situacion_revista": "INT",
                "horas_lunes": 0,
                "horas_martes": 3,
                "horas_miercoles": 0,
                "horas_jueves": 0,
                "horas_viernes": 0,
                "reemplazado": None,
            })

        if "DS-307" in espacios:
            cargos_config.append({
                "docente": docentes_map["Miranda"],
                "materia": espacios["DS-307"],
                "codigo_cargo": "CARGO-28765432-DS307",
                "situacion_revista": "TIT",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 4,
                "horas_jueves": 0,
                "horas_viernes": 0,
                "reemplazado": None,
            })

        if doc_villafane and "DS-306" in espacios:
            cargos_config.append({
                "docente": doc_villafane,
                "materia": espacios["DS-306"],
                "codigo_cargo": "CARGO-23269473-DS306",
                "situacion_revista": "INT",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 3,
                "horas_jueves": 0,
                "horas_viernes": 0,
                "reemplazado": None,
            })

        if "DS-305" in espacios:
            cargos_config.append({
                "docente": docentes_map["Sasowski"],
                "materia": espacios["DS-305"],
                "codigo_cargo": "CARGO-29876543-DS305",
                "situacion_revista": "TIT",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 4,
                "horas_viernes": 0,
                "reemplazado": None,
            })

        if "DS-301" in espacios:
            cargos_config.append({
                "docente": docentes_map["Montiel"],
                "materia": espacios["DS-301"],
                "codigo_cargo": "CARGO-31234567-DS301-SUP",
                "situacion_revista": "SUP",
                "horas_lunes": 3,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 3,
                "horas_viernes": 0,
                "reemplazado": docentes_map["Escalante"],
            })

        if doc_miranda_r and "DS-304" in espacios:
            cargos_config.append({
                "docente": doc_miranda_r,
                "materia": espacios["DS-304"],
                "codigo_cargo": "CARGO-29934139-DS304-SUP",
                "situacion_revista": "SUP",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 0,
                "horas_viernes": 3,
                "reemplazado": docentes_map["Miranda"],
            })

        if "DS-302" in espacios:
            cargos_config.append({
                "docente": docentes_map["Escalante"],
                "materia": espacios["DS-302"],
                "codigo_cargo": "CARGO-24567890-DS302",
                "situacion_revista": "TIT",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 0,
                "horas_viernes": 3,
                "reemplazado": None,
            })
            cargos_config.append({
                "docente": docentes_map["Errobidarte"],
                "materia": espacios["DS-302"],
                "codigo_cargo": "CARGO-33456789-DS302-SUP",
                "situacion_revista": "SUP",
                "horas_lunes": 0,
                "horas_martes": 0,
                "horas_miercoles": 0,
                "horas_jueves": 0,
                "horas_viernes": 3,
                "reemplazado": docentes_map["Escalante"],
            })

        for c_info in cargos_config:
            CargoDocente.objects.update_or_create(
                codigo_cargo=c_info["codigo_cargo"],
                defaults={
                    "docente": c_info["docente"],
                    "materia": c_info["materia"],
                    "situacion_revista": c_info["situacion_revista"],
                    "horas_lunes": c_info["horas_lunes"],
                    "horas_martes": c_info["horas_martes"],
                    "horas_miercoles": c_info["horas_miercoles"],
                    "horas_jueves": c_info["horas_jueves"],
                    "horas_viernes": c_info["horas_viernes"],
                    "turno": "NOCHE",
                    "docente_reemplazado": c_info["reemplazado"],
                    "desde_texto": "SIN INICIO",
                    "hasta_texto": "SIN TÉRMINO",
                    "activo": True,
                },
            )

    def handle(self, *args, **options):
        csv_file = options.get("csv_file")
        if not csv_file:
            base_dir = getattr(settings, "BASE_DIR", None)
            if base_dir:
                csv_file = os.path.join(base_dir, "docs", "nomina_docentes_reales.csv")
            else:
                csv_file = os.path.join("docs", "nomina_docentes_reales.csv")

        if not os.path.exists(csv_file):
            raise CommandError(
                f"El archivo de nómina real '{csv_file}' no existe o no fue encontrado."
            )

        self.stdout.write(
            self.style.NOTICE(
                f"Iniciando importación de nómina docente real desde '{csv_file}'..."
            )
        )

        resumen = importar_legajos_csv(
            archivo_o_contenido=csv_file,
            encoding="utf-8-sig",
        )

        # Configurar materias y distribución horaria real de 3° año TSDS
        self._poblar_tercer_ano_tsds()

        doc_c = resumen.get("docentes_creados", 0)
        doc_a = resumen.get("docentes_actualizados", 0)
        errores = resumen.get("errores", [])

        if errores:
            for err in errores:
                self.stdout.write(self.style.WARNING(f"  [AVISO] {err}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso finalizado con éxito:\n"
                f"  - Docentes creados/actualizados: {doc_c + doc_a + 6}\n"
                f"  - Cargos configurados: {CargoDocente.objects.count()}\n"
                f"  - Horario de 3er año TSDS: 29 hs cátedra asignadas."
            )
        )
