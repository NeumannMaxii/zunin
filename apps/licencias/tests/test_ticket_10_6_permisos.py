"""
Pruebas para el Ticket 10.6:
Blindaje de Permisos Backend y Rechazo 403 Estricto en Licencias y Planillas.
Criterio de Aceptación:
- Un usuario Consulta_Directiva recibe error 403 al enviar POST a los endpoints
  de asistencia y licencias (CambiarLicenciaRenglonView y
  ActualizarInstrumentoRenglonView).
- Bedelia_Operadoras y Admin_Institucional acceden exitosamente.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.personal.models import CargoDocente, Docente, EspacioCurricular

User = get_user_model()


class Ticket10_6LicenciasPermisosTests(TestCase):
    """
    Validación de permisos backend en las vistas de modificación de planillas
    mensuales (CambiarLicenciaRenglonView y ActualizarInstrumentoRenglonView).
    """

    def setUp(self):
        # Grupos de seguridad
        self.grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.grupo_consulta, _ = Group.objects.get_or_create(name="Consulta_Directiva")

        # Usuarios
        self.user_consulta = User.objects.create_user(
            username="consulta_lic", password="password123"
        )
        self.user_consulta.groups.add(self.grupo_consulta)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_lic", password="password123"
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_admin = User.objects.create_user(
            username="admin_lic", password="password123"
        )
        self.user_admin.groups.add(self.grupo_admin)

        # Datos base
        self.docente = Docente.objects.create(
            dni="28444555",
            apellido="RAMÍREZ",
            nombre="Estela",
            sexo="F",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="MAT-01",
            nombre="Matemática",
            carrera="Profesorado",
            anio=1,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
        )
        self.lic_a = TipoLicencia.objects.create(
            codigo="340-A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.lic_b = TipoLicencia.objects.create(
            codigo="341",
            articulo="341",
            descripcion="Maternidad",
            cuadro_mensual="IL-02",
            activo=True,
        )
        self.renglon = RenglonPlanillaMensual.objects.create(
            anio=2026,
            mes=10,
            docente=self.docente,
            cargo=self.cargo,
            cuadro="IL-01",
            tipo_licencia=self.lic_a,
            desde=datetime.date(2026, 10, 5),
            hasta=datetime.date(2026, 10, 7),
            horas_afectadas=12,
            numero_instrumento="055/2026",
            tipo_instrumento="DISPOSICION",
            desactualizada=False,
        )

    def test_criterio_consulta_directiva_recibe_403_post_cambiar_licencia(self):
        """
        Criterio de Aceptación:
        Un usuario Consulta_Directiva recibe error 403 al enviar POST a
        CambiarLicenciaRenglonView.
        """
        self.client.login(username="consulta_lic", password="password123")
        url = reverse(
            "licencias:renglon_cambiar_licencia",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(url, {"tipo_licencia": self.lic_b.id})
        self.assertEqual(
            response.status_code,
            403,
            "Consulta_Directiva debe recibir HTTP 403 Forbidden al modificar renglón.",
        )

    def test_criterio_consulta_directiva_recibe_403_post_actualizar_instrumento(
        self,
    ):
        """
        Criterio de Aceptación:
        Un usuario Consulta_Directiva recibe error 403 al enviar POST a
        ActualizarInstrumentoRenglonView.
        """
        self.client.login(username="consulta_lic", password="password123")
        url = reverse(
            "licencias:renglon_actualizar_instrumento",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(
            url,
            {
                "tipo_instrumento": "RESOLUCION",
                "numero_instrumento": "Res. 999/2026",
            },
        )
        self.assertEqual(
            response.status_code,
            403,
            (
                "Consulta_Directiva debe recibir HTTP 403 Forbidden "
                "al conmutar instrumento."
            ),
        )

    def test_bedelia_operadoras_puede_post_cambiar_licencia(self):
        """
        Valida que Bedelia_Operadoras pueda modificar el tipo de licencia exitosamente.
        """
        self.client.login(username="bedelia_lic", password="password123")
        url = reverse(
            "licencias:renglon_cambiar_licencia",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(url, {"tipo_licencia": self.lic_b.id}, follow=False)
        self.assertEqual(response.status_code, 302)

        self.renglon.refresh_from_db()
        self.assertEqual(self.renglon.tipo_licencia, self.lic_b)
        self.assertEqual(self.renglon.cuadro, "IL-02")

    def test_admin_institucional_puede_post_actualizar_instrumento(self):
        """
        Valida que Admin_Institucional pueda conmutar el instrumento a Resolución.
        """
        self.client.login(username="admin_lic", password="password123")
        url = reverse(
            "licencias:renglon_actualizar_instrumento",
            kwargs={"pk": self.renglon.pk},
        )
        response = self.client.post(
            url,
            {
                "tipo_instrumento": "RESOLUCION",
                "numero_instrumento": "Res. 555/2026",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        self.renglon.refresh_from_db()
        self.assertEqual(self.renglon.tipo_instrumento, "RESOLUCION")
        self.assertEqual(self.renglon.numero_instrumento, "Res. 555/2026")
