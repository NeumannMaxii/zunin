"""
Test End-to-End (E2E) con simulación temporal mediante freezegun (Ticket 14).
Cubre el ciclo completo anual de Bedelía:
1. Login institucional (operadora de Bedelía).
2. Registro de asistencia diaria con inasistencia en Diciembre 2026.
3. Justificación diferida con Licencia Estatutaria (RN-03).
4. Generación de Planilla Mensual consolidada de Diciembre 2026.
5. Viaje en el tiempo a Enero 2027 (freezegun).
6. Validación del reinicio de correlativo anual a '001/2027' (Cross-year reset).
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from freezegun import freeze_time
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import generar_planilla_mes
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class Ticket14E2ETiempoTests(TestCase):
    """
    Suite E2E de simulación temporal para la defensa final del sistema Zunin.
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()

        # Configurar grupo Bedelia_Operadoras
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )

        # Crear operadora de Bedelía
        self.user = User.objects.create_user(
            username="zaquino_e2e",
            password="Password123!",
            email="zaquino@iesetyfp.edu.ar",
            first_name="Zulma",
            last_name="Aquino",
            is_staff=True,
        )
        self.user.groups.add(self.grupo_bedelia)

        # Estructura académica: Carrera, Espacio Curricular y Cargo Catálogo
        self.carrera = Carrera.objects.create(
            codigo="TSDS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="P-II",
            nombre="Programación II",
            carrera=self.carrera,
            anio=2,
        )
        self.catalogo = CargoCatalogo.objects.create(
            codigo="PROF-P2",
            descripcion="Profesor de Programación II",
            activo=True,
        )

        # Docente y Cargo Docente activo y vigente durante 2026 y 2027
        self.docente = Docente.objects.create(
            dni="29111222",
            apellido="Gomez",
            nombre="Elena",
            sexo="F",
            activo=True,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            cargo_catalogo=self.catalogo,
            situacion_revista="TIT",
            fecha_alta=datetime.date(2026, 1, 1),
            fecha_baja=None,
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            activo=True,
        )

        # Catálogo de Licencias Estatutarias (IL-01)
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            activo=True,
        )

    def test_e2e_flujo_completo_con_viaje_temporal_reinicio_correlativo(self):
        """
        Test único integral E2E:
        Login -> Cargar asistencia -> Justificar -> Generar Planilla Diciembre ->
        Viajar en el tiempo a Enero -> Validar reinicio a 001/2027.
        """
        # =====================================================================
        # PASO 1: Inicio en Diciembre 2026 (Lunes 14 de Diciembre de 2026)
        # =====================================================================
        with freeze_time("2026-12-14 08:30:00") as frozen_time:
            # 1.1 Login institucional de la operadora de Bedelía
            login_url = reverse("login")
            login_resp = self.client.post(
                login_url,
                {"username": "zaquino_e2e", "password": "Password123!"},
                follow=True,
            )
            self.assertEqual(login_resp.status_code, 200)
            self.assertTrue(
                login_resp.context["user"].is_authenticated,
                "La operadora de Bedelía debe quedar autenticada tras el login.",
            )

            # 1.2 Cargar asistencia diaria: Registrar inasistencia (marca 'I')
            fecha_dic = "2026-12-14"
            carga_url = reverse("asistencia:asistencia_diaria")
            carga_data = {
                "fecha": fecha_dic,
                f"estado_{self.cargo.id}": "AUSENTE",
                f"marca_{self.cargo.id}": "I",
                f"observacion_{self.cargo.id}": "No concurrió a clase",
            }
            carga_resp = self.client.post(carga_url, carga_data, follow=True)
            self.assertEqual(carga_resp.status_code, 200)

            # Validar que el registro de asistencia fue persistido
            reg_dic = RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=datetime.date(2026, 12, 14)
            ).first()
            self.assertIsNotNone(
                reg_dic, "Debe existir el registro de inasistencia en BD."
            )
            self.assertEqual(reg_dic.estado, "AUSENTE")
            self.assertEqual(reg_dic.marca_diaria, "I")

            # 1.3 Justificación diferida con Licencia médica (340-A)
            justif_url = reverse("licencias:justificacion_diferida")
            justif_data = {
                "docente": self.docente.id,
                "fecha_desde": fecha_dic,
                "fecha_hasta": fecha_dic,
                "nueva_marca": "LIC",
                "tipo_licencia": self.tipo_lic.id,
                "tipo_instrumento": "DISPOSICION",
                "numero_disposicion": "085/2026",
                "observaciones": "Certificado médico de 24hs presentado",
            }
            justif_resp = self.client.post(justif_url, justif_data, follow=True)
            self.assertEqual(justif_resp.status_code, 200)

            reg_dic.refresh_from_db()
            self.assertEqual(reg_dic.estado, "LICENCIA")
            self.assertEqual(reg_dic.marca_diaria, "LIC")
            self.assertEqual(reg_dic.tipo_licencia, self.tipo_lic)

            # 1.4 Generar Planilla Mensual Consolidada de Diciembre 2026
            planillas_dic = generar_planilla_mes(
                mes=12, anio=2026, usuario=self.user
            )
            self.assertTrue(
                len(planillas_dic) > 0,
                "Debe generarse al menos un renglón mensual para Diciembre 2026.",
            )

            renglon_dic = planillas_dic[0]
            self.assertEqual(renglon_dic.mes, 12)
            self.assertEqual(renglon_dic.anio, 2026)
            self.assertTrue(
                renglon_dic.numero_instrumento.endswith("/2026"),
                f"El correlativo de 2026 debe terminar en /2026, obtenido: "
                f"{renglon_dic.numero_instrumento}",
            )

            # Validar visualización en pantalla mensual
            list_url = reverse("licencias:planilla_list") + "?mes=12&anio=2026"
            resp_list_dic = self.client.get(list_url)
            self.assertEqual(resp_list_dic.status_code, 200)
            self.assertContains(resp_list_dic, renglon_dic.numero_instrumento)

            # =================================================================
            # PASO 2: Viajar en el tiempo a Enero 2027 (Lunes 18 de Enero 2027)
            # =================================================================
            frozen_time.move_to("2027-01-18 09:00:00")

            # Al regresar tras el receso en Enero, la operadora inicia sesión
            # en el nuevo año calendario
            self.client.post(
                login_url,
                {"username": "zaquino_e2e", "password": "Password123!"},
                follow=True,
            )

            fecha_ene = "2027-01-18"
            # 2.1 Carga de asistencia de Enero 2027
            carga_data_ene = {
                "fecha": fecha_ene,
                f"estado_{self.cargo.id}": "AUSENTE",
                f"marca_{self.cargo.id}": "I",
                f"observacion_{self.cargo.id}": "Reposo médico inicio 2027",
            }
            carga_resp_ene = self.client.post(
                carga_url, carga_data_ene, follow=True
            )
            self.assertEqual(carga_resp_ene.status_code, 200)

            reg_ene = RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=datetime.date(2027, 1, 18)
            ).first()
            self.assertIsNotNone(reg_ene)

            # 2.2 Justificar inasistencia en Enero 2027
            justif_data_ene = {
                "docente": self.docente.id,
                "fecha_desde": fecha_ene,
                "fecha_hasta": fecha_ene,
                "nueva_marca": "LIC",
                "tipo_licencia": self.tipo_lic.id,
                "tipo_instrumento": "DISPOSICION",
                "numero_disposicion": "",  # Correlativo automático del motor
                "observaciones": "Certificado de inicio de ciclo",
            }
            justif_resp_ene = self.client.post(
                justif_url, justif_data_ene, follow=True
            )
            self.assertEqual(justif_resp_ene.status_code, 200)

            # 2.3 Generar Planilla Mensual de Enero 2027
            planillas_ene = generar_planilla_mes(
                mes=1, anio=2027, usuario=self.user
            )
            self.assertTrue(
                len(planillas_ene) > 0,
                "Debe generarse el renglón mensual para Enero 2027.",
            )

            renglon_ene = planillas_ene[0]
            self.assertEqual(renglon_ene.mes, 1)
            self.assertEqual(renglon_ene.anio, 2027)

            # =================================================================
            # PASO 3: Validación Crítica de Reinicio de Correlativo (001/2027)
            # =================================================================
            self.assertEqual(
                renglon_ene.numero_instrumento,
                "001/2027",
                "RN-04 / Ticket 14: Al cambiar de año calendario, el número "
                "correlativo de disposición institucional debe reiniciarse "
                "estrictamente a '001/YYYY' ('001/2027').",
            )

            total_2027 = RenglonPlanillaMensual.objects.filter(
                anio=2027
            ).count()
            self.assertEqual(total_2027, 1)

            # 3.2 Verificar que el renglón previo de Diciembre 2026 no fue
            # alterado ni contaminado con el nuevo año
            renglon_dic.refresh_from_db()
            self.assertEqual(renglon_dic.anio, 2026)
            self.assertTrue(renglon_dic.numero_instrumento.endswith("/2026"))

            # 3.3 Validar que la interfaz web de planillas refleja '001/2027'
            list_url_ene = reverse("licencias:planilla_list") + "?mes=1&anio=2027"
            resp_list_ene = self.client.get(list_url_ene)
            self.assertEqual(resp_list_ene.status_code, 200)
            self.assertContains(resp_list_ene, "001/2027")
            self.assertContains(resp_list_ene, "Gomez, Elena")
