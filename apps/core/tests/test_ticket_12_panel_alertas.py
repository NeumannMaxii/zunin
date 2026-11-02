"""
Pruebas automatizadas para el Ticket 12: Consultas y Panel de Alertas (RF-18).

Especificación Técnica:
- Cálculo de Alertas: Fórmula (Faltas 'I' / Límite Legal) * 100
  (límite fijo de 15 días).
- Optimización: annotate(Count(..., filter=Q(marca='I'))) con ExpressionWrapper
  sin iterar en memoria.
- Umbrales Visuales:
  - Supera 70% -> Alerta naranja (Precaución).
  - Supera 100% -> Alerta roja (Crítico).

Criterios de Aceptación:
- Un test verifica que un docente con 11 faltas sobre un límite de 15 dispara
  el umbral del 73% (Precaución).
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.asistencia.models import RegistroAsistencia
from apps.core.services import obtener_panel_alertas_docentes
from apps.personal.models import Docente

User = get_user_model()


class Ticket12PanelAlertasTests(TestCase):
    """
    Suite de pruebas para el Ticket 12:
    RF-18: Panel de Alertas Preventivas de Inasistencias.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="bedelia_alertas",
            password="password123",
            is_staff=True,
        )

        # Crear docente para pruebas
        self.docente = Docente.objects.create(
            dni="32999888",
            apellido="ALVAREZ",
            nombre="Roberto",
            sexo="M",
            activo=True,
        )

    def test_criterio_aceptacion_docente_con_11_faltas_dispara_umbral_73_porciento(
        self,
    ):
        """
        Criterio de Aceptación:
        Un test verifica que un docente con 11 faltas sobre un límite de 15
        dispara el umbral del 73% (Precaución).
        Fórmula: (11 / 15) * 100 = 73.333... % -> 73%
        """
        limite_legal = 15
        anio_actual = datetime.date.today().year

        # Cargar 11 inasistencias con marca 'I'
        for dia in range(1, 12):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                fecha=datetime.date(anio_actual, 3, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )

        # Ejecutar la consulta optimizada de alertas
        alertas = obtener_panel_alertas_docentes(
            limite_legal=limite_legal, anio=anio_actual
        )
        docente_anotado = alertas.get(pk=self.docente.pk)

        # Verificaciones del cálculo
        self.assertEqual(docente_anotado.faltas_count, 11)
        self.assertAlmostEqual(docente_anotado.porcentaje, 73.33333333333333, places=2)
        self.assertEqual(round(docente_anotado.porcentaje), 73)
        self.assertEqual(
            docente_anotado.nivel_alerta,
            "PRECAUCION",
            "Un docente con 11 faltas sobre 15 debe estar en estado PRECAUCION.",
        )

    def test_docente_con_mas_de_100_porciento_dispara_alerta_roja_critico(self):
        """
        Verifica que si el porcentaje supera el 100% (ej: 16 faltas sobre límite de 15)
        se categorice con alerta roja (CRITICO).
        Fórmula: (16 / 15) * 100 = 106.666... % > 100%
        """
        limite_legal = 15
        anio_actual = datetime.date.today().year

        for dia in range(1, 17):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                fecha=datetime.date(anio_actual, 4, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )

        alertas = obtener_panel_alertas_docentes(
            limite_legal=limite_legal, anio=anio_actual
        )
        docente_anotado = alertas.get(pk=self.docente.pk)

        self.assertEqual(docente_anotado.faltas_count, 16)
        self.assertGreater(docente_anotado.porcentaje, 100.0)
        self.assertEqual(
            docente_anotado.nivel_alerta,
            "CRITICO",
            "Superar el 100% de inasistencias debe catalogarse como alerta CRITICO.",
        )

    def test_docente_con_menos_del_70_porciento_permanece_en_estado_normal(self):
        """
        Verifica que un docente con inasistencias por debajo del 70%
        (ej: 8 faltas sobre 15 = 53.33%) permanezca en nivel NORMAL.
        """
        limite_legal = 15
        anio_actual = datetime.date.today().year

        for dia in range(1, 9):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                fecha=datetime.date(anio_actual, 5, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )

        alertas = obtener_panel_alertas_docentes(
            limite_legal=limite_legal, anio=anio_actual
        )
        docente_anotado = alertas.get(pk=self.docente.pk)

        self.assertEqual(docente_anotado.faltas_count, 8)
        self.assertLess(docente_anotado.porcentaje, 70.0)
        self.assertEqual(docente_anotado.nivel_alerta, "NORMAL")

    def test_dashboard_renderiza_panel_de_alertas_con_docente_en_precaucion(
        self,
    ):
        """
        Valida que el Dashboard principal renderice el panel de alertas y
        muestre la alerta naranja (Precaución) y el 73.3% para el docente evaluado.
        """
        anio_actual = datetime.date.today().year

        # 11 faltas sobre 15
        for dia in range(1, 12):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                fecha=datetime.date(anio_actual, 3, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )

        self.client.login(username="bedelia_alertas", password="password123")
        response = self.client.get(reverse("core:dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel de Alertas Preventivas")
        self.assertContains(response, "ALVAREZ, Roberto")
        content = response.content.decode("utf-8")
        self.assertTrue(
            "73,3%" in content or "73.3%" in content or "73%" in content,
            "El porcentaje de 73.3% debe renderizarse en el panel de alertas.",
        )
        self.assertContains(response, "Alerta Naranja (Precaución)")
        self.assertContains(response, "Precaución: 1")
