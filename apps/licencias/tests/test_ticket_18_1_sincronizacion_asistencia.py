"""
Pruebas automatizadas para Ticket 18.1:
Sincronización automática de licencias otorgadas con la Asistencia Diaria.

Criterio de Aceptación:
Al aprobar una licencia, los días comprendidos muestran automáticamente la marca
correspondiente en asistencia (LIC, LT, etc.). Al anularla, las marcas se revierten.
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import LicenciaOtorgada, RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import determinar_marca_licencia
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)

User = get_user_model()


class SincronizacionAsistenciaTicket18Tests(TestCase):
    """
    Suite de pruebas para validar Ticket 18.1: Sincronización automática
    de LicenciaOtorgada con RegistroAsistencia.
    """

    def setUp(self):
        super().setUp()

        # Docente de prueba
        self.docente = Docente.objects.create(
            dni="30111222",
            apellido="Gómez",
            nombre="Carlos",
            activo=True,
        )

        # Estructura curricular y cargos
        self.carrera = Carrera.objects.create(
            codigo="TSDS-18",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="BD-18",
            nombre="Bases de Datos",
            carrera=self.carrera,
            anio=1,
            turno="NOCHE",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="CAT-PROF-18",
            descripcion="Profesor Titular",
            activo=True,
        )
        self.cargo1 = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista="TIT",
            activo=True,
        )

        # Tipos de licencia estándar y largo tratamiento
        self.tipo_lic_ordinaria = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            categoria="LICENCIA",
            forma_goce="100%",
            duracion_maxima=30,
            unidad="Días",
            cuadro_mensual="IL-01",
        )
        self.tipo_lic_largo_tratamiento = TipoLicencia.objects.create(
            codigo="LIC-340B",
            articulo="340-B",
            descripcion="Afección de Largo Tratamiento",
            categoria="LICENCIA",
            forma_goce="100%",
            duracion_maxima=365,
            unidad="Días",
            cuadro_mensual="IL-01",
        )

        # Usuarios y roles para RBAC
        self.admin_user = User.objects.create_user(
            username="admin_test", password="password123", is_staff=True
        )
        self.bedelia_user = User.objects.create_user(
            username="bedelia_test", password="password123", is_staff=True
        )
        self.consulta_user = User.objects.create_user(
            username="consulta_test", password="password123", is_staff=True
        )

        admin_group, _ = Group.objects.get_or_create(name="Admin_Institucional")
        bedelia_group, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        consulta_group, _ = Group.objects.get_or_create(name="Consulta_Directiva")

        self.admin_user.groups.add(admin_group)
        self.bedelia_user.groups.add(bedelia_group)
        self.consulta_user.groups.add(consulta_group)

    def test_determinar_marca_licencia_helper(self):
        """Valida que el helper asigne 'LT' o 'LIC' según el tipo de licencia."""
        self.assertEqual(
            determinar_marca_licencia(self.tipo_lic_largo_tratamiento), "LT"
        )
        self.assertEqual(determinar_marca_licencia(self.tipo_lic_ordinaria), "LIC")
        self.assertEqual(determinar_marca_licencia(None), "LIC")

    def test_criterio_aceptacion_al_aprobar_licencia_dias_comprendidos(self):
        """
        Criterio de Aceptación Oficial Ticket 18.1:
        Al aprobar una licencia, los días comprendidos muestran automáticamente
        la marca correspondiente en asistencia ('LIC').
        """
        # Período: 3 días hábiles (Miércoles a Viernes)
        desde = datetime.date(2026, 11, 4)  # Miércoles
        hasta = datetime.date(2026, 11, 6)  # Viernes

        # 1. Crear solicitud de licencia en estado SOLICITADA
        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_solicitud=datetime.date(2026, 11, 1),
            fecha_desde=desde,
            fecha_hasta_prevista=hasta,
            estado="SOLICITADA",
            instrumento_legal="Resol. 450/26",
            sincronizar_asistencia=False,
        )

        # Verificar que antes de aprobar no existen marcas de asistencia
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente, fecha__range=[desde, hasta]
            ).count(),
            0,
        )

        # 2. Aprobar formalmente la licencia
        licencia.aprobar(usuario=self.admin_user)
        licencia.refresh_from_db()
        self.assertEqual(licencia.estado, "OTORGADA")

        # 3. Validar que los 3 días muestran automáticamente la marca 'LIC'
        registros = list(
            RegistroAsistencia.objects.filter(
                docente=self.docente,
                cargo=self.cargo1,
                fecha__range=[desde, hasta],
            ).order_by("fecha")
        )
        self.assertEqual(len(registros), 3)

        fechas_esperadas = [
            datetime.date(2026, 11, 4),
            datetime.date(2026, 11, 5),
            datetime.date(2026, 11, 6),
        ]
        for reg, f_esp in zip(registros, fechas_esperadas):
            self.assertEqual(reg.fecha, f_esp)
            self.assertEqual(reg.estado, "LICENCIA")
            self.assertEqual(reg.marca_diaria, "LIC")
            self.assertEqual(reg.tipo_licencia, self.tipo_lic_ordinaria)
            self.assertTrue(reg.justifica)
            self.assertEqual(reg.numero_disposicion, "Resol. 450/26")

    def test_sincronizacion_marca_largo_tratamiento_lt(self):
        """
        Valida que una licencia por afección de largo tratamiento refleje
        la marca diaria 'LT' en asistencia.
        """
        desde = datetime.date(2026, 11, 9)  # Lunes
        hasta = datetime.date(2026, 11, 10)  # Martes

        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_largo_tratamiento,
            fecha_desde=desde,
            fecha_hasta_prevista=hasta,
            estado="SOLICITADA",
            sincronizar_asistencia=False,
        )

        licencia.aprobar(usuario=self.bedelia_user)

        registros = RegistroAsistencia.objects.filter(
            docente=self.docente, fecha__range=[desde, hasta]
        )
        self.assertEqual(registros.count(), 2)
        for r in registros:
            self.assertEqual(r.marca_diaria, "LT")
            self.assertEqual(r.estado, "LICENCIA")

    def test_reversion_automatica_ante_anulacion(self):
        """
        Especificación Técnica Ticket 18.1:
        Revertir marcas diarias ante la anulación de la licencia.
        """
        desde = datetime.date(2026, 11, 16)
        hasta = datetime.date(2026, 11, 17)

        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_desde=desde,
            fecha_hasta_prevista=hasta,
            estado="OTORGADA",
        )

        # Verificar que están sincronizadas con 'LIC'
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente,
                fecha__range=[desde, hasta],
                marca_diaria="LIC",
            ).count(),
            2,
        )

        # Anular la licencia
        licencia.anular(usuario=self.admin_user, motivo="Certificado revocado")
        licencia.refresh_from_db()
        self.assertEqual(licencia.estado, "CANCELADA")
        self.assertIn("Certificado revocado", licencia.observaciones)

        # Validar reversión en asistencia diaria (pasan a inasistencia 'I')
        registros_revertidos = RegistroAsistencia.objects.filter(
            docente=self.docente, fecha__range=[desde, hasta]
        )
        self.assertEqual(registros_revertidos.count(), 2)
        for r in registros_revertidos:
            self.assertEqual(r.marca_diaria, "I")
            self.assertEqual(r.estado, "AUSENTE")
            self.assertIsNone(r.tipo_licencia)
            self.assertFalse(r.justifica)

    def test_preservacion_marca_previa_al_revertir(self):
        """
        Valida que si un registro ya existía previamente como inasistencia ('I'),
        al aprobar pasa a 'LIC' y al anular vuelve fielmente a 'I'.
        """
        fecha_test = datetime.date(2026, 11, 18)

        # Registro preexistente de Bedelía
        reg_previo = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            fecha=fecha_test,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            observaciones="Falta sin aviso",
        )

        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_desde=fecha_test,
            fecha_hasta_prevista=fecha_test,
            estado="OTORGADA",
        )

        reg_previo.refresh_from_db()
        self.assertEqual(reg_previo.marca_diaria, "LIC")
        self.assertEqual(reg_previo.estado, "LICENCIA")
        self.assertTrue(reg_previo.justifica)

        # Ahora anulamos
        licencia.anular(usuario=self.admin_user)
        reg_previo.refresh_from_db()
        self.assertEqual(reg_previo.marca_diaria, "I")
        self.assertEqual(reg_previo.estado, "AUSENTE")
        self.assertFalse(reg_previo.justifica)
        self.assertIsNone(reg_previo.tipo_licencia)

    def test_licencia_institucional_general_sincroniza_todos_los_cargos_activos(
        self,
    ):
        """
        Valida que si una licencia se otorga a nivel institucional (cargo=None),
        se sincronice en todos los cargos activos del docente.
        """
        espacio2 = EspacioCurricular.objects.create(
            codigo="PROG-18",
            nombre="Programación",
            carrera=self.carrera,
            anio=2,
            turno="NOCHE",
        )
        cargo2 = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=espacio2,
            situacion_revista="INT",
            activo=True,
        )

        desde = datetime.date(2026, 11, 24)
        hasta = datetime.date(2026, 11, 24)

        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=None,  # General para el docente
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_desde=desde,
            fecha_hasta_prevista=hasta,
            estado="OTORGADA",
        )

        regs_c1 = RegistroAsistencia.objects.filter(
            docente=self.docente, cargo=self.cargo1, fecha=desde
        )
        regs_c2 = RegistroAsistencia.objects.filter(
            docente=self.docente, cargo=cargo2, fecha=desde
        )
        self.assertEqual(regs_c1.count(), 1)
        self.assertEqual(regs_c2.count(), 1)
        self.assertEqual(regs_c1.first().marca_diaria, "LIC")
        self.assertEqual(regs_c2.first().marca_diaria, "LIC")

    def test_vistas_aprobar_y_anular_flujo_http_y_rbac(self):
        """
        Valida el flujo web completo mediante las vistas:
        - Admin y Bedelía pueden aprobar y anular (302 con éxito).
        - Consulta Directiva recibe 403 Forbidden.
        - Usuario anónimo recibe 302 a login.
        """
        licencia = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_desde=datetime.date(2026, 11, 25),
            fecha_hasta_prevista=datetime.date(2026, 11, 26),
            estado="SOLICITADA",
            sincronizar_asistencia=False,
        )

        url_aprobar = reverse("licencias:licenciaotorgada_aprobar", args=[licencia.pk])
        url_anular = reverse("licencias:licenciaotorgada_anular", args=[licencia.pk])

        # 1. Anónimo -> 302 a login
        resp_anon = self.client.post(url_aprobar)
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn("/accounts/login/", resp_anon.url)

        # 2. Consulta Directiva -> 403 Forbidden
        self.client.login(username="consulta_test", password="password123")
        resp_consulta = self.client.post(url_aprobar)
        self.assertEqual(resp_consulta.status_code, 403)
        self.client.logout()

        # 3. Bedelía aprueba -> 302 a listado y marcas creadas
        self.client.login(username="bedelia_test", password="password123")
        resp_bedelia = self.client.post(url_aprobar)
        self.assertEqual(resp_bedelia.status_code, 302)
        self.assertRedirects(resp_bedelia, reverse("licencias:licenciaotorgada_list"))

        licencia.refresh_from_db()
        self.assertEqual(licencia.estado, "OTORGADA")
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente,
                fecha__range=[licencia.fecha_desde, licencia.fecha_hasta_prevista],
                marca_diaria="LIC",
            ).count(),
            2,
        )

        # 4. Admin anula -> 302 a listado y marcas revertidas
        self.client.login(username="admin_test", password="password123")
        resp_anular = self.client.post(url_anular, {"motivo": "Anulado por error"})
        self.assertEqual(resp_anular.status_code, 302)
        self.assertRedirects(resp_anular, reverse("licencias:licenciaotorgada_list"))

        licencia.refresh_from_db()
        self.assertEqual(licencia.estado, "CANCELADA")
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente,
                fecha__range=[licencia.fecha_desde, licencia.fecha_hasta_prevista],
                marca_diaria="I",
            ).count(),
            2,
        )

    def test_regla_rn03_desactualiza_planillas_mensuales_al_sincronizar(self):
        """
        Valida que si existe una planilla mensual consolidada emitida en el mes,
        al sincronizar se marque automáticamente como desactualizada=True (RN-03).
        """
        # Crear renglón consolidado existente para Noviembre 2026
        planilla = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            mes=11,
            anio=2026,
            desde=datetime.date(2026, 11, 2),
            hasta=datetime.date(2026, 11, 3),
            horas_afectadas=4,
            numero_instrumento="001/2026",
            desactualizada=False,
        )

        # Crear y aprobar licencia en ese mismo mes
        LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo1,
            tipo_licencia=self.tipo_lic_ordinaria,
            fecha_desde=datetime.date(2026, 11, 26),
            fecha_hasta_prevista=datetime.date(2026, 11, 27),
            estado="OTORGADA",
        )

        planilla.refresh_from_db()
        self.assertTrue(
            planilla.desactualizada,
            "RN-03: La planilla preexistente debe marcarse como desactualizada.",
        )
