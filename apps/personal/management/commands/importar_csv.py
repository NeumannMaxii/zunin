"""
Management command para importación CSV de legajos docentes y cargos (Ticket 3).
Consume el servicio de importación de apps.personal.importer.
"""

import os
from django.core.management.base import BaseCommand, CommandError
from apps.personal.importer import (
    FORMATOS_FECHA,
    MAPA_SITUACION_REVISTA,
    importar_csv,
    importar_docentes_cargos_csv,
    importar_legajos_csv,
    parsear_fecha,
    parsear_fecha_desde,
    parsear_fecha_hasta,
)


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


__all__ = [
    "Command",
    "FORMATOS_FECHA",
    "MAPA_SITUACION_REVISTA",
    "importar_csv",
    "importar_docentes_cargos_csv",
    "importar_legajos_csv",
    "parsear_fecha",
    "parsear_fecha_desde",
    "parsear_fecha_hasta",
]
