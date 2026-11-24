"""
Pruebas automatizadas para el Ticket 22:
Exportación de Copia de Seguridad Completa (Base de Datos en ZIP).
"""

import io
import json
import os
import tempfile
import zipfile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.core.backup import (
    generar_backup_completo_zip,
    recopilar_estadisticas_base_datos,
)
from apps.personal.models import Carrera, Docente

User = get_user_model()


class Ticket22BackupZipTests(TestCase):
    def setUp(self):
        # Grupos de seguridad institucional
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_directiva, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )

        # Usuarios con distintos perfiles
        self.user_admin = User.objects.create_user(
            username="admin_backup",
            password="password123",
            first_name="Admin",
            last_name="General",
        )
        self.user_admin.groups.add(self.grupo_admin)

        self.superuser = User.objects.create_superuser(
            username="super_backup",
            password="password123",
            email="super@iesetyfp.edu.ar",
        )

        self.user_bedelia = User.objects.create_user(
            username="bedelia_backup",
            password="password123",
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_directiva = User.objects.create_user(
            username="directiva_backup",
            password="password123",
        )
        self.user_directiva.groups.add(self.grupo_directiva)

        # Datos de muestra institucionales
        self.docente = Docente.objects.create(
            nombre="María Eugenia",
            apellido="Vidal",
            dni="29888999",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-T22",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )

    def test_recopilar_estadisticas_base_datos(self):
        """Verifica que el diccionario de conteos registre las entidades clave."""
        stats = recopilar_estadisticas_base_datos()
        self.assertIn("docentes", stats)
        self.assertIn("carreras", stats)
        self.assertIn("usuarios_sistema", stats)
        self.assertGreaterEqual(stats["docentes"], 1)
        self.assertGreaterEqual(stats["carreras"], 1)

    def test_servicio_generar_backup_completo_zip(self):
        """
        Verifica que generar_backup_completo_zip genere un ZIP válido
        con database_dump.json, manifest.json y README_RESTAURACION.txt.
        """
        zip_buf, filename, manifest = generar_backup_completo_zip(
            usuario=self.user_admin
        )

        self.assertTrue(filename.startswith("zunin_backup_IESETyFP_"))
        self.assertTrue(filename.endswith(".zip"))
        self.assertGreater(len(zip_buf.getvalue()), 0)

        # Verificar contenido del archivo ZIP
        with zipfile.ZipFile(zip_buf, "r") as zf:
            archivos = zf.namelist()
            self.assertIn("database_dump.json", archivos)
            self.assertIn("manifest.json", archivos)
            self.assertIn("README_RESTAURACION.txt", archivos)

            # Validar JSON de dump
            dump_raw = zf.read("database_dump.json").decode("utf-8")
            dump_json = json.loads(dump_raw)
            self.assertIsInstance(dump_json, list)
            # El dump debe incluir el docente creado
            dnis = [
                item["fields"].get("dni")
                for item in dump_json
                if item.get("model") == "personal.docente"
            ]
            self.assertIn("29888999", dnis)

            # Validar manifest.json
            manifest_raw = zf.read("manifest.json").decode("utf-8")
            manifest_json = json.loads(manifest_raw)
            self.assertEqual(manifest_json["generado_por"], "admin_backup")
            self.assertIn("estadisticas_registros", manifest_json)
            self.assertEqual(
                manifest_json["estadisticas_registros"]["docentes"], 1
            )

    def test_vista_exportar_backup_admin_institucional_permitido(self):
        """Admin_Institucional puede descargar la copia de seguridad (HTTP 200)."""
        self.client.force_login(self.user_admin)
        url = reverse("core:exportar_backup")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        # Verificar que la respuesta contiene un ZIP íntegro
        zip_content = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_content, "r") as zf:
            self.assertIn("database_dump.json", zf.namelist())

    def test_vista_exportar_backup_superusuario_permitido(self):
        """Superusuario puede descargar la copia de seguridad (HTTP 200)."""
        self.client.force_login(self.superuser)
        url = reverse("core:exportar_backup")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

    def test_vista_exportar_backup_bedelia_operadora_prohibido_403(self):
        """Usuarios del rol Bedelia_Operadoras reciben HTTP 403 Forbidden."""
        self.client.force_login(self.user_bedelia)
        url = reverse("core:exportar_backup")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_vista_exportar_backup_consulta_directiva_prohibido_403(self):
        """Usuarios del rol Consulta_Directiva reciben HTTP 403 Forbidden."""
        self.client.force_login(self.user_directiva)
        url = reverse("core:exportar_backup")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_vista_exportar_backup_anonimo_redirige_login_302(self):
        """Usuarios anónimos son redirigidos al formulario de login (HTTP 302)."""
        self.client.logout()
        url = reverse("core:exportar_backup")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_management_command_export_backup_zip(self):
        """Verifica la ejecución del comando de consola manage.py export_backup_zip."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            archivo_destino = os.path.join(tmp_dir, "test_backup.zip")
            out = io.StringIO()

            call_command(
                "export_backup_zip",
                output=archivo_destino,
                stdout=out,
            )

            self.assertTrue(os.path.exists(archivo_destino))
            self.assertGreater(os.path.getsize(archivo_destino), 0)

            # Validar que el archivo creado es un ZIP con database_dump.json
            with zipfile.ZipFile(archivo_destino, "r") as zf:
                self.assertIn("database_dump.json", zf.namelist())
                self.assertIn("manifest.json", zf.namelist())

            salida_cmd = out.getvalue()
            self.assertIn("Copia de seguridad generada con exito", salida_cmd)
