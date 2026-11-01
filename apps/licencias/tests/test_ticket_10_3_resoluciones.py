"""
Pruebas automatizadas para Ticket 10.3: Gestión de Resoluciones Ministeriales Externas.
Valida:
- Conmutación entre Disposición Interna y Resolución Ministerial externa.
- Registro y persistencia del número oficial externo (ej: Res. 1450/2026).
- Exportación CSV reflejando 'Resolución' con su número oficial.
- Formulario de justificación diferida con soporte de resolución ministerial.
- Renderizado de interfaz en planilla mensual (Ticket 9).
"""

import csv
import datetime
import io
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.licencias.forms import JustificacionDiferidaForm
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import generar_planilla_mes
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class Ticket103ResolucionesMinisterialesTests(TestCase):
    """
    Suite de pruebas para validar los requerimientos del Ticket 10.3.
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="operador_ticket103",
            password="password123",
            email="ticket103@iesetyfp.edu.ar",
        )
        self.client.login(username="operador_ticket103", password="password123")

        self.lic_il01 = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            activo=True,
        )

        self.docente = Docente.objects.create(
            dni="28444555",
            apellido="Gomez",
            nombre="Mariana",
            sexo="F",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="MAT-I",
            nombre="Matemática I",
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

        self.renglon = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.lic_il01,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 5),
            hasta=datetime.date(2026, 10, 7),
            horas_afectadas=8,
            tipo_instrumento="DISPOSICION",
            numero_instrumento="042/2026",
            creado_por=self.user,
        )

    def test_conmutar_instrumento_a_resolucion_ministerial(self):
        """
        Verifica que se pueda conmutar el instrumento a RESOLUCION
        con número oficial externo.
        """
        url = reverse(
            "licencias:renglon_actualizar_instrumento",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(
            url,
            {
                "tipo_instrumento": "RESOLUCION",
                "numero_instrumento": "1450/2026 M.E.C.C.y T.",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.renglon.refresh_from_db()
        self.assertEqual(self.renglon.tipo_instrumento, "RESOLUCION")
        self.assertEqual(
            self.renglon.numero_instrumento, "1450/2026 M.E.C.C.y T."
        )
        self.assertEqual(self.renglon.modificado_por, self.user)

    def test_conmutar_instrumento_de_vuelta_a_disposicion_interna(self):
        """
        Verifica que un renglón con resolución pueda conmutarse nuevamente
        a disposición interna.
        """
        self.renglon.tipo_instrumento = "RESOLUCION"
        self.renglon.numero_instrumento = "Res. 888/2026"
        self.renglon.save()

        url = reverse(
            "licencias:renglon_cambiar_licencia",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(
            url,
            {
                "tipo_instrumento": "DISPOSICION",
                "numero_instrumento": "099/2026",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.renglon.refresh_from_db()
        self.assertEqual(self.renglon.tipo_instrumento, "DISPOSICION")
        self.assertEqual(self.renglon.numero_instrumento, "099/2026")

    def test_exportacion_csv_refleja_resolucion_con_numero_oficial(self):
        """
        Verifica que la exportación CSV formatee correctamente la columna
        con 'Resolución <numero>' cuando tipo_instrumento es RESOLUCION.
        """
        # Renglón 1: Disposición Interna
        self.renglon.tipo_instrumento = "DISPOSICION"
        self.renglon.numero_instrumento = "042/2026"
        self.renglon.save()

        # Renglón 2: Resolución Ministerial con número simple
        docente2 = Docente.objects.create(
            dni="30111222",
            apellido="Alvarez",
            nombre="Carlos",
            sexo="M",
            activo=True,
        )
        RenglonPlanillaMensual.objects.create(
            docente=docente2,
            cargo=self.cargo,
            tipo_licencia=self.lic_il01,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 13),
            hasta=datetime.date(2026, 10, 15),
            horas_afectadas=8,
            tipo_instrumento="RESOLUCION",
            numero_instrumento="1450/2026",
            creado_por=self.user,
        )

        # Renglón 3: Resolución Ministerial con prefijo Res.
        docente3 = Docente.objects.create(
            dni="32333444",
            apellido="Britez",
            nombre="Lucia",
            sexo="F",
            activo=True,
        )
        RenglonPlanillaMensual.objects.create(
            docente=docente3,
            cargo=self.cargo,
            tipo_licencia=self.lic_il01,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 20),
            hasta=datetime.date(2026, 10, 22),
            horas_afectadas=8,
            tipo_instrumento="RESOLUCION",
            numero_instrumento="Res. 2026/045 MECCyT",
            creado_por=self.user,
        )

        url = reverse("licencias:exportar_planilla_csv") + "?mes=10&anio=2026"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        header = rows[0]
        self.assertIn("N° Disposición", header)
        col_idx = header.index("N° Disposición")

        data_rows = rows[1:]
        # Renglón con Disposición
        fila_gomez = next(r for r in data_rows if "Gomez" in r[2])
        self.assertEqual(fila_gomez[col_idx], "042/2026")

        # Renglón con Resolución simple -> debe reflejar "Resolución 1450/2026"
        fila_alvarez = next(r for r in data_rows if "Alvarez" in r[2])
        self.assertEqual(fila_alvarez[col_idx], "Resolución 1450/2026")

        # Renglón con prefijo Res. -> debe reflejar "Resolución 2026/045 MECCyT"
        fila_britez = next(r for r in data_rows if "Britez" in r[2])
        self.assertEqual(
            fila_britez[col_idx], "Resolución 2026/045 MECCyT"
        )

    def test_guardar_justificacion_diferida_con_resolucion_ministerial(self):
        """
        Verifica que al guardar justificación diferida indicando RESOLUCION
        y número de resolución, se registre correctamente y al consolidar
        la planilla mensual preserve el instrumento ministerial.
        """
        form_data = {
            "docente": self.docente.pk,
            "fecha_desde": "2026-11-02",
            "fecha_hasta": "2026-11-04",
            "nueva_marca": "LIC",
            "tipo_licencia": self.lic_il01.pk,
            "tipo_instrumento": "RESOLUCION",
            "numero_resolucion": "Res. 1450/2026 M.E.C.C.y T.",
            "observaciones": "Resolución ministerial externa recibida en Bedelía",
        }
        form = JustificacionDiferidaForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        regs = form.save(usuario=self.user)
        self.assertTrue(len(regs) > 0)
        for r in regs:
            self.assertEqual(r.estado, "LICENCIA")
            self.assertIn("1450/2026", r.numero_disposicion)

        # Consolidación mensual
        planillas = generar_planilla_mes(mes=11, anio=2026, usuario=self.user)
        self.assertTrue(len(planillas) > 0)
        r_plan = planillas[0]
        self.assertEqual(r_plan.tipo_instrumento, "RESOLUCION")
        self.assertIn("1450/2026", r_plan.numero_instrumento)

    def test_ui_mensual_renderiza_controles_conmutar_instrumento(self):
        """
        Verifica que la plantilla mensual renderice el selector de conmutación
        y el campo para número oficial.
        """
        url = reverse("licencias:planilla_list") + "?mes=10&anio=2026"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn("Conmutar Instrumento", content)
        self.assertIn('name="tipo_instrumento"', content)
        self.assertIn('name="numero_instrumento"', content)
        self.assertIn("Resolución Ministerial", content)
        self.assertIn("Disposición Interna", content)
