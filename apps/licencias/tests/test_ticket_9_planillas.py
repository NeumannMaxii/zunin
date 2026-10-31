"""
Pruebas automatizadas para Ticket 9: Pantalla Mensual (Planillas).
Valida:
- Visualización de cuadros IL-01 e IL-02 con selector de tipo_licencia por renglón.
- Edición de renglón: cambiar de cuadro preserva intacto el número de
  instrumento original.
- Exportación CSV con los encabezados exactos requeridos:
  Cuadro, N° Disposición, Docente, DNI, Desde, Hasta, Materias, Horas,
  Tipo Licencia.
"""

import csv
import datetime
import io
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Docente,
    EspacioCurricular,
)


class Ticket9PantallaMensualPlanillasTests(TestCase):
    """
    Suite de pruebas para validar los requerimientos y criterios del Ticket 9.
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="operador_ticket9",
            password="password123",
            email="ticket9@iesetyfp.edu.ar",
        )
        self.client.login(username="operador_ticket9", password="password123")

        # Catálogo de Licencias
        self.lic_il01 = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.lic_il02 = TipoLicencia.objects.create(
            codigo="LIC-341",
            articulo="341",
            descripcion="Maternidad y Familia",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-02",
            activo=True,
        )

        # Personal y Cargos
        self.docente = Docente.objects.create(
            dni="25123456",
            apellido="Navarro",
            nombre="Esteban",
            sexo="M",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="PROG-I",
            nombre="Programación I",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            horas_lunes=4,
            horas_martes=4,
            activo=True,
        )

        # Renglón de Planilla Mensual inicial en IL-01 con Disposición
        self.renglon_1 = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.lic_il01,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 5),
            hasta=datetime.date(2026, 10, 8),
            horas_afectadas=8,
            numero_instrumento="045/2026",
            creado_por=self.user,
        )

        # Renglón de Planilla Mensual inicial en IL-02
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="BEDEL-01",
            descripcion="Bedelía Turno Noche",
        )
        self.cargo_adm = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            tipo_cargo="CARGO_ADM",
            situacion_revista="INT",
            horas_lunes=5,
            activo=True,
        )
        self.renglon_2 = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_adm,
            tipo_licencia=self.lic_il02,
            cuadro="IL-02",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 12),
            hasta=datetime.date(2026, 10, 14),
            horas_afectadas=5,
            numero_instrumento="046/2026",
            creado_por=self.user,
        )

    def test_visualizar_cuadros_il01_e_il02_y_selector_por_renglon(self):
        """
        Valida que la vista liste los renglones con selector de tipo_licencia
        y permita filtrar por cuadros IL-01 e IL-02.
        """
        response = self.client.get(reverse("licencias:planilla_list"))
        self.assertEqual(response.status_code, 200)

        # Verifica ambos cuadros en la vista general
        self.assertContains(response, "IL-01")
        self.assertContains(response, "IL-02")
        self.assertContains(response, "045/2026")
        self.assertContains(response, "046/2026")
        self.assertContains(response, "Navarro, Esteban")

        # Verifica renderizado del selector de tipo_licencia por renglón
        self.assertContains(response, 'name="tipo_licencia"')
        self.assertContains(response, self.lic_il01.codigo)
        self.assertContains(response, self.lic_il02.codigo)

        # Filtro exclusivo por Cuadro IL-01
        res_il01 = self.client.get(
            reverse("licencias:planilla_list") + "?cuadro=IL-01"
        )
        self.assertEqual(res_il01.status_code, 200)
        self.assertContains(res_il01, "045/2026")
        self.assertNotContains(res_il01, "046/2026")

        # Filtro exclusivo por Cuadro IL-02
        res_il02 = self.client.get(
            reverse("licencias:planilla_list") + "?cuadro=IL-02"
        )
        self.assertEqual(res_il02.status_code, 200)
        self.assertContains(res_il02, "046/2026")
        self.assertNotContains(res_il02, "045/2026")

    def test_criterio_modificar_cuadro_preserva_numero_instrumento(self):
        """
        Criterio de Aceptación:
        Modificar el cuadro de un renglón (ej. pasar de IL-01 a IL-02)
        debe mantener intacto su numero_instrumento (Disposición) original.
        """
        self.assertEqual(self.renglon_1.cuadro, "IL-01")
        self.assertEqual(self.renglon_1.numero_instrumento, "045/2026")

        # Se cambia el renglón 1 de IL-01 a la licencia lic_il02 (que pertenece a IL-02)
        url_cambio = reverse(
            "licencias:renglon_cambiar_licencia", args=[self.renglon_1.id]
        )
        post_data = {"tipo_licencia": self.lic_il02.id}
        response = self.client.post(url_cambio, post_data)
        self.assertEqual(response.status_code, 302)

        # Refrescar desde la base de datos
        self.renglon_1.refresh_from_db()

        # El cuadro debe haber cambiado a IL-02
        self.assertEqual(self.renglon_1.cuadro, "IL-02")
        self.assertEqual(self.renglon_1.tipo_licencia, self.lic_il02)

        # Aserción obligatoria: numero_instrumento debe ser EXACTAMENTE el original
        self.assertEqual(self.renglon_1.numero_instrumento, "045/2026")
        self.assertEqual(self.renglon_1.modificado_por, self.user)

        # Prueba inversa: cambiar renglón 2 de IL-02 a IL-01
        self.assertEqual(self.renglon_2.cuadro, "IL-02")
        self.assertEqual(self.renglon_2.numero_instrumento, "046/2026")

        res_inv = self.client.post(
            reverse(
                "licencias:renglon_cambiar_licencia",
                args=[self.renglon_2.id],
            ),
            {"tipo_licencia": self.lic_il01.id},
        )
        self.assertEqual(res_inv.status_code, 302)

        self.renglon_2.refresh_from_db()
        self.assertEqual(self.renglon_2.cuadro, "IL-01")
        self.assertEqual(self.renglon_2.tipo_licencia, self.lic_il01)
        self.assertEqual(self.renglon_2.numero_instrumento, "046/2026")

    def test_criterio_descarga_csv_con_encabezados_exactos(self):
        """
        Criterio de Aceptación:
        El archivo CSV se descarga con los encabezados exactos:
        Cuadro, N° Disposición, Docente, DNI, Desde, Hasta, Materias,
        Horas, Tipo Licencia.
        """
        url_csv = reverse("licencias:exportar_planilla_csv")
        response = self.client.get(url_csv)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("Content-Type", ""))
        self.assertIn(
            "attachment;", response.headers.get("Content-Disposition", "")
        )

        contenido = response.content.decode("utf-8")
        reader = csv.reader(io.StringIO(contenido))
        filas = list(reader)

        self.assertGreater(len(filas), 1)

        # Encabezados exactos según la especificación técnica
        encabezados_esperados = [
            "Cuadro",
            "N° Disposición",
            "Docente",
            "DNI",
            "Desde",
            "Hasta",
            "Materias",
            "Horas",
            "Tipo Licencia",
        ]
        self.assertEqual(filas[0], encabezados_esperados)

        # Verificación de datos exportados en las filas
        todos_dni = [fila[3] for fila in filas[1:]]
        self.assertIn(self.docente.dni, todos_dni)

        disposiciones = [fila[1] for fila in filas[1:]]
        self.assertIn("045/2026", disposiciones)
        self.assertIn("046/2026", disposiciones)

    def test_exportacion_csv_via_parametro_get_en_planilla_list(self):
        """
        Valida que solicitar ?export=csv en la vista de lista también
        descargue el CSV con los encabezados exactos.
        """
        url = reverse("licencias:planilla_list") + "?export=csv"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("Content-Type", ""))

        reader = csv.reader(io.StringIO(response.content.decode("utf-8")))
        encabezados = next(reader)
        self.assertEqual(
            encabezados,
            [
                "Cuadro",
                "N° Disposición",
                "Docente",
                "DNI",
                "Desde",
                "Hasta",
                "Materias",
                "Horas",
                "Tipo Licencia",
            ],
        )
