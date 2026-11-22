"""
Comando de Django para poblar la Oferta Académica oficial del IESETyFP (ISPETyP Chaco).
Incluye todas las Tecnicaturas Superiores y Profesorados con sus planes de estudio
y espacios curriculares organizados por año de cursada.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.personal.models import Carrera, PlanEstudio, EspacioCurricular
from apps.personal.oferta_academica_data import OFERTA_ACADEMICA_DATA


class Command(BaseCommand):
    help = (
        "Puebla o actualiza la oferta académica institucional (Carreras, Planes "
        "y Espacios Curriculares) con datos oficiales del IESETyFP de forma "
        "idempotente."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Iniciando carga de Oferta Académica oficial del IESETyFP..."
            )
        )

        resumen = {
            "carreras_creadas": 0,
            "carreras_actualizadas": 0,
            "planes_creados": 0,
            "planes_actualizados": 0,
            "materias_creadas": 0,
            "materias_actualizadas": 0,
        }

        with transaction.atomic():
            for c_data in OFERTA_ACADEMICA_DATA:
                carrera, c_created = Carrera.objects.update_or_create(
                    codigo=c_data["codigo"],
                    defaults={
                        "nombre": c_data["nombre"],
                        "activo": c_data.get("activo", True),
                    },
                )
                if c_created:
                    resumen["carreras_creadas"] += 1
                else:
                    resumen["carreras_actualizadas"] += 1

                plan_data = c_data.get("plan")
                plan = None
                if plan_data:
                    plan, p_created = PlanEstudio.objects.update_or_create(
                        carrera=carrera,
                        nombre=plan_data["nombre"],
                        defaults={
                            "resolucion": plan_data.get("resolucion", ""),
                            "anio_implementacion": plan_data.get("anio_implementacion"),
                            "activo": plan_data.get("activo", True),
                            "descripcion": plan_data.get("descripcion", ""),
                        },
                    )
                    if p_created:
                        resumen["planes_creados"] += 1
                    else:
                        resumen["planes_actualizados"] += 1

                for m_data in c_data.get("materias", []):
                    defaults = {
                        "nombre": m_data["nombre"],
                        "carrera": carrera,
                        "plan_estudio_ref": plan,
                        "plan_estudio": plan.nombre if plan else "",
                        "anio": m_data["anio"],
                        "regimen": m_data.get("regimen", "ANUAL"),
                        "turno": m_data.get("turno", "NOCHE"),
                        "comision": m_data.get("comision", "UNICA"),
                    }
                    _, m_created = EspacioCurricular.objects.update_or_create(
                        codigo=m_data["codigo"],
                        defaults=defaults,
                    )
                    if m_created:
                        resumen["materias_creadas"] += 1
                    else:
                        resumen["materias_actualizadas"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Oferta Académica cargada exitosamente:\n"
                f"  - Carreras: {resumen['carreras_creadas']} creadas, "
                f"{resumen['carreras_actualizadas']} actualizadas.\n"
                f"  - Planes de Estudio: {resumen['planes_creados']} creados, "
                f"{resumen['planes_actualizados']} actualizados.\n"
                f"  - Materias / Espacios: {resumen['materias_creadas']} creadas, "
                f"{resumen['materias_actualizadas']} actualizadas."
            )
        )
