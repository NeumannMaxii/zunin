"""
Pruebas automatizadas para el Ticket 18.3:
Automatización Multimateria en Justificación Diferida por Rango.

Valida:
1. Desglose automático por materia según la distribución semanal de horas cuando
   no se especifica cargo (cargo=None).
2. Creación de registros de asistencia independientes para cada materia en su
   respectivo día con horas cátedra.
3. Consolidación mensual (generar_planilla_mes): genera ambos renglones
   desglosados por materia con sus horas exactas compartiendo el mismo número
   correlativo de disposición.
4. Contingencia de asignación a first_cargo en días hábiles sin horas configuradas.
5. Formulario JustificacionDiferidaForm y template con badge informativo.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.forms import JustificacionDiferidaForm
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import (
    generar_planilla_mes,
    procesar_justificacion_rango,
)
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class JustificacionMultimateriaTicket18_3Tests(TestCase):
    """Pruebas unitarias para la automatización multimateria en justificación."""

    def setUp(self):
        User = get_user_model()
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.usuario = User.objects.create_user(
            username="bedel_multimateria",
            password="password123",
            is_staff=True,
        )
        self.usuario.groups.add(grupo_bedelia)

        # 1. Crear docente
        self.docente = Docente.objects.create(
            dni="30999888",
            apellido="MONTIEL",
            nombre="Roberto Carlos",
            sexo="M",
            activo=True,
        )

        # 2. Espacios curriculares
        self.espacio_a = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática Aplicada",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.espacio_b = EspacioCurricular.objects.create(
            codigo="PROG-102",
            nombre="Programación I",
            carrera="Desarrollo de Software",
            anio=1,
        )

        # 3. Dos cargos con distribución en días distintos:
        # Cargo A: 3 hs los Jueves
        self.cargo_a = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio_a,
            situacion_revista="TIT",
            horas_jueves=3,
            activo=True,
        )

        # Cargo B: 4 hs los Viernes
        self.cargo_b = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio_b,
            situacion_revista="INT",
            horas_viernes=4,
            activo=True,
        )

        # 4. Tipo de licencia para la prueba
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            cuadro_mensual="IL-01",
            activo=True,
        )

    def test_justificacion_rango_multimateria_automatica(self):
        """
        Criterio de Aceptación Principal (Ticket 18.3):
        - Docente con Cargo A (3 hs Jueves) y Cargo B (4 hs Viernes).
        - Justificar de Jueves a Viernes sin especificar cargo (cargo=None).
        - Verifica que se creen 2 RegistroAsistencia: uno para Cargo A (jueves)
          y otro para Cargo B (viernes).
        - Invocar generar_planilla_mes() y validar que contenga ambos renglones
          desglosados (3 hs y 4 hs) compartiendo el mismo número de disposición.
        """
        # Jueves 15 de Octubre de 2026 y Viernes 16 de Octubre de 2026
        jueves = datetime.date(2026, 10, 15)
        viernes = datetime.date(2026, 10, 16)
        self.assertEqual(jueves.weekday(), 3)  # Jueves
        self.assertEqual(viernes.weekday(), 4)  # Viernes

        # Ejecutar sin especificar cargo
        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=jueves,
            fecha_hasta=viernes,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            cargo=None,
            usuario=self.usuario,
        )

        # Debe generar 2 registros en la BD
        self.assertEqual(len(registros), 2)
        asistencias_qs = RegistroAsistencia.objects.filter(docente=self.docente)
        self.assertEqual(asistencias_qs.count(), 2)

        # Registro 1: Jueves con Cargo A
        reg_jueves = asistencias_qs.get(fecha=jueves)
        self.assertEqual(reg_jueves.cargo, self.cargo_a)
        self.assertEqual(reg_jueves.marca_diaria, "LIC")
        self.assertEqual(reg_jueves.estado, "LICENCIA")
        self.assertEqual(reg_jueves.tipo_licencia, self.tipo_lic)

        # Registro 2: Viernes con Cargo B
        reg_viernes = asistencias_qs.get(fecha=viernes)
        self.assertEqual(reg_viernes.cargo, self.cargo_b)
        self.assertEqual(reg_viernes.marca_diaria, "LIC")
        self.assertEqual(reg_viernes.estado, "LICENCIA")
        self.assertEqual(reg_viernes.tipo_licencia, self.tipo_lic)

        # Consolidar la planilla mensual de Octubre 2026
        renglones = generar_planilla_mes(mes=10, anio=2026, usuario=self.usuario)
        self.assertEqual(len(renglones), 2)

        renglones_docente = RenglonPlanillaMensual.objects.filter(
            docente=self.docente, mes=10, anio=2026
        ).order_by("cargo__materia__codigo")
        self.assertEqual(renglones_docente.count(), 2)

        renglon_a = renglones_docente.get(cargo=self.cargo_a)
        renglon_b = renglones_docente.get(cargo=self.cargo_b)

        # Horas exactas desglosadas por materia
        self.assertEqual(renglon_a.horas_afectadas, 3)
        self.assertEqual(renglon_b.horas_afectadas, 4)

        # Ambos renglones deben compartir el mismo número de disposición correlativo
        self.assertTrue(bool(renglon_a.numero_instrumento))
        self.assertEqual(renglon_a.numero_instrumento, renglon_b.numero_instrumento)

    def test_justificacion_con_cargo_especifico_solo_afecta_a_ese_cargo(self):
        """
        Si la bedel selecciona voluntariamente un cargo específico,
        la justificación solo debe aplicarse a ese cargo.
        """
        jueves = datetime.date(2026, 10, 15)
        viernes = datetime.date(2026, 10, 16)

        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=jueves,
            fecha_hasta=viernes,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            cargo=self.cargo_a,
            usuario=self.usuario,
        )

        # Cargo A solo tiene clases el jueves
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].cargo, self.cargo_a)
        self.assertEqual(registros[0].fecha, jueves)

    def test_contingencia_primer_cargo_en_dia_habil_sin_horas(self):
        """
        Si un docente tiene cargos pero ninguno tiene horas en ese día hábil
        y se justifica dicho día, el sistema asigna el primer cargo activo
        como contingencia.
        """
        # Miércoles 14 de Octubre de 2026 (día hábil donde ni Cargo A ni B
        # tienen horas fijadas)
        miercoles = datetime.date(2026, 10, 14)
        self.assertEqual(miercoles.weekday(), 2)

        # Docente con cargo sin horas semanales configuradas
        docente_sin_horas = Docente.objects.create(
            dni="40111222",
            apellido="GOMEZ",
            nombre="Laura",
            activo=True,
        )
        cargo_activo = CargoDocente.objects.create(
            docente=docente_sin_horas,
            situacion_revista="TIT",
            activo=True,
        )

        registros = procesar_justificacion_rango(
            docente=docente_sin_horas,
            fecha_desde=miercoles,
            fecha_hasta=miercoles,
            nueva_marca="P",
            tipo_licencia=None,
            cargo=None,
            usuario=self.usuario,
        )

        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].cargo, cargo_activo)
        self.assertEqual(registros[0].fecha, miercoles)
        self.assertEqual(registros[0].marca_diaria, "P")

    def test_help_text_cargo_en_formulario_justificacion(self):
        """
        Verifica que JustificacionDiferidaForm mantenga cargo opcional
        y tenga el help_text descriptivo de la automatización multimateria.
        """
        form = JustificacionDiferidaForm()
        self.assertFalse(form.fields["cargo"].required)
        self.assertIn(
            "Dejar en blanco para aplicar automáticamente a todas las materias",
            form.fields["cargo"].help_text,
        )

    def test_badge_multimateria_en_template_justificacion_diferida(self):
        """
        Verifica que el template justificacion_diferida.html incluya el badge
        informativo sobre el desglose multimateria automático.
        """
        self.client.force_login(self.usuario)
        url = reverse("licencias:justificacion_diferida")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Desglose Multimateria Automático")
        self.assertContains(
            response,
            "Al dejar el cargo en blanco, el sistema desglosa automáticamente",
        )

    def test_justificacion_multimateria_via_form_post(self):
        """
        Envío del formulario POST desde la vista sin especificar cargo.
        Debe procesar la justificación multimateria y redirigir con éxito.
        """
        self.client.force_login(self.usuario)
        jueves = datetime.date(2026, 10, 15)
        viernes = datetime.date(2026, 10, 16)
        data = {
            "docente": self.docente.pk,
            "fecha_desde": jueves.strftime("%Y-%m-%d"),
            "fecha_hasta": viernes.strftime("%Y-%m-%d"),
            "cargo": "",  # Vacío para automatización multimateria
            "nueva_marca": "LIC",
            "tipo_licencia": self.tipo_lic.pk,
            "tipo_instrumento": "DISPOSICION",
            "numero_disposicion": "Disp. 150/2026",
            "observaciones": "Justificación médica multimateria",
        }
        url = reverse("licencias:justificacion_diferida")
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)

        asistencias = RegistroAsistencia.objects.filter(docente=self.docente)
        self.assertEqual(asistencias.count(), 2)
        self.assertEqual(asistencias.get(fecha=jueves).cargo, self.cargo_a)
        self.assertEqual(asistencias.get(fecha=viernes).cargo, self.cargo_b)

    def test_regla_rn03_regenera_planilla_desactualizada(self):
        """
        RN-03: Si el mes ya contaba con renglones de planilla mensual generados,
        la justificación multimateria debe marcar la planilla previa como
        desactualizada y regenerar automáticamente los nuevos renglones.
        """
        jueves = datetime.date(2026, 10, 15)
        viernes = datetime.date(2026, 10, 16)

        # Planilla preexistente para el docente
        renglon_previo = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo_a,
            tipo_licencia=self.tipo_lic,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=jueves,
            hasta=jueves,
            horas_afectadas=3,
            marca_origen="I",
            numero_instrumento="001/2026",
            desactualizada=False,
        )

        # Ejecutar justificación diferida que abarca jueves y viernes
        procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=jueves,
            fecha_hasta=viernes,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            cargo=None,
            usuario=self.usuario,
        )

        renglon_previo.refresh_from_db()
        self.assertTrue(renglon_previo.desactualizada)

        # Renglones vigentes actualizados
        renglones_vigentes = RenglonPlanillaMensual.objects.vigentes().filter(
            docente=self.docente, mes=10, anio=2026
        )
        self.assertEqual(renglones_vigentes.count(), 2)
