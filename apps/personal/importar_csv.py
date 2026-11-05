"""
Re-exportación del módulo importer para compatibilidad hacia atrás en apps.personal.
"""

from .importer import (
    FORMATOS_FECHA,
    MAPA_SITUACION_REVISTA,
    importar_csv,
    importar_docentes_cargos_csv,
    importar_legajos_csv,
    parsear_fecha,
    parsear_fecha_desde,
    parsear_fecha_hasta,
)
from .management.commands.importar_csv import Command

__all__ = [
    "FORMATOS_FECHA",
    "MAPA_SITUACION_REVISTA",
    "parsear_fecha",
    "parsear_fecha_desde",
    "parsear_fecha_hasta",
    "importar_legajos_csv",
    "importar_docentes_cargos_csv",
    "importar_csv",
    "Command",
]
