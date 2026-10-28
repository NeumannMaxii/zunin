"""
Pruebas automatizadas para el motor mensual de licencias (Ticket 2):
- Idempotencia: no duplica renglones al ejecutar dos veces el motor.
- Adyacencia: agrupa bloques contiguos de licencias.
- Cross-year: reinicio del contador anual de instrumentos a '001/YYYY'.
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import generar_planilla_mes
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class MotorMensualPlanillaTests(TestCase):
    """Pruebas de la lógica del motor generar_planilla_mes."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="admin_motor",
            password="password123",
        )
        self.docente = Docente.objects.create(
            dni="20444555",
            apellido="Acosta",
            nombre="Valeria",
            sexo="F",
            creado_por=self.user,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática I",
            carrera="Tecnicatura Superior",
            anio=1,
        )
        # Cargo docente con horas asignadas lunes, martes, miércoles
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            horas_lunes=3,
            horas_martes=3,
            horas_miercoles=3,
            activo=True,
            hasta_texto="SIN TERMINO",
            creado_por=self.user,
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="Art. 340-A",
            descripcion="Enfermedad de corto tratamiento",
            cuadro_mensual="IL-01",
            creado_por=self.user,
        )

    def test_idempotencia_ejecutar_dos_veces_no_duplica_renglones(self):
        """
        1. Idempotencia: Verificar que ejecutar el motor dos veces para el
        mismo mes no duplica renglones en la base de datos (SKIP).
        """
        fecha_lunes = datetime.date(2026, 10, 5)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=None,
            fecha=fecha_lunes,
            estado="LICENCIA",
            marca_diaria="LIC",
            tipo_licencia=self.tipo_lic,
            creado_por=self.user,
        )

        # Primera ejecución
        renglones_1 = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)
        total_1 = RenglonPlanillaMensual.objects.filter(
            mes=10, anio=2026
        ).count()
        self.assertEqual(len(renglones_1), 1)
        self.assertEqual(total_1, 1)

        # Segunda ejecución (debe hacer SKIP y no duplicar)
        renglones_2 = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)
        total_2 = RenglonPlanillaMensual.objects.filter(
            mes=10, anio=2026
        ).count()
        self.assertEqual(total_1, total_2)
        self.assertEqual(len(renglones_2), 1)

    def test_adyacencia_agrupa_bloques_contiguos_mismo_tipo_licencia(self):
        """
        2. Adyacencia: Agrupa correctamente registros continuos con el mismo
        tipo de licencia en un único bloque con fecha_desde y fecha_hasta consolidadas.
        """
        # Tres días consecutivos: 5 (lunes), 6 (martes) y 7 (miércoles) de Octubre 2026
        for f in [
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 6),
            datetime.date(2026, 10, 7),
        ]:
            RegistroAsistencia.objects.create(
                docente=self.docente,
                cargo=None,
                fecha=f,
                estado="LICENCIA",
                marca_diaria="LIC",
                tipo_licencia=self.tipo_lic,
                creado_por=self.user,
            )

        renglones = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)

        # Debe generar un único renglón que abarque del 05/10 al 07/10
        self.assertEqual(len(renglones), 1)
        renglon = renglones[0]
        self.assertEqual(renglon.desde, datetime.date(2026, 10, 5))
        self.assertEqual(renglon.hasta, datetime.date(2026, 10, 7))
        # 3hs lunes + 3hs martes + 3hs miércoles = 9hs afectadas
        self.assertEqual(renglon.horas_afectadas, 9)

    def test_cross_year_reinicia_contador_instrumento(self):
        """
        3. Cross-year: Generar planilla en Dic 2026 y luego otra en Ene 2027
        reinicia el contador de instrumento correlativo a '001/2027'.
        """
        # Registro en Diciembre 2026
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=None,
            fecha=datetime.date(2026, 12, 1),
            estado="LICENCIA",
            marca_diaria="LIC",
            tipo_licencia=self.tipo_lic,
            creado_por=self.user,
        )
        renglones_2026 = generar_planilla_mes(
            mes=12, anio=2026, usuario=self.user
        )
        self.assertEqual(len(renglones_2026), 1)
        self.assertTrue(renglones_2026[0].numero_instrumento.endswith("/2026"))

        # Registro en Enero 2027
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=None,
            fecha=datetime.date(2027, 1, 11),
            estado="LICENCIA",
            marca_diaria="LIC",
            tipo_licencia=self.tipo_lic,
            creado_por=self.user,
        )
        renglones_2027 = generar_planilla_mes(
            mes=1, anio=2027, usuario=self.user
        )
        self.assertEqual(len(renglones_2027), 1)
        # El contador se reinicia a 001 para el nuevo año
        self.assertEqual(renglones_2027[0].numero_instrumento, "001/2027")
