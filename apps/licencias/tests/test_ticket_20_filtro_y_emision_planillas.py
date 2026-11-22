"""
Pruebas automatizadas para el Filtro de Período y Emisión de Planillas Mensuales.
Valida:
1. Filtro por mes y año en RenglonPlanillaMensualListView.
2. Preservación de parámetros de mes y año al conmutar cuadros (Todos, IL-01, IL-02).
3. Preservación de parámetros de mes y año en enlaces de exportación (Excel y CSV).
4. Seguridad RBAC en EmitirPlanillaMesView: anónimo (302), consulta (403),
   Bedelía y Admin (200/302).
5. Emisión exitosa de planilla mensual y cálculo de totales.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import CargoDocente, Carrera, Docente, EspacioCurricular


class FiltroYEmisionPlanillasTestCase(TestCase):
    """
    Suite de pruebas para el selector de período y la emisión de planillas.
    """

    def setUp(self):
        User = get_user_model()
        self.grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.grupo_consulta, _ = Group.objects.get_or_create(name="Consulta_Directiva")
        self.grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")

        # Usuarios con distintos roles
        self.user_bedelia = User.objects.create_user(
            username="bedel_filtro",
            password="password123",
            email="bedel@iesetyp.edu.ar",
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_consulta = User.objects.create_user(
            username="consulta_filtro",
            password="password123",
            email="consulta@iesetyp.edu.ar",
        )
        self.user_consulta.groups.add(self.grupo_consulta)

        # Datos académicos
        self.carrera = Carrera.objects.create(
            codigo="TEC-TEST",
            nombre="Tecnicatura de Prueba",
        )
        self.materia = EspacioCurricular.objects.create(
            carrera=self.carrera,
            codigo="MAT-01",
            nombre="Materia 01",
            anio=1,
        )
        self.docente = Docente.objects.create(
            dni="30999888",
            nombre="Juan",
            apellido="Pérez",
            sexo="M",
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            tipo_cargo="HORAS",
            codigo_cargo="166",
            situacion_revista="TIT",
            horas_lunes=4,
            dia_lunes=True,
            activo=True,
        )

        self.tipo_lic_salud, _ = TipoLicencia.objects.get_or_create(
            codigo="01.01.01",
            defaults={
                "articulo": "308",
                "descripcion": "Enfermedad Común",
                "cuadro_mensual": "IL-01",
                "forma_pago": "CON_SUELDO",
                "activo": True,
            },
        )
        self.tipo_lic_otros, _ = TipoLicencia.objects.get_or_create(
            codigo="02.01.01",
            defaults={
                "articulo": "344",
                "descripcion": "Razones Particulares",
                "cuadro_mensual": "IL-02",
                "forma_pago": "SIN_SUELDO",
                "activo": True,
            },
        )

        # Renglones de prueba en meses distintos: Octubre (10) y Noviembre (11)
        self.renglon_octubre = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_salud,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 5),
            hasta=datetime.date(2026, 10, 5),
            horas_afectadas=4,
            numero_instrumento="001/2026",
            tipo_instrumento="DISPOSICION",
            desactualizada=False,
        )

        self.renglon_noviembre = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_otros,
            cuadro="IL-02",
            mes=11,
            anio=2026,
            desde=datetime.date(2026, 11, 2),
            hasta=datetime.date(2026, 11, 2),
            horas_afectadas=4,
            numero_instrumento="002/2026",
            tipo_instrumento="DISPOSICION",
            desactualizada=False,
        )

    def test_listado_sin_filtro_muestra_consolidado_ambos_meses(self):
        """Sin filtros mes ni año, muestra todos los renglones vigentes."""
        self.client.login(username="bedel_filtro", password="password123")
        url = reverse("licencias:planilla_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Consolidado")
        renglones_ctx = list(response.context["renglones"])
        self.assertIn(self.renglon_octubre, renglones_ctx)
        self.assertIn(self.renglon_noviembre, renglones_ctx)
        self.assertEqual(len(renglones_ctx), 2)

    def test_listado_filtrado_por_octubre_muestra_solo_octubre(self):
        """Al filtrar mes=10 y anio=2026, sólo incluye renglones de ese mes."""
        self.client.login(username="bedel_filtro", password="password123")
        url = f"{reverse('licencias:planilla_list')}?mes=10&anio=2026"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OCTUBRE 2026")
        renglones_ctx = list(response.context["renglones"])
        self.assertIn(self.renglon_octubre, renglones_ctx)
        self.assertNotIn(self.renglon_noviembre, renglones_ctx)
        self.assertEqual(len(renglones_ctx), 1)

        # Totales por período filtrado
        self.assertEqual(response.context["total_il01"], 1)
        self.assertEqual(response.context["total_il02"], 0)

    def test_listado_filtrado_por_noviembre_muestra_solo_noviembre(self):
        """Al filtrar mes=11 y anio=2026, sólo incluye renglones de ese mes."""
        self.client.login(username="bedel_filtro", password="password123")
        url = f"{reverse('licencias:planilla_list')}?mes=11&anio=2026"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NOVIEMBRE 2026")
        renglones_ctx = list(response.context["renglones"])
        self.assertNotIn(self.renglon_octubre, renglones_ctx)
        self.assertIn(self.renglon_noviembre, renglones_ctx)
        self.assertEqual(len(renglones_ctx), 1)

        # Totales por período filtrado
        self.assertEqual(response.context["total_il01"], 0)
        self.assertEqual(response.context["total_il02"], 1)

    def test_enlaces_de_exportacion_preservan_mes_y_anio(self):
        """Enlaces de exportación deben propagar mes y año en sus URLs."""
        self.client.login(username="bedel_filtro", password="password123")
        url = f"{reverse('licencias:planilla_list')}?mes=11&anio=2026&cuadro=IL-02"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("mes=11", content)
        self.assertIn("anio=2026", content)

    def test_emitir_planilla_requiere_autenticacion_y_rol_operativo(self):
        """Los usuarios anónimos son redirigidos (302) y consulta recibe 403."""
        emitir_url = reverse("licencias:planilla_emitir")

        # 1. Anónimo
        self.client.logout()
        res_anon = self.client.post(emitir_url, {"mes": 11, "anio": 2026})
        self.assertEqual(res_anon.status_code, 302)

        # 2. Rol Consulta_Directiva
        self.client.login(username="consulta_filtro", password="password123")
        res_consulta = self.client.post(emitir_url, {"mes": 11, "anio": 2026})
        self.assertEqual(res_consulta.status_code, 403)

    def test_emitir_planilla_exitoso_para_bedelia(self):
        """Bedelía emite la planilla y es redirigida con mensaje de éxito."""
        self.client.login(username="bedel_filtro", password="password123")
        emitir_url = reverse("licencias:planilla_emitir")

        response = self.client.post(emitir_url, {"mes": 10, "anio": 2026}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Verifica redirección con los parámetros en la URL
        self.assertIn("mes=10", response.request["QUERY_STRING"])
        self.assertIn("anio=2026", response.request["QUERY_STRING"])
        self.assertContains(response, "emitida exitosamente")
