"""
Pruebas automatizadas para el Ticket 7: Justificación Diferida (RN-03).
Valida:
1. Omisión automática de fines de semana y feriados (DiaNoLaborable).
2. Cumplimiento de regla de integridad histórica RN-03 (no borra renglones
   ni altera números de instrumentos existentes).
3. Transaccionalidad atómica (rollback total ante fallo simulado).
4. Permisos de acceso a la vista JustificacionDiferidaView.
"""

import datetime
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.licencias.forms import JustificacionDiferidaForm
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import procesar_justificacion_rango
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class JustificacionDiferidaRN03Tests(TestCase):
    """
    Conjunto de pruebas para la justificación diferida y RN-03.
    """

    def setUp(self):
        User = get_user_model()

        # Grupos de seguridad
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_consulta, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )

        # Permisos
        perms_bedelia = Permission.objects.filter(
            codename__in=[
                "add_registroasistencia",
                "change_registroasistencia",
                "view_registroasistencia",
                "add_renglonplanillamensual",
                "change_renglonplanillamensual",
                "view_renglonplanillamensual",
            ]
        )
        self.grupo_bedelia.permissions.set(perms_bedelia)

        # Usuarios
        self.director = User.objects.create_user(
            username="director_lic",
            password="password123",
            is_staff=True,
        )
        self.director.groups.add(self.grupo_admin)

        self.zaquino = User.objects.create_user(
            username="zaquino_lic",
            password="password123",
            is_staff=True,
        )
        self.zaquino.groups.add(self.grupo_bedelia)

        self.msosa = User.objects.create_user(
            username="msosa_lic",
            password="password123",
            is_staff=True,
        )
        self.msosa.groups.add(self.grupo_consulta)

        # Datos institucionales
        self.docente = Docente.objects.create(
            dni="25111222",
            apellido="GUTIÉRREZ",
            nombre="Marcos Antonio",
            sexo="M",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PROG-3",
            nombre="Programación Avanzada",
            carrera="Software",
            anio=3,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            horas_jueves=4,
            horas_viernes=4,
            activo=True,
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            cuadro_mensual="IL-01",
            activo=True,
        )

    def test_justificar_rango_omite_fines_de_semana_y_feriados(self):
        """
        Validación 1 (Ticket 7):
        Justificar un rango de fechas omite automáticamente los fines de semana
        (sábados y domingos) y los feriados registrados en DiaNoLaborable.
        """
        # Feriado en el medio del rango: Miércoles 07/10/2026
        DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 10, 7),
            descripcion="Feriado Local Institucional",
        )

        # Rango: Lunes 05/10/2026 al Lunes 12/10/2026 (8 días corridos)
        # - Lun 05/10: Hábil -> SÍ
        # - Mar 06/10: Hábil -> SÍ
        # - Mié 07/10: Feriado -> OMITE
        # - Jue 08/10: Hábil -> SÍ
        # - Vie 09/10: Hábil -> SÍ
        # - Sáb 10/10: Fin de semana -> OMITE
        # - Dom 11/10: Fin de semana -> OMITE
        # - Lun 12/10: Hábil -> SÍ
        # Total esperados: 5 días justificados
        fecha_desde = datetime.date(2026, 10, 5)
        fecha_hasta = datetime.date(2026, 10, 12)

        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            numero_disposicion="Disp. 100/2026",
            observaciones="Certificado médico reposo 7 días",
            cargo=self.cargo,
            usuario=self.zaquino,
        )

        self.assertEqual(len(registros), 5)
        self.assertEqual(RegistroAsistencia.objects.count(), 5)

        # Verificar que el feriado no fue registrado
        self.assertFalse(
            RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=datetime.date(2026, 10, 7)
            ).exists()
        )

        # Verificar que los fines de semana no fueron registrados
        self.assertFalse(
            RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=datetime.date(2026, 10, 10)
            ).exists()
        )
        self.assertFalse(
            RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=datetime.date(2026, 10, 11)
            ).exists()
        )

        # Verificar los 5 días hábiles registrados correctamente
        dias_esperados = [
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 6),
            datetime.date(2026, 10, 8),
            datetime.date(2026, 10, 9),
            datetime.date(2026, 10, 12),
        ]
        for dia in dias_esperados:
            reg = RegistroAsistencia.objects.get(
                docente=self.docente, fecha=dia
            )
            self.assertEqual(reg.estado, "LICENCIA")
            self.assertEqual(reg.marca_diaria, "LIC")
            self.assertEqual(reg.tipo_licencia, self.tipo_lic)
            self.assertTrue(reg.justifica)
            self.assertEqual(reg.numero_disposicion, "Disp. 100/2026")
            self.assertEqual(reg.modificado_por, self.zaquino)

    def test_justificar_sobre_mes_con_planilla_ya_generada_no_destruye_historial_rn03(
        self,
    ):
        """
        Validación 2 (Ticket 7 - RN-03):
        Justificar una novedad en un mes que YA tiene planilla mensual generada
        NO destruye los renglones existentes ni altera el número de Disposición
        originalmente asignado.
        """
        # 1. Renglón histórico previo generado en Octubre 2026
        renglon_original = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 2),
            horas_afectadas=8,
            numero_instrumento="001/2026",
            tipo_instrumento="DISPOSICION",
            desactualizada=False,
            creado_por=self.director,
        )

        pk_original = renglon_original.pk

        # 2. Se recibe justificación diferida para otro período del mismo mes
        # Lunes 19 y Martes 20 de Octubre 2026
        fecha_desde = datetime.date(2026, 10, 19)
        fecha_hasta = datetime.date(2026, 10, 20)

        procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            numero_disposicion="Disp. 102/2026",
            cargo=self.cargo,
            usuario=self.zaquino,
        )

        # 3. Verificación de Integridad Histórica (RN-03)
        # El renglón original NO fue eliminado
        self.assertTrue(
            RenglonPlanillaMensual.objects.filter(pk=pk_original).exists(),
            "RN-03: El renglón previo no debe ser eliminado.",
        )

        renglon_original.refresh_from_db()
        # El número de instrumento original permanece intacto
        self.assertEqual(
            renglon_original.numero_instrumento,
            "001/2026",
            "RN-03: No debe perderse el número de disposición asignado.",
        )

        # Se marca como desactualizada ante la novedad posterior
        self.assertTrue(
            renglon_original.desactualizada,
            "RN-03: La planilla previa debe marcarse como desactualizada.",
        )

        # El nuevo bloque recibió un número correlativo seguro sin colisionar
        nuevo_renglon = RenglonPlanillaMensual.objects.filter(
            desde=fecha_desde, hasta=fecha_hasta
        ).first()
        self.assertIsNotNone(nuevo_renglon)
        self.assertEqual(nuevo_renglon.numero_instrumento, "002/2026")

        # Total de renglones en Octubre: 2 (el previo y el nuevo)
        total_renglones = RenglonPlanillaMensual.objects.filter(
            mes=10, anio=2026
        ).count()
        self.assertEqual(total_renglones, 2)

    def test_fallo_simulado_genera_rollback_completo_transaction_atomic(self):
        """
        Validación 3 (Ticket 7):
        Un fallo o excepción simulada en medio del procesamiento genera
        un rollback íntegro gracias a transaction.atomic().
        """
        # 3 días hábiles: Lun 19, Mar 20, Mié 21
        fecha_desde = datetime.date(2026, 10, 19)
        fecha_hasta = datetime.date(2026, 10, 21)

        total_antes = RegistroAsistencia.objects.count()

        # Simular fallo en audit_save cuando se intenta guardar el segundo día
        llamadas = 0

        def audit_save_con_fallo(obj, user, created=False):
            nonlocal llamadas
            llamadas += 1
            if llamadas >= 2:
                raise ValidationError("Fallo de integridad simulado para rollback")
            return obj.save()

        with patch(
            "apps.licencias.services.audit_save",
            side_effect=audit_save_con_fallo,
        ):
            with self.assertRaises(ValidationError):
                procesar_justificacion_rango(
                    docente=self.docente,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                    nueva_marca="LIC",
                    tipo_licencia=self.tipo_lic,
                    cargo=self.cargo,
                    usuario=self.zaquino,
                )

        # Verificar que NO se guardó ningún registro (Rollback total)
        total_despues = RegistroAsistencia.objects.count()
        self.assertEqual(
            total_antes,
            total_despues,
            "Rollback atómico falló: quedaron registros huérfanos persistidos.",
        )

    def test_vista_justificacion_diferida_permisos_acceso(self):
        """
        Valida que Bedelia y Admin puedan acceder con HTTP 200/302,
        mientras que Consulta Directiva recibe 403 Forbidden.
        """
        url = reverse("licencias:justificacion_diferida")

        # Bedelia accede OK
        self.client.login(username="zaquino_lic", password="password123")
        resp_bedelia = self.client.get(url)
        self.assertEqual(resp_bedelia.status_code, 200)
        self.assertContains(resp_bedelia, "Justificación Diferida")

        # Admin accede OK
        self.client.login(username="director_lic", password="password123")
        resp_admin = self.client.get(url)
        self.assertEqual(resp_admin.status_code, 200)

        # Consulta Directiva recibe 403 Forbidden
        self.client.login(username="msosa_lic", password="password123")
        resp_consulta_get = self.client.get(url)
        self.assertEqual(resp_consulta_get.status_code, 403)

        resp_consulta_post = self.client.post(url, {})
        self.assertEqual(resp_consulta_post.status_code, 403)

    def test_vista_justificacion_diferida_post_exitoso(self):
        """
        Valida el flujo POST completo desde la vista JustificacionDiferidaView.
        """
        url = reverse("licencias:justificacion_diferida")
        self.client.login(username="zaquino_lic", password="password123")

        data = {
            "docente": self.docente.pk,
            "fecha_desde": "2026-11-02",
            "fecha_hasta": "2026-11-03",
            "nueva_marca": "LIC",
            "tipo_licencia": self.tipo_lic.pk,
            "numero_disposicion": "Disp. 150/2026",
            "observaciones": "Presentado en formulario oficial",
        }

        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("licencias:planilla_list"))

        # Validar registros creados
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente, fecha__year=2026, fecha__month=11
            ).count(),
            2,
        )

    def test_justificacion_diferida_form_rango_exitoso(self):
        """Valida JustificacionDiferidaForm con rango de fechas."""
        form = JustificacionDiferidaForm(
            data={
                "docente": self.docente.pk,
                "fecha_desde": "2026-11-09",
                "fecha_hasta": "2026-11-10",
                "nueva_marca": "P",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        res = form.save(usuario=self.zaquino)
        self.assertEqual(len(res), 2)
