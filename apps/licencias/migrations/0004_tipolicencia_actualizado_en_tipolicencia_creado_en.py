# Generated for Ticket 12.8: Trazabilidad Temporal en Modelos

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licencias", "0003_renglonplanillamensual_desactualizada"),
    ]

    operations = [
        migrations.AddField(
            model_name="tipolicencia",
            name="actualizado_en",
            field=models.DateTimeField(
                auto_now=True,
                verbose_name="Actualizado en",
            ),
        ),
        migrations.AddField(
            model_name="tipolicencia",
            name="creado_en",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="Creado en",
            ),
            preserve_default=False,
        ),
    ]

