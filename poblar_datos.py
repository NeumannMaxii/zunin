#!/usr/bin/env python
"""
Script ejecutable para poblar datos de prueba y demo de Octubre 2026 (Ticket 3).
Puede ejecutarse directamente: python poblar_datos.py [--reset]
o mediante manage.py: python manage.py poblar_datos [--reset]
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.core.management import call_command

    call_command("poblar_datos", *sys.argv[1:])
