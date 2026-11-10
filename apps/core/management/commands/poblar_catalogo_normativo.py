"""
Comando de Django para poblar el Catálogo Normativo completo según Ley 647-E
para Personal Titular, Interino y Suplente (Ticket 15.2).
"""

from django.core.management.base import BaseCommand
from apps.core.seeder import poblar_catalogo_normativo_ley647e


class Command(BaseCommand):
    help = (
        "Puebla el Catálogo Normativo completo de licencias, inasistencias "
        "y permisos según Ley 647-E para todos los regímenes de revista "
        "(Titular, Interino, Suplente)."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Iniciando carga del Catálogo Normativo Ley 647-E..."
            )
        )

        resumen = poblar_catalogo_normativo_ley647e()

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo Normativo cargado exitosamente:\n"
                f"  - Total especificaciones: {resumen['total']}\n"
                f"  - Registros creados: {resumen['creados']}\n"
                f"  - Registros actualizados: {resumen['actualizados']}"
            )
        )
