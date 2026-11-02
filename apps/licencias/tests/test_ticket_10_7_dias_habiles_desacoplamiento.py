"""
Pruebas para el Ticket 10.7:
Flexibilización de Días Hábiles y Desacoplamiento.
Criterios de Aceptación:
- Una justificación por rango para un cargo con clases los sábados (ej. 6 horas)
  procesa y guarda correctamente ese día de fin de semana.
- Un cargo sin clases los fines de semana saltea sábados y domingos.
- El código de oficina se desacopla a config/settings.py (DEFAULT_OFICINA_CODE)
  y se consume dinámicamente con getattr.
"""

import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import TipoLicencia
from apps.licencias.services import (
    generar_planilla_mes,
    procesar_justificacion_rango,
)
from apps.personal.models import CargoDocente, Docente, EspacioCurricular

User = get_user_model()


class Ticket10_7FlexibilizacionDiasHabilesTests(TestCase):
    """
    Pruebas automatizadas para evaluar dinámicamente la carga horaria en fines
    de semana y desacoplar el código de oficina institucional.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_10_7",
            password="password123",
            email="admin107@test.com",
        )
        self.docente = Docente.objects.create(
            dni="32111000",
            apellido="SABATINI",
            nombre="Gabriela",
            sexo="F",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="TEC-SAB",
            nombre="Taller de Robótica Fin de Semana",
            carrera="Tecnicatura Superior",
            anio=2,
        )
        # Cargo con clases los viernes (4 hs) y sábados (6 hs)
        self.cargo_con_sabado = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            horas_lunes=0,
            horas_martes=0,
            horas_miercoles=0,
            horas_jueves=0,
            horas_viernes=4,
            horas_sabado=6,
            activo=True,
        )

        # Cargo regular de lunes a viernes (sin fines de semana)
        self.cargo_regular = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            horas_lunes=4,
            horas_martes=4,
            horas_miercoles=4,
            horas_jueves=4,
            horas_viernes=4,
            activo=True,
        )

        self.tipo_lic = TipoLicencia.objects.create(
            codigo="340-A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            cuadro_mensual="IL-01",
            activo=True,
        )

    def test_criterio_justificacion_rango_cargo_con_clases_sabado_procesa_fin_de_semana(
        self,
    ):
        """
        Criterio de Aceptación:
        Una justificación por rango para un cargo con clases los sábados
        (ej. 6 horas) procesa y guarda correctamente ese día de fin de semana.
        """
        # Noviembre 2026:
        # 2026-11-06: Viernes (4 hs)
        # 2026-11-07: Sábado (6 hs de clase)
        # 2026-11-08: Domingo (0 hs)
        # 2026-11-09: Lunes (0 hs para este cargo)
        f_desde = datetime.date(2026, 11, 6)
        f_hasta = datetime.date(2026, 11, 9)

        # Verificar que el método del modelo evalúa correctamente las 6 horas
        horas_sabado = self.cargo_con_sabado.obtener_horas_en_fecha(
            datetime.date(2026, 11, 7)
        )
        self.assertEqual(
            horas_sabado,
            6,
            "cargo.obtener_horas_en_fecha debe retornar 6 horas para el sábado.",
        )

        # Procesar justificación de rango para el cargo con sábados
        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=f_desde,
            fecha_hasta=f_hasta,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            cargo=self.cargo_con_sabado,
            usuario=self.user,
        )

        fechas_procesadas = [r.fecha for r in registros]

        # Viernes 6 debe procesarse
        self.assertIn(
            datetime.date(2026, 11, 6),
            fechas_procesadas,
            "El viernes 6 con clases debe procesarse.",
        )

        # Sábado 7 DEBE PROCESARSE Y GUARDARSE
        self.assertIn(
            datetime.date(2026, 11, 7),
            fechas_procesadas,
            "Criterio de Aceptación: El sábado 7 con 6 hs debe procesarse y guardarse.",
        )

        # Verificar persistencia en base de datos para el sábado
        reg_sabado = RegistroAsistencia.objects.filter(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 7),
        ).first()
        self.assertIsNotNone(reg_sabado)
        self.assertEqual(reg_sabado.estado, "LICENCIA")
        self.assertEqual(reg_sabado.marca_diaria, "LIC")
        self.assertEqual(reg_sabado.horas_afectadas(), 6)

        # Domingo 8 (0 hs) NO debe procesarse
        self.assertNotIn(
            datetime.date(2026, 11, 8),
            fechas_procesadas,
            "El domingo sin horas no debe procesarse.",
        )

        # Lunes 9 (0 hs para este cargo) NO debe procesarse
        self.assertNotIn(
            datetime.date(2026, 11, 9),
            fechas_procesadas,
            "El lunes sin horas no debe procesarse.",
        )

    def test_cargo_regular_sin_clases_fin_de_semana_omite_sabado_y_domingo(
        self,
    ):
        """
        Valida que un cargo regular de lunes a viernes omita sábados y domingos.
        """
        f_desde = datetime.date(2026, 11, 6)  # Viernes
        f_hasta = datetime.date(2026, 11, 9)  # Lunes

        registros = procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=f_desde,
            fecha_hasta=f_hasta,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic,
            cargo=self.cargo_regular,
            usuario=self.user,
        )

        fechas_procesadas = [r.fecha for r in registros]
        self.assertIn(datetime.date(2026, 11, 6), fechas_procesadas)
        self.assertIn(datetime.date(2026, 11, 9), fechas_procesadas)
        self.assertNotIn(datetime.date(2026, 11, 7), fechas_procesadas)
        self.assertNotIn(datetime.date(2026, 11, 8), fechas_procesadas)

    def test_desacoplamiento_default_oficina_code_consumido_dinamicamente(
        self,
    ):
        """
        Valida que el código de oficina se consuma dinámicamente desde settings
        (DEFAULT_OFICINA_CODE) usando getattr.
        """
        # Valor por defecto
        self.assertEqual(
            getattr(settings, "DEFAULT_OFICINA_CODE", None),
            "1452",
        )

        # Probar consumo dinámico con override_settings
        with override_settings(DEFAULT_OFICINA_CODE="8888"):
            # 1. En justificación por rango
            f_prueba = datetime.date(2026, 9, 10)
            procesar_justificacion_rango(
                docente=self.docente,
                fecha_desde=f_prueba,
                fecha_hasta=f_prueba,
                nueva_marca="LIC",
                tipo_licencia=self.tipo_lic,
                cargo=self.cargo_regular,
                usuario=self.user,
            )
            reg = RegistroAsistencia.objects.filter(
                docente=self.docente, fecha=f_prueba
            ).first()
            self.assertEqual(reg.oficina, "8888")

            # 2. En generación de planilla mensual
            renglones = generar_planilla_mes(mes=9, anio=2026, usuario=self.user)
            self.assertTrue(len(renglones) > 0)
            for r in renglones:
                self.assertEqual(r.oficina, "8888")
