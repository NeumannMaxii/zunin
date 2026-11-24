"""
Comando de gestión Django para exportar una copia de seguridad completa en ZIP.
Ticket 22: Exportación de Copia de Seguridad Completa (Base de Datos en ZIP).

Uso:
  python manage.py export_backup_zip
  python manage.py export_backup_zip --output /ruta/personalizada/backup.zip
"""

import os
from django.core.management.base import BaseCommand
from apps.core.backup import generar_backup_completo_zip


class Command(BaseCommand):
    help = (
        "Genera un archivo ZIP con la copia de seguridad completa de la "
        "base de datos institucional (JSON + SQLite si aplica + Manifiesto)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Ruta completa o nombre del archivo ZIP de destino.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Iniciando generacion de copia de seguridad de la base de datos..."
            )
        )

        zip_buffer, nombre_sugerido, manifest = generar_backup_completo_zip(
            usuario=None
        )

        destino = options.get("output")
        if not destino:
            directorio_backups = os.path.join(os.getcwd(), "backups")
            os.makedirs(directorio_backups, exist_ok=True)
            destino = os.path.join(directorio_backups, nombre_sugerido)
        else:
            dir_padre = os.path.dirname(os.path.abspath(destino))
            if dir_padre:
                os.makedirs(dir_padre, exist_ok=True)

        with open(destino, "wb") as f_out:
            f_out.write(zip_buffer.getvalue())

        tamano_kb = len(zip_buffer.getvalue()) / 1024.0

        self.stdout.write(
            self.style.SUCCESS(
                f"Copia de seguridad generada con exito en: {destino}\n"
                f"Tamano: {tamano_kb:.2f} KB\n"
                f"Archivos en el ZIP: {', '.join(manifest['archivos_en_paquete'])}\n"
                f"Fecha: {manifest['fecha_generacion_local']}"
            )
        )
