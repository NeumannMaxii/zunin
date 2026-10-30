#!/usr/bin/env python
"""
Script ejecutable para importar CSV de docentes y cargos (Ticket 3).
Puede ejecutarse directamente: python importar_csv.py <ruta_archivo.csv>
o mediante manage.py: python manage.py importar_csv <ruta_archivo.csv>
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.core.management import call_command

    if len(sys.argv) < 2:
        print("Uso: python importar_csv.py <ruta_archivo.csv> [--delimiter ';']")
        sys.exit(1)

    call_command("importar_csv", *sys.argv[1:])

