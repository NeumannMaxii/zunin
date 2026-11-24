"""
Pruebas automatizadas para el Ticket 19.5:
Rediseño de Vista Diaria en Formato Planilla Tipo Parte de Bedelía
y Exportación a Excel (.xlsx) con detección automática de licencias.
"""

import datetime
from io import BytesIO
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import openpyxl

from apps.asistencia.models import RegistroAsistencia
from apps.asistencia.services import generar_excel_parte_diario
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.personal.models import (
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    PlanEstudio,
)

User = get_user_model()


class Ticket195ParteDiarioTests(TestCase):
    def setUp(self):
        # Usuario bedel / admin
        self.user_bedel = User.objects.create_user(
            username="bedel_test",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )

        # Carreras y Planes
        self.carrera_tsds = Carrera.objects.create(
            codigo="TSDS-195",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.carrera_meca = Carrera.objects.create(
            codigo="MEC-195",
            nombre="Tecnicatura en Mecatrónica",
            activo=True,
        )
        self.plan_tsds = PlanEstudio.objects.create(
            carrera=self.carrera_tsds,
            nombre="PLAN-TSDS-2026",
            anio_implementacion=2026,
            activo=True,
        )

        # Materias
        self.materia_prog = EspacioCurricular.objects.create(
            carrera=self.carrera_tsds,
            plan_estudio_ref=self.plan_tsds,
            codigo="PROG-195",
            nombre="Programación Avanzada",
            anio=2,
            comision="A",
            turno="MANANA",
        )
        self.materia_bd = EspacioCurricular.objects.create(
            carrera=self.carrera_tsds,
            plan_estudio_ref=self.plan_tsds,
            codigo="BD-195",
            nombre="Bases de Datos Relacionales",
            anio=2,
            comision="A",
            turno="NOCHE",
        )

        # Docentes
        self.docente_1 = Docente.objects.create(
            dni="35111222",
            apellido="Gómez",
            nombre="Carlos",
            sexo="M",
            fecha_nacimiento=datetime.date(1985, 10, 15),
            activo=True,
        )
        self.docente_2 = Docente.objects.create(
            dni="36333444",
            apellido="Fernández",
            nombre="Lucía",
            sexo="F",
            fecha_nacimiento=datetime.date(1990, 6, 20),
            activo=True,
        )

        # Cargos
        self.cargo_1 = CargoDocente.objects.create(
            docente=self.docente_1,
            materia=self.materia_prog,
            situacion_revista="TIT",
            horas_lunes=4,
            activo=True,
        )
        self.cargo_2 = CargoDocente.objects.create(
            docente=self.docente_2,
            materia=self.materia_bd,
            situacion_revista="INT",
            horas_lunes=3,
            activo=True,
        )

        # Tipo de Licencia
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="ART-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            cuadro_mensual="IL-01",
            activo=True,
        )

        self.fecha_lunes = datetime.date(2026, 6, 15)  # Es lunes

    def test_vista_diaria_get_filtros_operativos(self):
        """
        Verifica que AsistenciaDiariaView permita filtrar por fecha, turno,
        carrera y búsqueda de texto, calculando los KPIs.
        """
        self.client.force_login(self.user_bedel)
        url = (
            f"{reverse('asistencia:asistencia_diaria')}?"
            f"fecha={self.fecha_lunes.isoformat()}&turno=MANANA"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        grilla = resp.context["grilla"]
        self.assertEqual(len(grilla), 1)
        self.assertEqual(grilla[0]["cargo"].id, self.cargo_1.id)
        self.assertEqual(resp.context["turno_actual"], "MANANA")

        # Filtro por texto
        url_q = (
            f"{reverse('asistencia:asistencia_diaria')}?"
            f"fecha={self.fecha_lunes.isoformat()}&q=Fernández"
        )
        resp_q = self.client.get(url_q)
        self.assertEqual(resp_q.status_code, 200)
        grilla_q = resp_q.context["grilla"]
        self.assertEqual(len(grilla_q), 1)
        self.assertEqual(grilla_q[0]["docente"].apellido, "Fernández")

    def test_deteccion_automatica_licencia_estatutaria_activa(self):
        """
        Si un docente posee una LicenciaOtorgada vigente en la fecha,
        la grilla diaria la detecta, adjunta el objeto y sugiere LIC / LICENCIA.
        """
        LicenciaOtorgada.objects.create(
            docente=self.docente_1,
            cargo=self.cargo_1,
            tipo_licencia=self.tipo_lic,
            fecha_desde=datetime.date(2026, 6, 10),
            fecha_hasta_prevista=datetime.date(2026, 6, 20),
            estado="OTORGADA",
        )

        self.client.force_login(self.user_bedel)
        url = (
            f"{reverse('asistencia:asistencia_diaria')}?"
            f"fecha={self.fecha_lunes.isoformat()}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        grilla = resp.context["grilla"]
        item_1 = next(
            (it for it in grilla if it["cargo"].id == self.cargo_1.id),
            None,
        )
        self.assertIsNotNone(item_1)
        self.assertIsNotNone(item_1["licencia_activa"])
        self.assertEqual(item_1["estado_sugerido"], "LICENCIA")
        self.assertEqual(item_1["marca_sugerida"], "LIC")
        self.assertEqual(
            item_1["tipo_lic_id_sugerido"], self.tipo_lic.id
        )
        self.assertContains(resp, "Lic. Activa:")

    def test_exportacion_excel_parte_diario_xlsx(self):
        """
        Verifica que el parámetro export=excel genere un archivo .xlsx válido
        con encabezados institucionales, grilla, totales y firmas.
        """
        self.client.force_login(self.user_bedel)
        url = (
            f"{reverse('asistencia:asistencia_diaria')}?"
            f"fecha={self.fecha_lunes.isoformat()}&export=excel"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resp["Content-Type"],
        )
        self.assertIn("Parte_Diario_Bedelia_", resp["Content-Disposition"])

        # Cargar y verificar estructura del libro openpyxl
        wb = openpyxl.load_workbook(BytesIO(resp.content))
        ws = wb.active
        self.assertTrue(ws.title.startswith("Parte Diario"))

        # Fila 1: Título institucional
        self.assertIn("IESETyFP", str(ws["A1"].value))
        # Fila 2: Subtítulo
        self.assertIn("PARTE DIARIO", str(ws["A2"].value))
        # Fila 5: Encabezado 'N°'
        self.assertEqual(ws["A5"].value, "N°")

    def test_vista_excel_directa_url(self):
        """
        Verifica el funcionamiento de la URL dedicada /diaria/excel/.
        """
        self.client.force_login(self.user_bedel)
        url = (
            f"{reverse('asistencia:asistencia_diaria_excel')}?"
            f"fecha={self.fecha_lunes.isoformat()}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])

    def test_post_guardado_desde_pills_planilla(self):
        """
        Verifica que al guardar desde la vista de planilla, se persistan
        los registros con sus marcas y estados correspondientes.
        """
        self.client.force_login(self.user_bedel)
        post_data = {
            "fecha": self.fecha_lunes.isoformat(),
            f"estado_{self.cargo_1.id}": "PRESENTE",
            f"marca_diaria_{self.cargo_1.id}": "PR",
            f"estado_{self.cargo_2.id}": "AUSENTE",
            f"marca_diaria_{self.cargo_2.id}": "I",
            f"observaciones_{self.cargo_2.id}": "Aviso telefónico",
        }
        resp = self.client.post(
            reverse("asistencia:asistencia_diaria"), post_data
        )
        self.assertEqual(resp.status_code, 302)

        reg_1 = RegistroAsistencia.objects.get(
            cargo=self.cargo_1, fecha=self.fecha_lunes
        )
        reg_2 = RegistroAsistencia.objects.get(
            cargo=self.cargo_2, fecha=self.fecha_lunes
        )
        self.assertEqual(reg_1.estado, "PRESENTE")
        self.assertEqual(reg_1.marca_diaria, "PR")
        self.assertEqual(reg_2.estado, "AUSENTE")
        self.assertEqual(reg_2.marca_diaria, "I")
        self.assertEqual(reg_2.observaciones, "Aviso telefónico")

    def test_generar_excel_parte_diario_directo(self):
        """
        Prueba la función del servicio generar_excel_parte_diario directamente.
        """
        grilla = [
            {
                "cargo": self.cargo_1,
                "docente": self.docente_1,
                "registro": None,
                "licencia_activa": None,
                "horas_dia": 4,
            },
            {
                "cargo": self.cargo_2,
                "docente": self.docente_2,
                "registro": None,
                "licencia_activa": None,
                "horas_dia": 3,
            },
        ]
        wb = generar_excel_parte_diario(
            self.fecha_lunes,
            grilla,
            turno_filtro="MANANA",
            carrera_filtro="Desarrollo de Software",
        )
        self.assertIsNotNone(wb)
        ws = wb.active
        self.assertTrue(ws.title.startswith("Parte Diario"))
        self.assertEqual(ws["B6"].value, "Mañana")
