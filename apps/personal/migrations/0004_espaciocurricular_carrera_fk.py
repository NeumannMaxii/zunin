# Generated manually for Ticket 12.9: Normalización Relacional de EspacioCurricular

import re
from django.db import migrations, models
import django.db.models.deletion


def mapear_carreras(apps, schema_editor):
    EspacioCurricular = apps.get_model("personal", "EspacioCurricular")
    Carrera = apps.get_model("personal", "Carrera")

    espacios = list(EspacioCurricular.objects.all())
    if not espacios:
        return

    for espacio in espacios:
        nombre_carrera = getattr(espacio, "carrera_str", None)
        if not nombre_carrera:
            nombre_carrera = "Carrera General"
        nombre_carrera = str(nombre_carrera).strip()

        carrera_obj = Carrera.objects.filter(nombre__iexact=nombre_carrera).first()
        if not carrera_obj:
            carrera_obj = Carrera.objects.filter(codigo__iexact=nombre_carrera).first()

        if not carrera_obj:
            palabras = [
                w
                for w in re.sub(r"[^A-Za-z0-9\s]", "", nombre_carrera).upper().split()
                if len(w) > 2
            ]
            codigo_base = "".join(w[0] for w in palabras)[:6] or "CAR"
            codigo = codigo_base
            idx = 1
            while Carrera.objects.filter(codigo=codigo).exists():
                idx += 1
                codigo = f"{codigo_base}{idx}"

            carrera_obj = Carrera.objects.create(
                codigo=codigo,
                nombre=nombre_carrera,
                activo=True,
            )

        espacio.carrera = carrera_obj
        espacio.save(update_fields=["carrera"])


def revertir_carreras(apps, schema_editor):
    EspacioCurricular = apps.get_model("personal", "EspacioCurricular")
    for espacio in EspacioCurricular.objects.all():
        if espacio.carrera:
            espacio.carrera_str = espacio.carrera.nombre
            espacio.save(update_fields=["carrera_str"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "personal",
            "0003_cargodocente_actualizado_en_cargodocente_creado_en",
        ),
    ]

    operations = [
        migrations.RenameField(
            model_name="espaciocurricular",
            old_name="carrera",
            new_name="carrera_str",
        ),
        migrations.AddField(
            model_name="espaciocurricular",
            name="carrera",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="espacios_curriculares",
                to="personal.carrera",
                verbose_name="Carrera",
            ),
        ),
        migrations.RunPython(mapear_carreras, reverse_code=revertir_carreras),
        migrations.AlterField(
            model_name="espaciocurricular",
            name="carrera",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="espacios_curriculares",
                to="personal.carrera",
                verbose_name="Carrera",
            ),
        ),
        migrations.RemoveField(
            model_name="espaciocurricular",
            name="carrera_str",
        ),
    ]
