"""
Comando de administración para la ingesta del Catálogo Maestro Oficial
de Licencias Estatutarias (155 Artículos - Ley 647-E y Planilla Ministerial).
Ticket 18.4.
"""

from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.licencias.models import TipoLicencia


def extraer_registros_excel(ruta_archivo):
    """
    Procesa la hoja 'CODIGO Y ARTICULO DE LICENCIA' del Excel institucional
    usando openpyxl en modo read_only.
    """
    import openpyxl

    wb = openpyxl.load_workbook(str(ruta_archivo), read_only=True)
    nombre_hoja = "CODIGO Y ARTICULO DE LICENCIA"
    if nombre_hoja not in wb.sheetnames:
        raise ValueError(f"No se encontró la hoja '{nombre_hoja}' en el libro.")

    ws = wb[nombre_hoja]
    rows = list(ws.iter_rows(values_only=True))

    registros = []
    last_desc = ""

    for i, r in enumerate(rows):
        if not any(r):
            continue

        reg_raw = str(r[0] or "").strip().upper()
        if "TIT" in reg_raw:
            reg = "TIT"
        elif "INT" in reg_raw:
            reg = "INT"
        elif "SUP" in reg_raw:
            reg = "SUP"
        else:
            reg = "TIT"

        code_raw = str(r[1]).strip() if r[1] is not None else ""
        art_raw = str(r[2]).strip() if r[2] is not None else ""
        desc_raw = str(r[3]).strip() if r[3] is not None else ""
        if desc_raw:
            last_desc = desc_raw
        else:
            desc_raw = last_desc

        # Inferencia de códigos faltantes en el Excel institucional
        if not code_raw:
            if i == 0:
                code_raw = "01.01.01"
                if not art_raw:
                    art_raw = "308"
            elif i == 1:
                code_raw = "01.01.02"
                if not art_raw:
                    art_raw = "331-A"
            elif i == 97:
                code_raw = "2.20.1-VL"
            elif i == 98:
                code_raw = "2.20.2-VL"
            elif i == 99:
                code_raw = "2.20.3-VL"
            elif i == 100:
                code_raw = "2.20.1-DPS"
            elif i == 101:
                code_raw = "2.20.2-DPS"
            elif i == 102:
                code_raw = "2.20.3-DPS"
            elif i == 152:
                code_raw = "3.13.1"
                if not art_raw:
                    art_raw = "318"
            elif i == 153:
                code_raw = "3.13.2"
            elif i == 154:
                code_raw = "3.13.3"
                if not art_raw:
                    art_raw = "347"

        pago_raw = str(r[5] or "").strip()
        if "50%" in pago_raw:
            forma_pago = "CINCUENTA_PORCIENTO"
            forma_goce = "50%"
            goce = True
        elif "sin goce" in pago_raw.lower():
            forma_pago = "SIN_GOCE"
            forma_goce = "Sin goce"
            goce = False
        else:
            forma_pago = "CON_GOCE"
            forma_goce = "100%"
            goce = True

        # Regla Oficial de Asignación de Cuadro (Ticket 18.4)
        if code_raw.startswith("01.") or code_raw.startswith("1."):
            cuadro = "IL-01"
            hoja = "1-2"
            categoria = "LICENCIA"
        else:
            cuadro = "IL-02"
            hoja = "3-6"
            perm_keywords = [
                "PERMISO", "DUELO", "EXAMEN", "MATRIMONIO", "DONACION",
                "CITACION", "LACTANCIA", "NATALICIO", "FAMILIAR"
            ]
            es_perm = any(w in desc_raw.upper() for w in perm_keywords)
            categoria = "Permiso" if es_perm else "LICENCIA"

        duracion = str(r[7] or "").strip()

        registros.append({
            "codigo": code_raw,
            "regimen": reg,
            "articulo": art_raw,
            "descripcion": desc_raw,
            "categoria": categoria,
            "forma_pago": forma_pago,
            "forma_goce": forma_goce,
            "goce_haberes": goce,
            "cuadro_mensual": cuadro,
            "hoja_pdf": hoja,
            "cantidad_duracion": duracion,
            "situacion_revista_aplicable": reg,
            "activo": True,
        })

    return registros


class Command(BaseCommand):
    """
    Comando para poblar el Catálogo Maestro Oficial de Licencias (155 Artículos).
    """

    help = (
        "Puebla el Catálogo Maestro Oficial de Licencias Estatutarias (155 "
        "artículos oficiales) desde el Excel institucional o su dataset."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            type=str,
            default="docs/PLANILLAS ESTADISITICAS MENSUALES PARA TRABAJAR.xlsx",
            help="Ruta al libro Excel con la hoja CODIGO Y ARTICULO DE LICENCIA.",
        )

    def handle(self, *args, **options):
        ruta_opcional = options.get("archivo")
        ruta_archivo = Path(ruta_opcional)
        if not ruta_archivo.is_absolute():
            ruta_archivo = settings.BASE_DIR / ruta_opcional

        registros = []
        if ruta_archivo.exists():
            self.stdout.write(
                self.style.NOTICE(f"Leyendo catálogo oficial desde: {ruta_archivo}")
            )
            try:
                registros = extraer_registros_excel(ruta_archivo)
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Error al leer Excel ({exc}). "
                        "Utilizando dataset oficial integrado."
                    )
                )
                from apps.licencias.catalogo_maestro_data import (
                    CATALOGO_MAESTRO_OFICIAL_155,
                )

                registros = CATALOGO_MAESTRO_OFICIAL_155
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "Archivo Excel no encontrado. Utilizando dataset oficial integrado."
                )
            )
            from apps.licencias.catalogo_maestro_data import (
                CATALOGO_MAESTRO_OFICIAL_155,
            )

            registros = CATALOGO_MAESTRO_OFICIAL_155

        creados = 0
        actualizados = 0

        with transaction.atomic():
            for item in registros:
                defaults = dict(item)
                codigo = defaults.pop("codigo")

                _, created = TipoLicencia.objects.update_or_create(
                    codigo=codigo,
                    defaults=defaults,
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingesta de Catálogo Maestro finalizada exitosamente:\n"
                f"  - Total códigos procesados: {len(registros)}\n"
                f"  - Creados: {creados}\n"
                f"  - Actualizados: {actualizados}\n"
                f"  - Total registros en BD: {TipoLicencia.objects.count()}"
            )
        )
