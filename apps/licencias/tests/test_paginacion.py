"""
Pruebas automatizadas de paginación ágil y componente reutilizable (Ticket 3.8).
Criterio de Aceptación:
Poblar 30 licencias y verificar que page_obj.paginator.num_pages == 2
y que la primera página solo contiene 25 elementos.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.licencias.models import TipoLicencia
from apps.licencias.views import RenglonPlanillaMensualListView, TipoLicenciaListView


class PaginacionLicenciasTests(TestCase):
    """
    Validaciones de paginación ágil (paginate_by = 25) y componente
    core/includes/paginator.html (Ticket 3.8).
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="operador_bedelia",
            password="password123",
        )
        self.client.login(username="operador_bedelia", password="password123")

    def test_tipolicencia_listview_paginate_by_es_25(self):
        """Verifica que TipoLicenciaListView tenga paginate_by = 25."""
        self.assertEqual(TipoLicenciaListView.paginate_by, 25)

    def test_renglon_planilla_listview_paginate_by_es_25(self):
        """Verifica que RenglonPlanillaMensualListView tenga fijado paginate_by = 25."""
        self.assertEqual(RenglonPlanillaMensualListView.paginate_by, 25)

    def test_paginacion_30_licencias_dos_paginas_primera_con_25_elementos(self):
        """
        Criterio de Aceptación Ticket 3.8:
        Poblar 30 licencias y verificar que page_obj.paginator.num_pages == 2
        y que la primera página solo contiene 25 elementos.
        """
        for i in range(1, 31):
            TipoLicencia.objects.create(
                codigo=f"LIC_{i:03d}",
                articulo=f"Art. {300 + i}",
                descripcion=f"Descripción de prueba para licencia {i}",
                categoria="LICENCIA",
                forma_pago="CON_GOCE",
            )

        self.assertEqual(TipoLicencia.objects.count(), 30)

        # Petición a la primera página
        response = self.client.get(reverse("licencias:tipolicencia_list"))
        self.assertEqual(response.status_code, 200)

        page_obj = response.context["page_obj"]

        # Aserciones obligatorias del criterio de aceptación:
        self.assertEqual(page_obj.paginator.num_pages, 2)
        self.assertEqual(len(page_obj.object_list), 25)
        self.assertEqual(page_obj.paginator.count, 30)

        # Verificación de inclusión del componente reutilizable
        self.assertTemplateUsed(response, "core/includes/paginator.html")
        self.assertContains(response, "Mostrando")
        self.assertContains(response, "1")
        self.assertContains(response, "25")
        self.assertContains(response, "30")

        # Petición a la segunda página (?page=2)
        url_p2 = reverse("licencias:tipolicencia_list") + "?page=2"
        response_p2 = self.client.get(url_p2)
        self.assertEqual(response_p2.status_code, 200)

        page_obj_p2 = response_p2.context["page_obj"]
        self.assertEqual(len(page_obj_p2.object_list), 5)
        self.assertEqual(page_obj_p2.number, 2)
        self.assertFalse(page_obj_p2.has_next())
        self.assertTrue(page_obj_p2.has_previous())
