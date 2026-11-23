"""
Comando de Django para poblar la nómina real de docentes del IESETyFP.
Carga los 37 docentes interinos oficiales extraídos del padrón institucional
de forma idempotente consumiendo el servicio de importación de apps.personal.
"""

import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.personal.importer import importar_legajos_csv


class Command(BaseCommand):
    help = (
        "Puebla o actualiza la nómina de docentes reales del IESETyFP "
        "desde el archivo CSV oficial de forma idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-file",
            type=str,
            default=None,
            help="Ruta alternativa al archivo CSV.",
        )

    def handle(self, *args, **options):
        csv_file = options.get("csv_file")
        if not csv_file:
            # Buscar en BASE_DIR/docs/nomina_docentes_reales.csv
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

        doc_c = resumen.get("docentes_creados", 0)
        doc_a = resumen.get("docentes_actualizados", 0)
        carg_c = resumen.get("cargos_creados", 0)
        carg_a = resumen.get("cargos_actualizados", 0)
        errores = resumen.get("errores", [])

        if errores:
            for err in errores:
                self.stdout.write(self.style.WARNING(f"  [AVISO] {err}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso finalizado con éxito:\n"
                f"  - Docentes creados: {doc_c}\n"
                f"  - Docentes actualizados: {doc_a}\n"
                f"  - Cargos creados: {carg_c}\n"
                f"  - Cargos actualizados: {carg_a}\n"
                f"  - Total procesados: {resumen.get('filas_procesadas', 0)}"
            )
        )
