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
        total_1 = RenglonPlanillaMensual.objects.filter(mes=10, anio=2026).count()
        self.assertEqual(len(renglones_1), 1)
        self.assertEqual(total_1, 1)

        # Segunda ejecución (debe hacer SKIP y no duplicar)
        renglones_2 = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)
        total_2 = RenglonPlanillaMensual.objects.filter(mes=10, anio=2026).count()
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
        renglones_2026 = generar_planilla_mes(mes=12, anio=2026, usuario=self.user)
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
        renglones_2027 = generar_planilla_mes(mes=1, anio=2027, usuario=self.user)
        self.assertEqual(len(renglones_2027), 1)
        # El contador se reinicia a 001 para el nuevo año
        self.assertEqual(renglones_2027[0].numero_instrumento, "001/2027")

    def test_desglose_multimateria_mismo_dia_rf12_rf14(self):
        """
        RF-12 y RF-14: Si un docente tiene 2 materias activas el mismo día de la falta,
        la planilla mensual debe desglosarse en 2 renglones independientes,
        uno por cada materia con su respectiva carga horaria.
        """
        materia_b = EspacioCurricular.objects.create(
            codigo="PROG-102",
            nombre="Programación II",
            carrera="Tecnicatura Superior",
            anio=2,
        )
        cargo_b = CargoDocente.objects.create(
            docente=self.docente,
            materia=materia_b,
            situacion_revista="TIT",
            horas_lunes=2,
            activo=True,
            hasta_texto="SIN TERMINO",
            creado_por=self.user,
        )

        # Falta un lunes (05/10/2026) registrada en las materias del docente
        fecha_lunes = datetime.date(2026, 10, 5)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            creado_por=self.user,
        )
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=cargo_b,
            fecha=fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            creado_por=self.user,
        )

        renglones = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)
        r_doc = [r for r in renglones if r.docente == self.docente]

        # Debe generar 2 renglones independientes (3 hs y 2 hs)
        self.assertEqual(len(r_doc), 2)
        materias_desglosadas = {
            r.cargo.materia.codigo: r.horas_afectadas for r in r_doc
        }
        self.assertEqual(materias_desglosadas["MAT-101"], 3)
        self.assertEqual(materias_desglosadas["PROG-102"], 2)

    def test_unicidad_inasistencia_simple_no_se_agrupa_rn06(self):
        """
        RN-06: Una inasistencia injustificada o falta simple se computa
        únicamente por el día puntual en que ocurrió. Dos días consecutivos
        de falta simple deben generar 2 renglones separados (de 1 día cada uno).
        """
        # Faltas injustificadas lunes 5 y martes 6 de octubre 2026
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=datetime.date(2026, 10, 5),
            estado="AUSENTE",
            marca_diaria="I",
            creado_por=self.user,
        )
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=datetime.date(2026, 10, 6),
            estado="AUSENTE",
            marca_diaria="I",
            creado_por=self.user,
        )

        renglones = generar_planilla_mes(mes=10, anio=2026, usuario=self.user)
        r_doc = [r for r in renglones if r.docente == self.docente]

        # Debe generar 2 renglones separados de 1 día cada uno, no 1 agrupado
        self.assertEqual(len(r_doc), 2)
        for r in r_doc:
            self.assertEqual(r.desde, r.hasta)
            self.assertEqual(r.horas_afectadas, 3)
