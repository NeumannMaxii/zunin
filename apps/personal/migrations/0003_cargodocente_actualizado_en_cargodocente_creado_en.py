# Generated for Ticket 12.8: Trazabilidad Temporal en Modelos

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "personal",
            "0002_cargodocente_dia_domingo_cargodocente_dia_sabado_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="cargodocente",
            name="actualizado_en",
            field=models.DateTimeField(
                auto_now=True,
                verbose_name="Actualizado en",
            ),
        ),
        migrations.AddField(
            model_name="cargodocente",
            name="creado_en",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="Creado en",
            ),
            preserve_default=False,
        ),
    ]

