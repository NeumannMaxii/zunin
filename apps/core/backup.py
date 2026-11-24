"""
Módulo de exportación y respaldo de base de datos para el sistema Zunin.
Ticket 22: Exportación de Copia de Seguridad Completa (Base de Datos en ZIP).
"""

import io
import json
import logging
import os
import zipfile
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)


def recopilar_estadisticas_base_datos():
    """
    Recopila conteos de registros de las principales entidades del sistema
    para incluirlos en el manifiesto de la copia de seguridad.
    """
    modelos_clave = [
        ("personal", "Docente", "docentes"),
        ("personal", "CargoDocente", "cargos_docentes"),
        ("personal", "Carrera", "carreras"),
        ("personal", "PlanEstudio", "planes_estudio"),
        ("personal", "EspacioCurricular", "espacios_curriculares"),
        ("personal", "CargoCatalogo", "cargos_catalogo"),
        ("personal", "TipoAutorizacion", "tipos_autorizacion"),
        ("asistencia", "RegistroAsistencia", "asistencias_diarias"),
        ("asistencia", "Feriado", "feriados"),
        ("licencias", "LicenciaOtorgada", "licencias_otorgadas"),
        ("licencias", "TipoLicencia", "tipos_licencia"),
        ("licencias", "RenglonPlanillaMensual", "renglones_planilla"),
        ("licencias", "NumeradorDisposicion", "numeradores_disposicion"),
        ("auth", "User", "usuarios_sistema"),
    ]

    conteos = {}
    for app_label, model_name, clave in modelos_clave:
        try:
            model = apps.get_model(app_label, model_name)
            if model:
                conteos[clave] = model.objects.count()
        except Exception as exc:
            conteos[clave] = f"Error al consultar: {exc}"

    return conteos


def generar_contenido_readme():
    """
    Genera el texto de instrucciones para la restauración de la base de datos.
    """
    return (
        "======================================================================\n"
        "GUIA DE RESTAURACION DE COPIA DE SEGURIDAD - IESETyFP SISTEMA ZUNIN\n"
        "======================================================================\n\n"
        "Este archivo ZIP contiene el respaldo completo de la base de datos\n"
        "institucional del Instituto de Educacion Superior de Educacion Tecnica\n"
        "y Formacion Profesional (IESETyFP - Proyecto Zunin).\n\n"
        "ARCHIVOS CONTENIDOS EN ESTE PAQUETE:\n"
        "------------------------------------\n"
        "1. database_dump.json:\n"
        "   Volcado completo serializado en formato JSON con llaves foraneas\n"
        "   naturales. Compatible con cualquier motor de base de datos\n"
        "   (SQLite, MySQL, MariaDB, PostgreSQL).\n\n"
        "2. manifest.json:\n"
        "   Metadatos de la copia de seguridad: fecha y hora de generacion,\n"
        "   usuario responsable, motor de BD y recuento estadistico de registros.\n\n"
        "3. sqlite_database.sqlite3 (opcional):\n"
        "   Si la base de datos de origen es SQLite, se incluye una copia binaria\n"
        "   directa e instantanea del archivo de base de datos.\n\n"
        "----------------------------------------------------------------------\n"
        "METODO 1: Restauracion mediante comando loaddata (Recomendado)\n"
        "----------------------------------------------------------------------\n"
        "Apto para cualquier motor (SQLite, MySQL, MariaDB o PostgreSQL):\n\n"
        "1. Descomprima el archivo 'database_dump.json' en la raiz del proyecto.\n"
        "2. Asegurese de que las migraciones de Django esten aplicadas:\n"
        "   python manage.py migrate\n"
        "3. Importe los datos ejecutando:\n"
        "   python manage.py loaddata database_dump.json\n\n"
        "----------------------------------------------------------------------\n"
        "METODO 2: Restauracion directa para SQLite (db.sqlite3)\n"
        "----------------------------------------------------------------------\n"
        "Aplica unicamente si el entorno utiliza django.db.backends.sqlite3:\n\n"
        "1. Detenga el servidor Django (runserver, gunicorn, etc.).\n"
        "2. Realice una copia de resguardo de su archivo 'db.sqlite3' actual.\n"
        "3. Extraiga 'sqlite_database.sqlite3' y renombrelo a 'db.sqlite3'.\n"
        "4. Inicie nuevamente el servidor Django.\n"
        "======================================================================\n"
    )


