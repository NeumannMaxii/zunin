"""
Pruebas unitarias para el importador CSV de docentes y cargos (Ticket 3).
"""

import io
import os
import tempfile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from apps.asistencia.models import RegistroAsistencia
from apps.personal.importer import importar_docentes_cargos_csv
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class ImportadorCSVTests(TestCase):
    """Suite de validación para el importador CSV de Docentes y CargoDocente."""

    def test_importar_csv_exitoso_crea_docentes_y_cargos(self):
        """
        Verifica que se importen correctamente Docentes y Cargos con
        delimitador ';' y encoding 'utf-8-sig', y que NO cree asistencias.
        """
        csv_content = (
            "DNI;Apellido;Nombre;Situación de Revista;Espacio Curricular;"
            "Lunes;Martes;Miércoles;Jueves;Viernes;Resolución\n"
            "30111222;Gómez;Martín;TITULAR;Programación I;4 hs;0;4 hs;0;0;Res. 101/25\n"
            "30222333;López;Ana;INTERINO;Bases de Datos;0;3;0;3;0;Res. 102/25\n"
        )
        stream = io.StringIO(csv_content)

        resumen = importar_docentes_cargos_csv(stream)

        self.assertEqual(resumen["docentes_creados"], 2)
        self.assertEqual(resumen["cargos_creados"], 2)
        self.assertEqual(resumen["filas_omitidas"], 0)

        # Verificar datos del primer docente y cargo
        gomez = Docente.objects.get(dni="30111222")
        self.assertEqual(gomez.apellido, "Gómez")
        self.assertEqual(gomez.nombre, "Martín")

        cargo_gomez = CargoDocente.objects.get(docente=gomez)
        self.assertEqual(cargo_gomez.situacion_revista, "TIT")
        self.assertEqual(cargo_gomez.horas_lunes, 4)
        self.assertEqual(cargo_gomez.horas_miercoles, 4)
        self.assertEqual(cargo_gomez.horas_martes, 0)
        self.assertEqual(cargo_gomez.resolucion, "Res. 101/25")

        # Verificar segundo docente
        lopez = Docente.objects.get(dni="30222333")
        cargo_lopez = CargoDocente.objects.get(docente=lopez)
        self.assertEqual(cargo_lopez.situacion_revista, "INT")
        self.assertEqual(cargo_lopez.horas_martes, 3)
        self.assertEqual(cargo_lopez.horas_jueves, 3)

        # Regla clave: No crea registros de asistencia
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

    def test_idempotencia_ejecutar_dos_veces_no_duplica_registros(self):
        """
        Criterio de idempotencia: ejecutar el importador dos veces seguidas
        con el mismo CSV no duplica Docente ni CargoDocente.
        """
        csv_content = (
            "dni;apellido;nombre;situacion_revista;materia;lunes;martes\n"
            "40111222;Pereyra;Lucas;TIT;Sistemas Operativos;4;2\n"
            "40222333;Fernández;María;SUP;Redes de Datos;0;4\n"
        )

        # Primera ejecución
        resumen_1 = importar_docentes_cargos_csv(io.StringIO(csv_content))
        total_docentes_1 = Docente.objects.count()
        total_cargos_1 = CargoDocente.objects.count()

        self.assertEqual(resumen_1["docentes_creados"], 2)
        self.assertEqual(resumen_1["cargos_creados"], 2)
        self.assertEqual(total_docentes_1, 2)
        self.assertEqual(total_cargos_1, 2)

        # Segunda ejecución con los mismos datos
        resumen_2 = importar_docentes_cargos_csv(io.StringIO(csv_content))
        total_docentes_2 = Docente.objects.count()
        total_cargos_2 = CargoDocente.objects.count()

        self.assertEqual(resumen_2["docentes_creados"], 0)
        self.assertEqual(resumen_2["cargos_creados"], 0)
        self.assertEqual(resumen_2["docentes_actualizados"], 2)
        self.assertEqual(resumen_2["cargos_actualizados"], 2)
        self.assertEqual(total_docentes_1, total_docentes_2)
        self.assertEqual(total_cargos_1, total_cargos_2)

    def test_mapeo_situacion_revista_tit_int_sup(self):
        """
        Valida el mapeo de situaciones de revista:
        TITULAR -> TIT, INTERINO -> INT, SUPLENTE -> SUP.
        """
        csv_content = (
            "DNI;Docente;Situación de Revista;Materia\n"
            "50111111;Alonso, Marcos;TITULAR;Materia 1\n"
            "50222222;Bravo, Beatriz;INTERINO;Materia 2\n"
            "50333333;Castro, Claudio;SUPLENTE;Materia 3\n"
            "50444444;Duarte, Daniela;SUP;Materia 4\n"
        )
        importar_docentes_cargos_csv(io.StringIO(csv_content))

        cargo_1 = CargoDocente.objects.get(docente__dni="50111111")
        cargo_2 = CargoDocente.objects.get(docente__dni="50222222")
        cargo_3 = CargoDocente.objects.get(docente__dni="50333333")
        cargo_4 = CargoDocente.objects.get(docente__dni="50444444")

        self.assertEqual(cargo_1.situacion_revista, "TIT")
        self.assertEqual(cargo_2.situacion_revista, "INT")
        self.assertEqual(cargo_3.situacion_revista, "SUP")
        self.assertEqual(cargo_4.situacion_revista, "SUP")

    def test_omitir_filas_invalidas(self):
        """
        Valida que se omitan filas con situación de revista no válida,
        filas sin DNI o filas sin Apellido/Nombre, procesando las válidas.
        """
        csv_content = (
            "DNI;Apellido;Nombre;Situación de Revista;Materia\n"
            ";SinDni;Juan;TITULAR;Materia 1\n"
            "60222222;;;TITULAR;Materia 2\n"
            "60333333;Revista;Invalida;CONTRATADO;Materia 3\n"
            "60444444;Revista;Vacia;;Materia 4\n"
            "60555555;Válido;Esteban;INTERINO;Materia 5\n"
        )
        resumen = importar_docentes_cargos_csv(io.StringIO(csv_content))

        self.assertEqual(resumen["total_filas"], 5)
        self.assertEqual(resumen["filas_omitidas"], 4)
        self.assertEqual(resumen["filas_procesadas"], 1)
        self.assertEqual(resumen["docentes_creados"], 1)

        valido = Docente.objects.filter(dni="60555555").first()
        self.assertIsNotNone(valido)
        self.assertEqual(valido.apellido, "Válido")

    def test_mapeo_horas_diarias_lunes_a_viernes(self):
        """
        Valida el parseo correcto de horas numéricas, texto con 'hs', 'X' (1 hs)
        y días sin carga (0 hs).
        """
        csv_content = (
            "DNI;Apellido;Nombre;Revista;Lunes;Martes;Miércoles;Jueves;Viernes\n"
            "70111222;Test;Horas;TIT;4 hs;X;0;-;2\n"
        )
        importar_docentes_cargos_csv(io.StringIO(csv_content))

        cargo = CargoDocente.objects.get(docente__dni="70111222")
        self.assertEqual(cargo.horas_lunes, 4)
        self.assertEqual(cargo.horas_martes, 1)  # 'X' mapea a 1 hora
        self.assertEqual(cargo.horas_miercoles, 0)
        self.assertEqual(cargo.horas_jueves, 0)
        self.assertEqual(cargo.horas_viernes, 2)
        self.assertEqual(cargo.total_horas_semanales, 7)

    def test_comando_management_importar_csv(self):
        """
        Valida la ejecución del comando de Django 'importar_csv'
        sobre un archivo físico.
        """
        csv_content = (
            "DNI;Apellido;Nombre;Situación de Revista;Materia\n"
            "80111222;Comando;Django;TITULAR;Algoritmos\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            encoding="utf-8-sig",
            delete=False,
        ) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            out = io.StringIO()
            call_command("importar_csv", tmp_path, stdout=out)
            salida = out.getvalue()
            self.assertIn("Importación finalizada con éxito", salida)
            self.assertTrue(Docente.objects.filter(dni="80111222").exists())
            self.assertTrue(
                EspacioCurricular.objects.filter(nombre="Algoritmos").exists()
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_comando_management_archivo_inexistente_levanta_error(self):
        """
        Valida que pasar una ruta inexistente al comando levante CommandError.
        """
        with self.assertRaises(CommandError):
            call_command("importar_csv", "ruta_inexistente_12345.csv")
