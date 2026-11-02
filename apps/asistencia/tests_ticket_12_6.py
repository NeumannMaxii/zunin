"""
Pruebas para el Ticket 12.6: Módulo de Consulta Avanzada Multicriterio.

Valida:
1. Criterio de Aceptación: Búsquedas simultáneas por rango de fechas y materia
   devuelven el QuerySet exacto.
2. Filtros combinables: fecha_desde, fecha_hasta, dni o apellido, estado/marca
   de asistencia y materia.
3. Compatibilidad de argumentos de materia (nombre, código, ID y objeto modelo).
4. Respuestas HTTP 200 e integración con las vistas RegistroAsistenciaListView
   y ConsultaAsistenciaView.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from apps.asistencia.forms import (
    AsistenciaConsultaForm,
    ConsultaAsistenciaForm,
)
from apps.asistencia.models import RegistroAsistencia
from apps.asistencia.services import (
    consultar_asistencias_multicriterio,
    filtrar_asistencias_multicriterio,
)
from apps.asistencia.views import (
    ConsultaAsistenciaView,
    RegistroAsistenciaListView,
)
from apps.licencias.models import TipoLicencia
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class ConsultaAvanzadaMulticriterioTests(TestCase):
    """Pruebas del módulo de consulta avanzada multicriterio (Ticket 12.6)."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="operador_asistencia",
            password="password123",
        )
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.user.groups.add(grupo_bedelia)
        self.client.login(username="operador_asistencia", password="password123")

        # Docentes
        self.docente1 = Docente.objects.create(
            dni="20111222",
            apellido="Gómez",
            nombre="Carlos",
            sexo="M",
            activo=True,
        )
        self.docente2 = Docente.objects.create(
            dni="30333444",
            apellido="Fernández",
            nombre="María",
            sexo="F",
            activo=True,
        )

        # Materias (Espacios Curriculares)
        self.materia_matematica = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática Discreta",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.materia_fisica = EspacioCurricular.objects.create(
            codigo="FIS-201",
            nombre="Física Aplicada",
            carrera="Desarrollo de Software",
            anio=2,
        )

        # Cargos
        self.cargo_matematica = CargoDocente.objects.create(
            docente=self.docente1,
            materia=self.materia_matematica,
            situacion_revista="TIT",
            activo=True,
            hasta_texto="SIN TERMINO",
            horas_lunes=4,
        )
        self.cargo_fisica = CargoDocente.objects.create(
            docente=self.docente2,
            materia=self.materia_fisica,
            situacion_revista="INT",
            activo=True,
            hasta_texto="SIN TERMINO",
            horas_martes=3,
        )

        # Tipo Licencia para registros con licencia
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-ENF",
            articulo="340",
            descripcion="Licencia Médica",
            categoria="LICENCIA",
            cuadro_mensual="IL-01",
        )

        # Registros de Asistencia de prueba
        # R1: En rango (2026-04-10), Matemática, Docente 1, PRESENTE / PR
        self.asist1 = RegistroAsistencia.objects.create(
            docente=self.docente1,
            cargo=self.cargo_matematica,
            fecha=datetime.date(2026, 4, 10),
            estado="PRESENTE",
            marca_diaria="PR",
            oficina="1452",
            anio_planilla=2026,
            justifica=True,
        )
        # R2: En rango (2026-04-20), Matemática, Docente 1, AUSENTE / I
        self.asist2 = RegistroAsistencia.objects.create(
            docente=self.docente1,
            cargo=self.cargo_matematica,
            fecha=datetime.date(2026, 4, 20),
            estado="AUSENTE",
            marca_diaria="I",
            oficina="1452",
            anio_planilla=2026,
            justifica=False,
        )
        # R3: En rango (2026-04-15), Física, Docente 2, PRESENTE / PR
        self.asist3 = RegistroAsistencia.objects.create(
            docente=self.docente2,
            cargo=self.cargo_fisica,
            fecha=datetime.date(2026, 4, 15),
            estado="PRESENTE",
            marca_diaria="PR",
            oficina="1452",
            anio_planilla=2026,
            justifica=True,
        )
        # R4: Fuera de rango anterior (2026-03-25), Matemática, Docente 1
        self.asist4 = RegistroAsistencia.objects.create(
            docente=self.docente1,
            cargo=self.cargo_matematica,
            fecha=datetime.date(2026, 3, 25),
            estado="PRESENTE",
            marca_diaria="PR",
            oficina="1452",
            anio_planilla=2026,
            justifica=True,
        )
        # R5: Fuera de rango posterior (2026-05-05), Matemática, Docente 1
        self.asist5 = RegistroAsistencia.objects.create(
            docente=self.docente1,
            cargo=self.cargo_matematica,
            fecha=datetime.date(2026, 5, 5),
            estado="PRESENTE",
            marca_diaria="PR",
            oficina="1452",
            anio_planilla=2026,
            justifica=True,
        )
        # R6: En rango (2026-04-12), Sin Cargo, Docente 2, AUSENTE / I
        self.asist6 = RegistroAsistencia.objects.create(
            docente=self.docente2,
            cargo=None,
            fecha=datetime.date(2026, 4, 12),
            estado="AUSENTE",
            marca_diaria="I",
            oficina="1452",
            anio_planilla=2026,
            justifica=False,
        )

    def test_criterio_busquedas_simultaneas_rango_fechas_y_materia(self):
        """
        Criterio de Aceptación:
        Ejecutar búsquedas simultáneas por rango de fechas y materia devuelve
        el QuerySet filtrado exacto.
        """
        # Formulario con rango de abril 2026 y materia "Matemática Discreta"
        form = ConsultaAsistenciaForm(
            data={
                "fecha_desde": "2026-04-01",
                "fecha_hasta": "2026-04-30",
                "materia": "Matemática Discreta",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        qs = form.filtrar()

        # Debe incluir exactamente asist1 y asist2
        self.assertEqual(qs.count(), 2)
        self.assertEqual(set(qs), {self.asist1, self.asist2})

        # Excluye asist3 (otra materia), asist4/5 (fuera rango) y asist6
        self.assertNotIn(self.asist3, qs)
        self.assertNotIn(self.asist4, qs)
        self.assertNotIn(self.asist5, qs)
        self.assertNotIn(self.asist6, qs)

    def test_servicio_filtrar_por_rango_y_materia_objeto_o_id(self):
        """Valida filtrado directo via servicio por instancia o ID de materia."""
        # 1. Por instancia EspacioCurricular
        qs_instancia = filtrar_asistencias_multicriterio(
            fecha_desde=datetime.date(2026, 4, 1),
            fecha_hasta=datetime.date(2026, 4, 30),
            materia=self.materia_matematica,
        )
        self.assertEqual(set(qs_instancia), {self.asist1, self.asist2})

        # 2. Por ID entero de materia
        qs_id = consultar_asistencias_multicriterio(
            fecha_desde="2026-04-01",
            fecha_hasta="2026-04-30",
            materia_id=self.materia_matematica.pk,
        )
        self.assertEqual(set(qs_id), {self.asist1, self.asist2})

        # 3. Por código de materia (ej: FIS-201)
        qs_cod = filtrar_asistencias_multicriterio(
            fecha_desde="2026-04-01",
            fecha_hasta="2026-04-30",
            materia="FIS-201",
        )
        self.assertEqual(set(qs_cod), {self.asist3})

    def test_filtro_combinable_por_dni_o_apellido(self):
        """Valida filtrado por DNI o Apellido del docente."""
        # Búsqueda por DNI parcial o completo
        form_dni = ConsultaAsistenciaForm(data={"dni_o_apellido": "20111222"})
        self.assertTrue(form_dni.is_valid())
        qs_dni = form_dni.filtrar()
        self.assertTrue(all(r.docente == self.docente1 for r in qs_dni))
        self.assertIn(self.asist1, qs_dni)
        self.assertNotIn(self.asist3, qs_dni)

        # Búsqueda por Apellido
        form_ape = ConsultaAsistenciaForm(data={"dni_o_apellido": "Fernández"})
        self.assertTrue(form_ape.is_valid())
        qs_ape = form_ape.filtrar()
        self.assertTrue(all(r.docente == self.docente2 for r in qs_ape))
        self.assertIn(self.asist3, qs_ape)
        self.assertIn(self.asist6, qs_ape)
        self.assertNotIn(self.asist1, qs_ape)

    def test_filtro_combinable_por_estado_y_marca(self):
        """Valida filtrado por estado de asistencia y por marca diaria."""
        # Filtrar solo Ausentes
        form_ausente = ConsultaAsistenciaForm(data={"estado": "AUSENTE"})
        self.assertTrue(form_ausente.is_valid())
        qs_aus = form_ausente.filtrar()
        self.assertEqual(set(qs_aus), {self.asist2, self.asist6})

        # Filtrar solo Presentes
        form_presente = ConsultaAsistenciaForm(data={"estado": "PRESENTE"})
        self.assertTrue(form_presente.is_valid())
        qs_pres = form_presente.filtrar()
        self.assertEqual(
            set(qs_pres), {self.asist1, self.asist3, self.asist4, self.asist5}
        )

        # Filtrar por marca diaria 'I'
        form_marca = ConsultaAsistenciaForm(data={"marca": "I"})
        self.assertTrue(form_marca.is_valid())
        qs_marca = form_marca.filtrar()
        self.assertEqual(set(qs_marca), {self.asist2, self.asist6})

    def test_filtro_combinacion_todas_las_variables(self):
        """Valida combinación estricta de todos los criterios simultáneos."""
        form = ConsultaAsistenciaForm(
            data={
                "fecha_desde": "2026-04-01",
                "fecha_hasta": "2026-04-30",
                "dni_o_apellido": "Gómez",
                "estado": "AUSENTE",
                "materia": "Matemática",
            }
        )
        self.assertTrue(form.is_valid())
        qs = form.filtrar()

        # Solo asist2 cumple simultáneamente: abril 2026 + Gómez + AUSENTE + Matemática
        self.assertEqual(list(qs), [self.asist2])

    def test_formulario_rechaza_rango_fechas_invalido(self):
        """Valida que fecha_hasta < fecha_desde resulte en error de formulario."""
        form = ConsultaAsistenciaForm(
            data={
                "fecha_desde": "2026-04-30",
                "fecha_hasta": "2026-04-01",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_hasta", form.errors)
        self.assertIn(
            "no puede ser anterior a la inicial", form.errors["fecha_hasta"][0]
        )

    def test_vista_asistencia_list_con_filtros_get_retorna_200_y_queryset_exacto(self):
        """Valida que RegistroAsistenciaListView filtre correctamente via GET."""
        url = reverse("asistencia:asistencia_list")
        params = {
            "fecha_desde": "2026-04-01",
            "fecha_hasta": "2026-04-30",
            "materia": "Matemática Discreta",
        }
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        asistencias_ctx = response.context["asistencias"]
        self.assertEqual(set(asistencias_ctx), {self.asist1, self.asist2})
        self.assertTemplateUsed(response, "asistencia/asistencia_list.html")
        self.assertContains(response, "Filtros de Búsqueda Multicriterio")

    def test_vista_consulta_asistencia_ruta_dedicada_retorna_200(self):
        """Valida que la ruta /asistencia/consulta/ resuelva y filtre adecuadamente."""
        url = reverse("asistencia:consulta_asistencia")
        params = {
            "fecha_desde": "2026-04-01",
            "fecha_hasta": "2026-04-30",
            "materia": "Física Aplicada",
        }
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        asistencias_ctx = response.context["asistencias"]
        self.assertEqual(set(asistencias_ctx), {self.asist3})

    def test_paginacion_obligatoria_paginate_by_25(self):
        """Garantiza que paginate_by = 25 se preserve en ambas vistas."""
        self.assertEqual(RegistroAsistenciaListView.paginate_by, 25)
        self.assertEqual(ConsultaAsistenciaView.paginate_by, 25)

    def test_alias_compatibilidad_formulario(self):
        """Verifica que los alias de conveniencia apunten a ConsultaAsistenciaForm."""
        self.assertIs(AsistenciaConsultaForm, ConsultaAsistenciaForm)
