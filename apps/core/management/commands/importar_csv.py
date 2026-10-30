"""
Comando de Django para importar Docentes y Cargos desde archivos CSV (Ticket 3).
"""

from django.core.management.base import BaseCommand, CommandError
from apps.personal.importer import importar_docentes_cargos_csv


class Command(BaseCommand):
    help = (
        "Importa Docentes y Cargos desde un archivo CSV con encoding "
        "'utf-8-sig' y delimitador ';' de forma idempotente (Ticket 3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "archivo_csv",
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
        archivo_csv = options["archivo_csv"]
        encoding = options["encoding"]
        delimiter = options["delimiter"]

        self.stdout.write(
            self.style.NOTICE(f"Iniciando importación desde '{archivo_csv}'...")
        )

        try:
            resumen = importar_docentes_cargos_csv(
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

        if resumen["errores"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Avisos durante la importación ({len(resumen['errores'])}):"
                )
            )
            for err in resumen["errores"][:10]:
                self.stdout.write(self.style.WARNING(f"  * {err}"))
            if len(resumen["errores"]) > 10:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ... y {len(resumen['errores']) - 10} avisos más."
                    )
                )
