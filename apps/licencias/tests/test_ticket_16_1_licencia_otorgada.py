"""
Pruebas automatizadas para Ticket 16.1:
Creación del modelo LicenciaOtorgada.

Valida:
- Creación de registro de licencia vinculado a docente y cargo específico
  (Criterio de Aceptación).
- Persistencia y tipos de datos de todos los atributos:
  * docente_id
  * cargo_id
  * tipo_licencia_id
  * fecha_solicitud
  * fecha_desde
  * fecha_hasta_prevista
  * estado
  * porcentaje_goce
  * instrumento_legal
- Relaciones inversas (related_name="licencias_otorgadas").
- Sincronización y derivación de porcentajes de goce.
- Propiedades de duración y trazabilidad de auditoría.
"""

import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
)


class LicenciaOtorgadaModelTests(TestCase):
    """
    Suite de validación unitaria para el modelo LicenciaOtorgada (Ticket 16.1).
    """

    def setUp(self):
        super().setUp()
        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            dni="28123456",
            activo=True,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS-16",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PROG-16",
            nombre="Programación Avanzada",
            carrera=self.carrera,
            anio=2,
            turno="MANANA",
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="PROF-16",
            descripcion="Profesor Titular de Cátedra",
            activo=True,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            cargo_catalogo=self.cargo_cat,
            materia=self.espacio,
            situacion_revista="TIT",
            activo=True,
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-TEST-161",
            articulo="Art. 335",
            descripcion="Matrimonio del docente",
            categoria="Extraordinaria",
            forma_goce="100%",
            duracion_maxima=10,
            unidad="Hábiles",
            periodo_tope="Hecho",
            cuadro_mensual="IL-02",
        )

    def test_creacion_licencia_otorgada_con_docente_y_cargo_especifico(self):
        """
        Criterio de Aceptación:
        Es posible crear un registro de licencia vinculado a un docente
        y cargo específico.
        """
        fecha_sol = datetime.date(2026, 11, 1)
        fecha_ini = datetime.date(2026, 11, 5)
        fecha_fin = datetime.date(2026, 11, 14)

        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_solicitud=fecha_sol,
            fecha_desde=fecha_ini,
            fecha_hasta_prevista=fecha_fin,
            estado="OTORGADA",
            porcentaje_goce=Decimal("100.00"),
            instrumento_legal="Resolución Ministerial 450/2026",
            observaciones="Solicitud aprobada con documentación adjunta.",
        )

        lic.refresh_from_db()
        self.assertEqual(lic.docente, self.docente)
        self.assertEqual(lic.docente_id, self.docente.id)
        self.assertEqual(lic.cargo, self.cargo)
        self.assertEqual(lic.cargo_id, self.cargo.id)
        self.assertEqual(lic.tipo_licencia, self.tipo_lic)
        self.assertEqual(lic.tipo_licencia_id, self.tipo_lic.id)
        self.assertEqual(lic.fecha_solicitud, fecha_sol)
        self.assertEqual(lic.fecha_desde, fecha_ini)
        self.assertEqual(lic.fecha_hasta_prevista, fecha_fin)
        self.assertEqual(lic.estado, "OTORGADA")
        self.assertEqual(lic.porcentaje_goce, Decimal("100.00"))
        self.assertEqual(
            lic.instrumento_legal, "Resolución Ministerial 450/2026"
        )
        self.assertEqual(
            lic.observaciones, "Solicitud aprobada con documentación adjunta."
        )

        # Duración calculada
        self.assertEqual(lic.dias_duracion_prevista, 10)

        # Representación en string
        self.assertIn("LIC-TEST-161", str(lic))
        self.assertIn(str(self.docente), str(lic))

    def test_valores_por_defecto_y_derivacion_de_goce(self):
        """
        Verifica valores por defecto (fecha_solicitud, estado) y
        la derivación automática del porcentaje_goce según el tipo de licencia.
        """
        hoy = datetime.date.today()
        hasta = hoy + datetime.timedelta(days=5)

        # 1. Tipo de licencia con 50%
        tipo_50 = TipoLicencia.objects.create(
            codigo="LIC-50-161",
            descripcion="Licencia reducida al 50%",
            forma_goce="50%",
            cuadro_mensual="IL-01",
        )
        lic_50 = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=tipo_50,
            fecha_desde=hoy,
            fecha_hasta_prevista=hasta,
        )
        self.assertEqual(lic_50.fecha_solicitud, hoy)
        self.assertEqual(lic_50.estado, "OTORGADA")
        self.assertEqual(lic_50.porcentaje_goce, Decimal("50.00"))

        # 2. Tipo de licencia Sin goce
        tipo_sin = TipoLicencia.objects.create(
            codigo="LIC-SIN-161",
            descripcion="Licencia sin goce de haberes",
            forma_goce="Sin goce",
            cuadro_mensual="IL-02",
        )
        lic_sin = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=tipo_sin,
            fecha_desde=hoy,
            fecha_hasta_prevista=hasta,
        )
        self.assertEqual(lic_sin.porcentaje_goce, Decimal("0.00"))

        # 3. Conversión de string como "50%"
        lic_str = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=hoy,
            fecha_hasta_prevista=hasta,
            porcentaje_goce="50%",
        )
        self.assertEqual(lic_str.porcentaje_goce, Decimal("50.00"))

    def test_relaciones_inversas_docente_cargo_y_tipo_licencia(self):
        """
        Verifica que docente, cargo y tipo_licencia puedan consultar sus
        licencias otorgadas a través del related_name 'licencias_otorgadas'.
        """
        hoy = datetime.date.today()
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=hoy,
            fecha_hasta_prevista=hoy + datetime.timedelta(days=7),
            estado="SOLICITADA",
        )

        self.assertIn(lic, self.docente.licencias_otorgadas.all())
        self.assertIn(lic, self.cargo.licencias_otorgadas.all())
        self.assertIn(lic, self.tipo_lic.licencias_otorgadas.all())

    def test_estados_validos_licencia_otorgada(self):
        """
        Verifica los estados disponibles para la gestión de solicitudes:
        SOLICITADA, OTORGADA, RECHAZADA, FINALIZADA, CANCELADA.
        """
        estados_esperados = [
            "SOLICITADA",
            "OTORGADA",
            "RECHAZADA",
            "FINALIZADA",
            "CANCELADA",
        ]
        choices_estados = [
            key for key, _ in LicenciaOtorgada.ESTADO_CHOICES
        ]
        for estado in estados_esperados:
            self.assertIn(estado, choices_estados)

    def test_auditoria_trazabilidad_creacion_modificacion(self):
        """
        Verifica que LicenciaOtorgada herede de AuditoriaModel y registre
        creado_en, actualizado_en y usuario creador/modificador.
        """
        user = get_user_model().objects.create_user(
            username="admin_audit",
            password="testpassword",
        )
        hoy = datetime.date.today()
        lic = LicenciaOtorgada.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic,
            fecha_desde=hoy,
            fecha_hasta_prevista=hoy + datetime.timedelta(days=3),
            creado_por=user,
        )

        self.assertIsNotNone(lic.creado_en)
        self.assertIsNotNone(lic.actualizado_en)
        self.assertEqual(lic.creado_por, user)
        self.assertEqual(lic.creado_el, lic.creado_en)
        self.assertEqual(lic.modificado_el, lic.actualizado_en)
