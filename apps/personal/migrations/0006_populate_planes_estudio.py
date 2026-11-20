# Generated manually for Ticket 19.1 Data Migration

from django.db import migrations


def migrar_planes_estudio_existentes(apps, schema_editor):
    """
    Migración de datos no destructiva:
    Crea entidades PlanEstudio para los espacios curriculares existentes
    que tengan un texto en su campo plan_estudio y asocia la FK plan_estudio_ref.
    """
    EspacioCurricular = apps.get_model('personal', 'EspacioCurricular')
    PlanEstudio = apps.get_model('personal', 'PlanEstudio')

    for espacio in EspacioCurricular.objects.all():
        if espacio.plan_estudio and espacio.carrera_id:
            nombre_plan = espacio.plan_estudio.strip()
            if nombre_plan:
                plan_obj, _ = PlanEstudio.objects.get_or_create(
                    carrera_id=espacio.carrera_id,
                    nombre=nombre_plan,
                    defaults={
                        'activo': True,
                        'descripcion': f'Plan curricular generado automáticamente para {espacio.nombre}',
                    }
                )
                espacio.plan_estudio_ref = plan_obj
                espacio.save(update_fields=['plan_estudio_ref'])


def revertir_planes_estudio(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0005_planestudio_espaciocurricular_plan_estudio_ref_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrar_planes_estudio_existentes,
            reverse_code=revertir_planes_estudio,
        ),
    ]
