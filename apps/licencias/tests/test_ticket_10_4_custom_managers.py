"""
Pruebas automatizadas para el Ticket 10.4:
- Custom Managers para Integridad Histórica y Blindaje RN-03.
- RenglonPlanillaManager (vigentes y desactualizados).
- DocenteManager.activos() y CargoDocenteManager.vigentes().
- Blindaje en RenglonPlanillaMensualListView y ExportarPlanillaCSVView.
- Fix de idempotencia en generar_planilla_mes evaluando solo vigentes.

Criterios de Aceptación:
1. Justificar una licencia diferida sobre un mes previo deja los renglones
   viejos en desactualizada=True.
2. La exportación CSV devuelve exactamente 1 renglón por materia sin
   datos duplicados.
"""

import csv
import datetime
import io
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
from apps.licencias.services import (
    generar_planilla_mes,
    procesar_justificacion_rango,
)
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


class Ticket10_4CustomManagersTests(TestCase):
    """
    Pruebas para validación de Custom Managers y Criterios de Aceptación 10.4.
    """

    def setUp(self):
        User = get_user_model()

        # Grupos y Usuario Administrador
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password="password123",
            is_staff=True,
        )
        self.admin_user.groups.add(self.grupo_admin)

        # Docente
        self.docente = Docente.objects.create(
            dni="26333444",
            apellido="ALVAREZ",
            nombre="Sergio",
            sexo="M",
            activo=True,
        )

        # Materia
        self.materia = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática I",
            carrera="Software",
            anio=1,
        )

        # Cargo Docente (Lunes 4 hs)
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            horas_lunes=4,
            desde_texto="01/03/2026",
            hasta_texto="SIN TERMINO",
            activo=True,
            fecha_alta=datetime.date(2026, 3, 1),
            fecha_baja=None,
        )

        # Tipos de Licencias
        self.tipo_lic_il01 = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.tipo_lic_il02 = TipoLicencia.objects.create(
            codigo="LIC-346",
            articulo="346",
            descripcion="Razones Particulares",
            cuadro_mensual="IL-02",
            activo=True,
        )

    def test_custom_manager_renglon_planilla_vigentes_y_desactualizados(self):
        """
        Valida que RenglonPlanillaManager filtre correctamente
        mediante .vigentes() y .desactualizados().
        """
        # Renglón vigente
        renglon_vig = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il01,
            cuadro="IL-01",
            mes=5,
            anio=2026,
            desde=datetime.date(2026, 5, 4),
            hasta=datetime.date(2026, 5, 4),
            horas_afectadas=4,
            numero_instrumento="010/2026",
            desactualizada=False,
        )

        # Renglón desactualizado
        renglon_desact = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il02,
            cuadro="IL-02",
            mes=5,
            anio=2026,
            desde=datetime.date(2026, 5, 4),
            hasta=datetime.date(2026, 5, 4),
            horas_afectadas=4,
            numero_instrumento="009/2026",
            desactualizada=True,
        )

        # Testeo de vigentes()
        qs_vigentes = RenglonPlanillaMensual.objects.vigentes()
        self.assertIn(renglon_vig, qs_vigentes)
        self.assertNotIn(renglon_desact, qs_vigentes)

        # Testeo de desactualizados()
        qs_desactualizados = RenglonPlanillaMensual.objects.desactualizados()
        self.assertIn(renglon_desact, qs_desactualizados)
        self.assertNotIn(renglon_vig, qs_desactualizados)

    def test_custom_manager_docente_activos(self):
        """
        Valida que Docente.objects.activos() retorne solo docentes con activo=True.
        """
        docente_inactivo = Docente.objects.create(
            dni="99888777",
            apellido="INACTIVO",
            nombre="Pedro",
            sexo="M",
            activo=False,
        )

        activos_qs = Docente.objects.activos()
        self.assertIn(self.docente, activos_qs)
        self.assertNotIn(docente_inactivo, activos_qs)

    def test_custom_manager_cargodocente_vigentes(self):
        """
        Valida que CargoDocente.objects.vigentes() filtre designaciones
        activas sin fecha_baja o con fecha_baja >= hoy.
        """
        hoy = timezone.now().date()

        # Cargo dado de baja ayer
        cargo_baja_ayer = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            activo=True,
            fecha_baja=hoy - datetime.timedelta(days=1),
        )

        # Cargo inactivo
        cargo_inactivo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="INT",
            activo=False,
        )

        vigentes_qs = CargoDocente.objects.vigentes()
        self.assertIn(self.cargo, vigentes_qs)
        self.assertNotIn(cargo_baja_ayer, vigentes_qs)
        self.assertNotIn(cargo_inactivo, vigentes_qs)

    def test_criterio_1_licencia_diferida_mes_previo_deja_viejos_desactualizados(
        self,
    ):
        """
        Criterio de Aceptación 1:
        Justificar una licencia diferida sobre un mes previo deja los renglones
        viejos en desactualizada=True y genera la nueva planilla vigente.
        """
        # 1. Crear inasistencia previa en Mayo 2026 (Lunes 18 de Mayo de 2026)
        fecha_mayo = datetime.date(2026, 5, 18)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            fecha=fecha_mayo,
            estado="AUSENTE",
            marca_diaria="I",
        )

        # 2. Generación inicial de la planilla de Mayo (mes=5, anio=2026)
        generar_planilla_mes(mes=5, anio=2026, usuario=self.admin_user)

        # Verificar renglón inicial vigente
        renglon_mayo_orig = RenglonPlanillaMensual.objects.get(
            docente=self.docente,
            mes=5,
            anio=2026,
        )
        self.assertFalse(renglon_mayo_orig.desactualizada)
        pk_orig = renglon_mayo_orig.pk

        # 3. Posteriormente se procesa Justificación Diferida para esa fecha
        procesar_justificacion_rango(
            docente=self.docente,
            fecha_desde=fecha_mayo,
            fecha_hasta=fecha_mayo,
            nueva_marca="LIC",
            tipo_licencia=self.tipo_lic_il01,
            cargo=self.cargo,
            usuario=self.admin_user,
        )

        # 4. Verificación del Criterio 1:
        # El renglón original debe quedar en desactualizada=True
        renglon_mayo_orig.refresh_from_db()
        self.assertTrue(
            renglon_mayo_orig.desactualizada,
            "Criterio 1: El renglón histórico previo debe quedar en "
            "desactualizada=True.",
        )

        # Debe existir un nuevo renglón vigente para Mayo con desactualizada=False
        nuevo_renglon = RenglonPlanillaMensual.objects.vigentes().get(
            docente=self.docente,
            mes=5,
            anio=2026,
        )
        self.assertNotEqual(nuevo_renglon.pk, pk_orig)
        self.assertFalse(nuevo_renglon.desactualizada)
        self.assertEqual(nuevo_renglon.cuadro, "IL-01")

        # Total en base de datos: 1 desactualizado + 1 vigente = 2
        total_mayo = RenglonPlanillaMensual.objects.filter(
            mes=5, anio=2026
        ).count()
        self.assertEqual(total_mayo, 2)

    def test_criterio_2_exportacion_csv_un_renglon_por_materia_sin_duplicados(
        self,
    ):
        """
        Criterio de Aceptación 2:
        La exportación CSV devuelve exactamente 1 renglón por materia
        sin datos duplicados, ignorando los renglones desactualizados.
        """
        # Renglón histórico desactualizado para la materia en Junio 2026
        RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il02,
            cuadro="IL-02",
            mes=6,
            anio=2026,
            desde=datetime.date(2026, 6, 1),
            hasta=datetime.date(2026, 6, 1),
            horas_afectadas=4,
            numero_instrumento="050/2026",
            desactualizada=True,
        )

        # Renglón actual vigente para la misma materia en Junio 2026
        RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il01,
            cuadro="IL-01",
            mes=6,
            anio=2026,
            desde=datetime.date(2026, 6, 1),
            hasta=datetime.date(2026, 6, 1),
            horas_afectadas=4,
            numero_instrumento="051/2026",
            desactualizada=False,
        )

        # En la BD existen 2 renglones para este mes/materia
        self.assertEqual(
            RenglonPlanillaMensual.objects.filter(mes=6, anio=2026).count(),
            2,
        )

        # Petición a la vista de exportación CSV con filtro del mes 6
        self.client.login(username="admin_test", password="password123")
        url_csv = reverse("licencias:exportar_planilla_csv")
        response = self.client.get(f"{url_csv}?mes=6&anio=2026")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"], "text/csv; charset=utf-8"
        )

        # Parsear el CSV resultante
        csv_content = response.content.decode("utf-8")
        reader = list(csv.reader(io.StringIO(csv_content)))

        # Encabezado (1 fila)
        self.assertGreater(len(reader), 1)
        headers = reader[0]
        self.assertIn("Materias", headers)

        # Filas de datos (debe ser exactamente 1 sola fila para la materia)
        data_rows = reader[1:]
        self.assertEqual(
            len(data_rows),
            1,
            "Criterio 2: El CSV debe contener exactamente 1 renglón por "
            "materia sin datos duplicados.",
        )

        # La única fila debe ser la del renglón vigente (IL-01, LIC-340A)
        fila = data_rows[0]
        # Columnas: Cuadro, N° Disposición, Docente, DNI, Desde, Hasta,
        # Materias, Horas, Tipo Licencia
        self.assertEqual(fila[0], "IL-01")
        self.assertEqual(fila[1], "051/2026")
        self.assertEqual(fila[6], "Matemática I")
        self.assertEqual(fila[8], "LIC-340A")

    def test_blindaje_planilla_list_view_muestra_solo_vigentes(self):
        """
        Valida que RenglonPlanillaMensualListView consulte y liste únicamente
        renglones vigentes, ocultando los desactualizados.
        """
        # Renglón vigente
        r_vig = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il01,
            cuadro="IL-01",
            mes=7,
            anio=2026,
            desde=datetime.date(2026, 7, 6),
            hasta=datetime.date(2026, 7, 6),
            horas_afectadas=4,
            numero_instrumento="080/2026",
            desactualizada=False,
        )

        # Renglón desactualizado
        r_desact = RenglonPlanillaMensual.objects.create(
            docente=self.docente,
            cargo=self.cargo,
            tipo_licencia=self.tipo_lic_il02,
            cuadro="IL-02",
            mes=7,
            anio=2026,
            desde=datetime.date(2026, 7, 6),
            hasta=datetime.date(2026, 7, 6),
            horas_afectadas=4,
            numero_instrumento="079/2026",
            desactualizada=True,
        )

        self.client.login(username="admin_test", password="password123")
        url_list = reverse("licencias:planilla_list")
        response = self.client.get(f"{url_list}?mes=7&anio=2026")

        self.assertEqual(response.status_code, 200)
        renglones_en_contexto = list(response.context["renglones"])

        self.assertIn(r_vig, renglones_en_contexto)
        self.assertNotIn(r_desact, renglones_en_contexto)
        self.assertEqual(response.context["total_il01"], 1)
        self.assertEqual(response.context["total_il02"], 0)