def generar_backup_completo_zip(usuario=None):
    """
    Genera un archivo ZIP en memoria con la copia de seguridad completa:
      - database_dump.json: Dump completo de Django con natural foreign keys.
      - manifest.json: Información de auditoría, fecha y conteos.
      - README_RESTAURACION.txt: Manual de instrucciones para restauración.
      - sqlite_database.sqlite3: Copia binaria física si el motor es SQLite.

    Retorna:
      tuple (io.BytesIO, str, dict): (buffer_zip, nombre_archivo, manifest)
    """
    ahora = timezone.now()
    ahora_local = timezone.localtime(ahora)
    timestamp_str = ahora_local.strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"zunin_backup_IESETyFP_{timestamp_str}.zip"

    logger.info(
        "Iniciando generacion de copia de seguridad ZIP por usuario: %s",
        usuario.username if usuario and usuario.is_authenticated else "sistema",
    )

    # 1. Volcado completo de la base de datos en formato JSON
    dump_buffer = io.StringIO()
    call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=["contenttypes", "auth.permission"],
        indent=2,
        stdout=dump_buffer,
    )
    dump_json_bytes = dump_buffer.getvalue().encode("utf-8")

    # 2. Recopilación de estadísticas y metadatos para el manifiesto
    conteos = recopilar_estadisticas_base_datos()
    archivos_incluidos = [
        "database_dump.json",
        "manifest.json",
        "README_RESTAURACION.txt",
    ]

    # Verificar si es SQLite para incluir copia física binaria
    engine_name = settings.DATABASES["default"].get("ENGINE", "")
    db_name = settings.DATABASES["default"].get("NAME", "")
    sqlite_bytes = None

    if "sqlite" in engine_name.lower() and db_name:
        db_path = str(db_name)
        if os.path.exists(db_path) and os.path.isfile(db_path):
            try:
                with open(db_path, "rb") as f_sqlite:
                    sqlite_bytes = f_sqlite.read()
                archivos_incluidos.append("sqlite_database.sqlite3")
            except Exception as exc:
                logger.warning("No se pudo leer archivo sqlite: %s", exc)

    manifest_data = {
        "sistema": "IESETyFP - Sistema Zunin",
        "modulo": "Copia de Seguridad y Respaldo Institucional (Ticket 22)",
        "fecha_generacion_iso": ahora.isoformat(),
        "fecha_generacion_local": ahora_local.strftime("%d/%m/%Y %H:%M:%S"),
        "generado_por": (
            usuario.username
            if usuario and usuario.is_authenticated
            else "sistema"
        ),
        "usuario_nombre_completo": (
            usuario.get_full_name()
            if usuario and usuario.is_authenticated
            else "Operación Automática"
        ),
        "motor_base_datos": engine_name,
        "nombre_base_datos": str(db_name),
        "total_modelos_auditados": len(conteos),
        "estadisticas_registros": conteos,
        "archivos_en_paquete": archivos_incluidos,
    }
    manifest_bytes = json.dumps(manifest_data, indent=2, ensure_ascii=False).encode(
        "utf-8"
    )
    readme_bytes = generar_contenido_readme().encode("utf-8")

    # 3. Empaquetado comprimido ZIP en memoria
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(
        zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        zip_file.writestr("database_dump.json", dump_json_bytes)
        zip_file.writestr("manifest.json", manifest_bytes)
        zip_file.writestr("README_RESTAURACION.txt", readme_bytes)
        if sqlite_bytes:
            zip_file.writestr("sqlite_database.sqlite3", sqlite_bytes)

    zip_buffer.seek(0)
    logger.info(
        "Copia de seguridad ZIP finalizada exitosamente. Tamano: %d bytes",
        zip_buffer.getbuffer().nbytes,
    )

    return zip_buffer, nombre_archivo, manifest_data
