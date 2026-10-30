"""
Comando de Django para poblar datos de prueba y catálogos base (Ticket 3).
"""

from django.core.management.base import BaseCommand
from apps.core.seeder import poblar_datos_demo


class Command(BaseCommand):
    help = (
        "Puebla catálogos base, docentes, cargos y genera un mes completo "
        "de asistencia (Octubre 2026) con registros 'P', 'I' y 'LIC' (Ticket 3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina registros de asistencia de Octubre 2026 antes de poblar.",
        )
        parser.add_argument(
            "--generar-planilla",
            action="store_true",
            help=(
                "Ejecuta también el motor mensual para generar la planilla "
                "de Octubre 2026."
            ),
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)
        generar_planilla = options.get("generar_planilla", False)

        self.stdout.write(
            self.style.NOTICE("Iniciando población de datos base y demo...")
        )

        resumen = poblar_datos_demo(
            usuario=None,
            reset=reset,
            generar_planilla=generar_planilla,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Población de datos finalizada con éxito:\n"
                f"  - Carreras creadas: {resumen['carreras']}\n"
                f"  - Cargos de catálogo: {resumen['cargos_catalogo']}\n"
                f"  - Tipos de autorización: {resumen['tipos_autorizacion']}\n"
                f"  - Tipos de licencia: {resumen['tipos_licencia']}\n"
                f"  - Días no laborables: {resumen['dias_no_laborables']}\n"
                f"  - Espacios curriculares: {resumen['espacios']}\n"
                f"  - Docentes creados/verificados: {resumen['docentes']}\n"
                f"  - Cargos docentes: {resumen['cargos_docente']}\n"
                f"  - Asistencias diarias creadas: {resumen['asistencias_creadas']}\n"
                f"  - Asistencias actualizadas: {resumen['asistencias_actualizadas']}\n"
                f"  - Renglones de planilla mensual: {resumen['renglones_planilla']}"
            )
        )
