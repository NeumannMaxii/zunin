"""
Pruebas automatizadas para el Ticket 18.5:
Exportación Oficial a Excel (.xlsx) Formateado según IL-01 e IL-02.

Valida:
1. Autenticación obligatoria (LoginRequiredMixin): redirección de usuarios
   anónimos a login.
2. Respuesta HTTP 200 con Content-Type oficial y Content-Disposition dinámico:
   Planilla_Mensual_{mes}_{anio}.xlsx.
3. Estructura del libro openpyxl: Bloque IL-01 (Salud), espaciador intermedio y
   Bloque IL-02 (Otros / Permisos) con membretes institucionales oficiales.
4. Distribución automática de renglones entre IL-01 e IL-02 según encuadre legal.
5. Dinamismo de nombres de archivo, títulos, meses en texto y años.
6. Presencia del botón institucional verde en la interfaz web de planillas.
"""

import datetime
import io
import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import CargoDocente, Carrera, Docente, EspacioCurricular


class ExportarPlanillaExcelTestCase(TestCase):
    """Suite de pruebas para la exportación oficial a Excel de planillas mensuales."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="bedel_test",
            password="password123",
            email="bedel@iesetyp.edu.ar",
        )
        self.client.login(username="bedel_test", password="password123")

        # Datos base de carrera y materia
        self.carrera = Carrera.objects.create(
            codigo="TEC-DES",
            nombre="Tecnicatura Superior en Desarrollo de Software",
        )
        self.materia_prog = EspacioCurricular.objects.create(
            carrera=self.carrera,
            codigo="PROG-I",
            nombre="Programación I",
            anio=1,
        )
        self.materia_bd = EspacioCurricular.objects.create(
            carrera=self.carrera,
            codigo="BD-I",
            nombre="Bases de Datos I",
            anio=1,
        )

        # Docentes
        self.docente_salud = Docente.objects.create(
            dni="20111222",
            nombre="Laura",
            apellido="Gómez",
            sexo="F",
        )
        self.docente_permiso = Docente.objects.create(
            dni="20333444",
            nombre="Carlos",
            apellido="Benítez",
            sexo="M",
        )

        # Cargos
        self.cargo_salud = CargoDocente.objects.create(
            docente=self.docente_salud,
            materia=self.materia_prog,
            tipo_cargo="HORAS",
            codigo_cargo="166",
            situacion_revista="TIT",
            horas_lunes=4,
            dia_lunes=True,
            activo=True,
        )
        self.cargo_permiso = CargoDocente.objects.create(
            docente=self.docente_permiso,
            materia=self.materia_bd,
            tipo_cargo="HORAS",
            codigo_cargo="166",
            situacion_revista="INT",
            horas_martes=3,
            dia_martes=True,
            activo=True,
        )

        # Tipos de Licencia (IL-01 e IL-02)
        self.lic_salud, _ = TipoLicencia.objects.get_or_create(
            codigo="01.01.01",
            defaults={
                "articulo": "308",
                "descripcion": "Enfermedad Común Corto Tratamiento",
                "cuadro_mensual": "IL-01",
                "hoja_pdf": "1-2",
                "regimen": "TIT",
            },
        )
        self.lic_permiso, _ = TipoLicencia.objects.get_or_create(
            codigo="2.13.1",
            defaults={
                "articulo": "323",
                "descripcion": "Examen o Perfeccionamiento Docente",
                "cuadro_mensual": "IL-02",
                "hoja_pdf": "3-6",
                "regimen": "INT",
            },
        )

    def test_exportar_excel_requiere_autenticacion(self):
        """Valida que un usuario anónimo sea redirigido a login al solicitar Excel."""
        self.client.logout()
        url = reverse("licencias:exportar_planilla_excel")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_exportar_excel_respuesta_http_200_y_headers(self):
        """Valida respuesta 200, Content-Type oficial y Content-Disposition dinámico."""
        url = reverse("licencias:exportar_planilla_excel") + "?mes=8&anio=2026"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(
            'attachment; filename="Planilla_Mensual_8_2026.xlsx"',
            response["Content-Disposition"],
        )

    def test_exportar_excel_contenido_binario_y_estructura_openpyxl(self):
        """
        Valida que el contenido binario sea un libro openpyxl válido con membretes.
        """
        url = reverse("licencias:exportar_planilla_excel") + "?mes=8&anio=2026"
        response = self.client.get(url)

        # Cargar libro en memoria
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("Planilla 8_2026", wb.sheetnames)
        ws = wb["Planilla 8_2026"]

        # Recopilar todos los valores textuales de la hoja
        valores = []
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is not None:
                    valores.append(str(cell))

        todo_texto = " ".join(valores)

        # Validar membretes y datos oficiales requeridos
        self.assertIn("SELLO REGIONAL", todo_texto)
        self.assertIn(
            "INFORME MENSUAL DE LICENCIAS POR ENFERMEDAD (IL-01) - ANEXO I",
            todo_texto,
        )
        self.assertIn(
            "INFORME MENSUAL DE LICENCIAS Y OTROS (IL-02) - ANEXO I",
            todo_texto,
        )
        self.assertIn("MES: AGOSTO", todo_texto)
        self.assertIn("AÑO: 2026", todo_texto)
        self.assertIn("1452", todo_texto)

    def test_distribucion_automatica_il01_e_il02(self):
        """
        Valida que los renglones se ubiquen en el bloque IL-01 o IL-02 según
        su encuadre estatutario.
        """
        # Renglón de Salud (IL-01)
        r_salud = RenglonPlanillaMensual.objects.create(
            docente=self.docente_salud,
            cargo=self.cargo_salud,
            tipo_licencia=self.lic_salud,
            cuadro="IL-01",
            mes=8,
            anio=2026,
            oficina="1452",
            desde=datetime.date(2026, 8, 3),
            hasta=datetime.date(2026, 8, 5),
            horas_afectadas=4,
            marca_origen="LIC",
            tipo_instrumento="DISPOSICION",
            numero_instrumento="055/2026",
            desactualizada=False,
        )

        # Renglón de Permiso (IL-02)
        r_permiso = RenglonPlanillaMensual.objects.create(
            docente=self.docente_permiso,
            cargo=self.cargo_permiso,
            tipo_licencia=self.lic_permiso,
            cuadro="IL-02",
            mes=8,
            anio=2026,
            oficina="1452",
            desde=datetime.date(2026, 8, 10),
            hasta=datetime.date(2026, 8, 11),
            horas_afectadas=3,
            marca_origen="LIC",
            tipo_instrumento="RESOLUCION",
            numero_instrumento="Res. 1450/2026",
            desactualizada=False,
        )

        url = reverse("licencias:exportar_planilla_excel") + "?mes=8&anio=2026"
        response = self.client.get(url)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))

        fila_il01_titulo = None
        fila_il02_titulo = None
        fila_docente_salud = None
        fila_docente_permiso = None

        for idx, row in enumerate(rows):
            fila_str = " ".join([str(c) for c in row if c is not None])
            if "INFORME MENSUAL DE LICENCIAS POR ENFERMEDAD (IL-01)" in fila_str:
                fila_il01_titulo = idx
            if "INFORME MENSUAL DE LICENCIAS Y OTROS (IL-02)" in fila_str:
                fila_il02_titulo = idx
            if r_salud.docente.dni in fila_str:
                fila_docente_salud = idx
            if r_permiso.docente.dni in fila_str:
                fila_docente_permiso = idx

        self.assertIsNotNone(fila_il01_titulo)
        self.assertIsNotNone(fila_il02_titulo)
        self.assertIsNotNone(fila_docente_salud)
        self.assertIsNotNone(fila_docente_permiso)

        # El docente de salud debe figurar entre el título IL-01 y el título IL-02
        self.assertTrue(fila_il01_titulo < fila_docente_salud < fila_il02_titulo)

        # El docente de permiso debe figurar después del título IL-02
        self.assertTrue(fila_il02_titulo < fila_docente_permiso)

    def test_nombre_archivo_y_titulos_dinamicos(self):
        """
        Valida que nombres de archivo y membretes reflejen dinámicamente mes y año.
        """
        url = reverse("licencias:exportar_planilla_excel") + "?mes=10&anio=2025"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'attachment; filename="Planilla_Mensual_10_2025.xlsx"',
            response["Content-Disposition"],
        )

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        valores = [str(c) for r in ws.iter_rows(values_only=True) for c in r if c]
        todo_texto = " ".join(valores)

        self.assertIn("MES: OCTUBRE", todo_texto)
        self.assertIn("AÑO: 2025", todo_texto)

    def test_boton_en_interfaz_web_planilla_list(self):
        """Valida la presencia del botón verde oficial en la vista web de planillas."""
        url = reverse("licencias:planilla_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Botón verde institucional
        self.assertContains(response, "Exportar Excel Oficial (.xlsx)")
        self.assertContains(response, reverse("licencias:exportar_planilla_excel"))
        self.assertContains(response, "bg-emerald-600")
