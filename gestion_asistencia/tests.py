import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from gestion_asistencia.apps import GestionAsistenciaConfig
from gestion_asistencia.models import (
    Docente,
    EspacioCurricular,
    Carrera,
    CargoCatalogo,
    TipoAutorizacion,
    CargoDocente,
    TipoLicencia,
    DiaNoLaborable,
    RegistroAsistencia,
    RenglonPlanillaMensual,
    autocompletar_por_articulo,
)


class GestionAsistenciaAppTests(TestCase):
    """Pruebas de configuración y arranque de la aplicación."""

    def test_app_is_installed(self):
        """Verifica que la app gestion_asistencia esté registrada."""
        self.assertTrue(apps.is_installed("gestion_asistencia"))

    def test_app_config_name(self):
        """Verifica que el AppConfig tenga el nombre correcto."""
        self.assertEqual(GestionAsistenciaConfig.name, "gestion_asistencia")


class VistaPrincipalTests(TestCase):
    """Pruebas para la vista inicial del dashboard de Bedelía."""

    def setUp(self):
        self.client = Client()

    def test_index_url_status_code(self):
        """Verifica que la página principal retorne código HTTP 200."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertEqual(response.status_code, 200)

    def test_index_template_used(self):
        """Verifica que se usen las plantillas base.html e index.html."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "gestion_asistencia/index.html")

    def test_index_context_and_content(self):
        """Verifica la presencia de la marca institucional IESETyFP."""
        response = self.client.get(reverse("gestion_asistencia:index"))
        self.assertContains(response, "IESETyFP")
        self.assertContains(response, "Bedelía")


class ModelosRelacionalesTests(TestCase):
    """Pruebas unitarias para los modelos relacionales del IESETyFP."""

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="32456789",
            apellido="González",
            nombre="Laura",
            sexo="F",
            contacto="laura.gonzalez@iesetyfp.edu.ar",
            activo=True,
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="DS-301",
            nombre="Práctica Profesionalizante III",
            carrera="Tecnicatura Superior en Desarrollo de Software",
            anio=3,
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TITULAR",
            horas_lunes=4,
            horas_martes=0,
            horas_miercoles=3,
            horas_jueves=0,
            horas_viernes=2,
            resolucion="Res. 1420/24",
        )
        self.tipo_licencia = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="Art. 340-A",
            descripcion="Enfermedad de corto tratamiento",
            goce_haberes=True,
            tope_anual=30,
            activo=True,
        )

    def test_docente_str_y_propiedades(self):
        """Verifica representación en cadena y propiedades del docente."""
        self.assertEqual(str(self.docente), "González, Laura (DNI: 32456789)")
        self.assertEqual(self.docente.nombre_completo, "González, Laura")
        self.assertEqual(self.docente.total_horas_semanales, 9)

    def test_espacio_curricular_str(self):
        """Verifica representación en cadena del espacio curricular."""
        expected = (
            "DS-301 - Práctica Profesionalizante III "
            "(Tecnicatura Superior en Desarrollo de Software - 3° Año)"
        )
        self.assertEqual(str(self.espacio), expected)

    def test_cargo_docente_calculo_horas(self):
        """Verifica cálculo total semanal y desglose por día del cargo."""
        self.assertEqual(self.cargo.total_horas_semanales, 9)
        # Lunes (0), Miércoles (2), Viernes (4)
        self.assertEqual(self.cargo.get_horas_dia(0), 4)
        self.assertEqual(self.cargo.get_horas_dia(1), 0)
        self.assertEqual(self.cargo.get_horas_dia(2), 3)
        self.assertEqual(self.cargo.get_horas_dia(3), 0)
        self.assertEqual(self.cargo.get_horas_dia(4), 2)

    def test_tipo_licencia_str(self):
        """Verifica formato de cadena de tipo de licencia con goce de haberes."""
        expected = (
            "Art. 340-A (LIC-340A) - Enfermedad de corto tratamiento [C/Goce]"
        )
        self.assertEqual(str(self.tipo_licencia), expected)

    def test_registro_asistencia_presente_exitoso(self):
        """Crea un registro de asistencia PRESENTE válido."""
        fecha_lunes = datetime.date(2026, 10, 19)  # 2026-10-19 es Lunes
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_lunes,
            estado="PRESENTE",
        )
        asistencia.full_clean()
        asistencia.save()
        self.assertIn("Presente", str(asistencia))
        self.assertEqual(asistencia.horas_afectadas(), 4)

    def test_registro_asistencia_licencia_valida(self):
        """Crea un registro de asistencia en LICENCIA con tipo asignado."""
        fecha_miercoles = datetime.date(2026, 10, 21)  # Miércoles
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_miercoles,
            estado="LICENCIA",
            tipo_licencia=self.tipo_licencia,
        )
        asistencia.full_clean()
        asistencia.save()
        self.assertEqual(asistencia.horas_afectadas(), 3)

    def test_validacion_licencia_sin_tipo(self):
        """Lanza ValidationError si estado es LICENCIA y no se asigna tipo."""
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 22),
            estado="LICENCIA",
        )
        with self.assertRaises(ValidationError):
            asistencia.full_clean()

    def test_validacion_presente_con_tipo_licencia(self):
        """Lanza ValidationError si estado es PRESENTE y se adjunta tipo."""
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 23),
            estado="PRESENTE",
            tipo_licencia=self.tipo_licencia,
        )
        with self.assertRaises(ValidationError):
            asistencia.full_clean()

    def test_unicidad_docente_fecha(self):
        """Verifica que no se dupliquen partes diarios en la misma fecha."""
        fecha = datetime.date(2026, 10, 26)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=fecha,
            estado="PRESENTE",
        )
        with self.assertRaises(IntegrityError):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                fecha=fecha,
                estado="AUSENTE",
            )

    def test_cargo_suplente_requiere_docente_reemplazado(self):
        """Suplente sin docente reemplazado emite ValidationError en clean()."""
        cargo_suplente = CargoDocente(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="SUPLENTE",
            horas_lunes=2,
            docente_reemplazado=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            cargo_suplente.full_clean()
        self.assertIn("docente_reemplazado", ctx.exception.message_dict)
        error_msg = ctx.exception.message_dict["docente_reemplazado"][0]
        self.assertIn(
            "Debe especificar el docente reemplazado para una suplencia según "
            "Formulario DP-01",
            error_msg,
        )

    def test_cargo_suplente_con_docente_reemplazado_valido(self):
        """Suplente con docente reemplazado valida y persiste exitosamente."""
        docente_reemplazado = Docente.objects.create(
            dni="28123456",
            apellido="Ramírez",
            nombre="Carlos",
            sexo="M",
        )
        cargo_suplente = CargoDocente(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="SUPLENTE",
            docente_reemplazado=docente_reemplazado,
            horas_martes=3,
        )
        cargo_suplente.full_clean()
        cargo_suplente.save()
        self.assertEqual(
            cargo_suplente.docente_reemplazado, docente_reemplazado
        )
        self.assertIn(
            cargo_suplente, docente_reemplazado.suplencias_recibidas.all()
        )

    def test_cargo_administrativo_sin_materia(self):
        """Permite cargo administrativo sin materia (null=True)."""
        cargo_adm = CargoDocente(
            docente=self.docente,
            materia=None,
            tipo_cargo="CARGO_ADM",
            situacion_revista="TITULAR",
            horas_lunes=5,
        )
        cargo_adm.full_clean()
        cargo_adm.save()
        self.assertIsNone(cargo_adm.materia)
        self.assertIn("Cargo Administrativo / Bedel", str(cargo_adm))

    def test_tipo_licencia_categoria_permiso_cincuenta_porciento(self):
        """Licencia PERMISO con CINCUENTA_PORCIENTO sincroniza goce=False."""
        licencia = TipoLicencia.objects.create(
            codigo="PERM-50",
            articulo="Art. 210",
            descripcion="Permiso gremial parcial",
            categoria="PERMISO",
            forma_pago="CINCUENTA_PORCIENTO",
        )
        self.assertEqual(licencia.categoria, "PERMISO")
        self.assertEqual(licencia.forma_pago, "CINCUENTA_PORCIENTO")
        self.assertFalse(licencia.goce_haberes)
        self.assertIn("[S/Goce]", str(licencia))

    def test_tipo_licencia_categoria_inasistencia_cincuenta_porciento(self):
        """Inasistencia con CINCUENTA_PORCIENTO sincroniza goce=False."""
        inasistencia = TipoLicencia.objects.create(
            codigo="INA-50",
            articulo="Art. 105",
            descripcion="Inasistencia justificada al 50%",
            categoria="INASISTENCIA",
            forma_pago="CINCUENTA_PORCIENTO",
        )
        self.assertEqual(inasistencia.categoria, "INASISTENCIA")
        self.assertEqual(inasistencia.forma_pago, "CINCUENTA_PORCIENTO")
        self.assertFalse(inasistencia.goce_haberes)

    def test_docente_campos_oficiales_formulario_1(self):
        """Verifica campos ampliados según Formulario N° 1 de Agente (Chaco)."""
        docente = Docente.objects.create(
            dni="40123987",
            apellido="Benítez",
            nombre="Mariano",
            tipo_documento="DNI",
            fecha_nacimiento=datetime.date(1995, 5, 14),
            estado_civil="Soltero",
            nacionalidad="Argentina",
            cuil_dgi="20-40123987-3",
            inscripcion_dgr="99-887766-5",
            domicilio_calle="Av. Las Heras 727",
            barrio="Centro",
            localidad="Resistencia",
            codigo_postal="3500",
            provincia="Chaco",
        )
        self.assertEqual(docente.tipo_documento, "DNI")
        self.assertEqual(docente.cuil_dgi, "20-40123987-3")
        self.assertEqual(docente.provincia, "Chaco")

    def test_espacio_curricular_campos_oficiales(self):
        """Verifica nuevos campos comision, turno, regimen, aula y plan."""
        espacio = EspacioCurricular.objects.create(
            codigo="BD-202",
            nombre="Bases de Datos",
            carrera="Tecnicatura Superior en Desarrollo de Software",
            anio=2,
            comision="A",
            turno="NOCHE",
            regimen="CUAT_1",
            aula="Laboratorio 1",
            plan_estudio="Plan Res. 4500/22",
        )
        self.assertEqual(espacio.comision, "A")
        self.assertEqual(espacio.turno, "NOCHE")
        self.assertEqual(espacio.regimen, "CUAT_1")
        self.assertEqual(espacio.aula, "Laboratorio 1")
        self.assertEqual(espacio.plan_estudio, "Plan Res. 4500/22")

    def test_registro_asistencia_formulario_dl01_campos(self):
        """Verifica campos fecha_hasta, justifica y numero_disposicion."""
        asistencia = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 2),
            fecha_hasta=datetime.date(2026, 11, 6),
            estado="LICENCIA",
            tipo_licencia=self.tipo_licencia,
            justifica=True,
            numero_disposicion="Disp. D-045/26",
            observaciones="Licencia médica otorgada",
        )
        asistencia.full_clean()
        self.assertEqual(asistencia.fecha_hasta, datetime.date(2026, 11, 6))
        self.assertTrue(asistencia.justifica)
        self.assertEqual(asistencia.numero_disposicion, "Disp. D-045/26")


class ReglasNegocioRequerimientosV1Tests(TestCase):
    """
    Pruebas unitarias de las Reglas de Negocio RN-01 a RN-10
    del Documento de Requerimientos Intercátedra v1.0.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="bedel_test",
            password="testpassword123",
        )
        self.docente = Docente.objects.create(
            dni="20111222",
            apellido="Pérez",
            nombre="Juan",
            creado_por=self.user,
        )
        self.carrera = Carrera.objects.create(
            codigo="TSDS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
        )
        self.cargo_catalogo = CargoCatalogo.objects.create(
            codigo="PROF-SUP",
            descripcion="Profesor de Educación Superior",
        )
        self.tipo_autorizacion = TipoAutorizacion.objects.create(
            nombre="RESOLUCIÓN",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PROG-1",
            nombre="Programación I",
            carrera="TSDS",
            anio=1,
        )

    def test_rn01_y_rn02_multiples_designaciones_mismo_dni(self):
        """
        RN-01 y RN-02: Múltiples designaciones para un mismo DNI sin duplicar
        el registro del docente, soportando códigos abreviados TIT, INT, SUP.
        """
        cargo_tit = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
            carrera_ref=self.carrera,
            cargo_catalogo=self.cargo_catalogo,
            tipo_autorizacion=self.tipo_autorizacion,
            horas_lunes=3,
        )
        cargo_sup = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="SUP",
            carrera_ref=self.carrera,
            horas_martes=2,
            docente_reemplazado=None,
        )
        cargo_sup.full_clean()

        self.assertEqual(
            Docente.objects.filter(dni="20111222").count(), 1
        )
        cargos = self.docente.cargos.all()
        self.assertEqual(cargos.count(), 2)
        self.assertIn(cargo_tit, cargos)
        self.assertIn(cargo_sup, cargos)
        self.assertEqual(cargo_tit.situacion_revista, "TIT")
        self.assertEqual(cargo_sup.situacion_revista, "SUP")

    def test_rn04_y_rn05_clasificacion_tipo_licencia_cuadros(self):
        """
        RN-04 y RN-05: Clasificación en DL-01 (enfermedad) y DL-02 (otros),
        permitiendo artículo y descripción vacíos y datos complementarios.
        """
        lic_enfermedad = TipoLicencia.objects.create(
            codigo="ENF-01",
            articulo="Art. 340",
            descripcion="Afección común",
            cuadro_mensual="DL-01",
            tipo_novedad_excel="Licencia Salud",
            cantidad_duracion="Hasta 30 días",
        )
        lic_vacia = TipoLicencia.objects.create(
            codigo="OTRA-01",
            articulo="",
            descripcion="",
            cuadro_mensual="DL-02",
        )

        self.assertEqual(lic_enfermedad.cuadro_mensual, "DL-01")
        self.assertEqual(lic_vacia.cuadro_mensual, "DL-02")
        self.assertEqual(
            lic_vacia.situacion_revista_aplicable, "TIT,INT,SUP"
        )
        self.assertIn("(OTRA-01)", str(lic_vacia))

    def test_rn06_validacion_inasistencia_un_solo_dia(self):
        """
        RN-06: ValidationError si una inasistencia (AUSENTE, INA o categoría
        INASISTENCIA) abarca más de un día (fecha_hasta != fecha).
        """
        fecha_ini = datetime.date(2026, 10, 19)
        fecha_fin = datetime.date(2026, 10, 20)

        # Inasistencia válida: un solo día (mismo día)
        asistencia_valida = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_ini,
            fecha_hasta=fecha_ini,
            estado="AUSENTE",
        )
        asistencia_valida.full_clean()

        # Inasistencia inválida: más de un día con estado AUSENTE
        asistencia_invalida_ausente = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_ini,
            fecha_hasta=fecha_fin,
            estado="AUSENTE",
        )
        with self.assertRaises(ValidationError) as ctx:
            asistencia_invalida_ausente.full_clean()
        self.assertIn(
            "RN-06: Las inasistencias solamente pueden ser por un día.",
            str(ctx.exception),
        )

        # Inasistencia inválida con marca_diaria='INA'
        asistencia_invalida_marca = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_ini,
            fecha_hasta=fecha_fin,
            estado="JUSTIFICADO",
            marca_diaria="INA",
        )
        with self.assertRaises(ValidationError) as ctx:
            asistencia_invalida_marca.full_clean()
        self.assertIn(
            "RN-06: Las inasistencias solamente pueden ser por un día.",
            str(ctx.exception),
        )

        # Inasistencia inválida por tipo_licencia de categoría INASISTENCIA
        tipo_ina = TipoLicencia.objects.create(
            codigo="INA-SIMPLE",
            categoria="INASISTENCIA",
        )
        asistencia_invalida_tipo = RegistroAsistencia(
            docente=self.docente,
            fecha=fecha_ini,
            fecha_hasta=fecha_fin,
            estado="JUSTIFICADO",
            tipo_licencia=tipo_ina,
        )
        with self.assertRaises(ValidationError) as ctx:
            asistencia_invalida_tipo.full_clean()
        self.assertIn(
            "RN-06: Las inasistencias solamente pueden ser por un día.",
            str(ctx.exception),
        )

    def test_rn07_y_rn08_valores_por_defecto_oficina_y_anio_planilla(self):
        """
        RN-07 y RN-08: Verificar valores predeterminados oficina='1452'
        y anio_planilla=2026.
        """
        asistencia = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 22),
            estado="PRESENTE",
        )
        self.assertEqual(asistencia.oficina, "1452")
        self.assertEqual(asistencia.anio_planilla, 2026)
        self.assertEqual(asistencia.marca_diaria, "P")

    def test_rn09_guardado_desde_hasta_texto_y_es_designacion_vigente(self):
        """
        RN-09: Guardado de desde_texto='SIN INICIO', hasta_texto='SIN TERMINO'
        y evaluación de método es_designacion_vigente().
        """
        cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
        )
        self.assertEqual(cargo.desde_texto, "SIN INICIO")
        self.assertEqual(cargo.hasta_texto, "SIN TERMINO")
        self.assertTrue(cargo.es_designacion_vigente())

        # Fecha de referencia para pruebas
        ref = datetime.date(2026, 10, 21)

        # Vigente con fecha en el futuro (YYYY-MM-DD y DD/MM/YYYY)
        cargo.hasta_texto = "2026-12-31"
        self.assertTrue(cargo.es_designacion_vigente(ref))
        cargo.hasta_texto = "31/12/2026"
        self.assertTrue(cargo.es_designacion_vigente(ref))

        # No vigente si la fecha ya caducó
        cargo.hasta_texto = "2025-01-01"
        self.assertFalse(cargo.es_designacion_vigente(ref))
        cargo.hasta_texto = "01/01/2025"
        self.assertFalse(cargo.es_designacion_vigente(ref))

        # No vigente si activo=False
        cargo.activo = False
        cargo.hasta_texto = "SIN TERMINO"
        self.assertFalse(cargo.es_designacion_vigente(ref))

    def test_rn10_dia_no_laborable_y_trazabilidad_usuarios(self):
        """
        RN-10: Creación de DiaNoLaborable y trazabilidad de creado_por
        y modificado_por.
        """
        dia = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 12, 8),
            tipo="FERIADO",
            descripcion="Día de la Inmaculada Concepción",
            creado_por=self.user,
        )
        self.assertEqual(dia.tipo, "FERIADO")
        self.assertEqual(dia.creado_por, self.user)
        self.assertIn("Día de la Inmaculada Concepción", str(dia))

        # Trazabilidad en modelos del sistema
        self.assertEqual(self.docente.creado_por, self.user)
        self.docente.modificado_por = self.user
        self.docente.save()
        self.assertEqual(self.docente.modificado_por, self.user)

        # Unicidad por fecha en DiaNoLaborable
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DiaNoLaborable.objects.create(
                    fecha=datetime.date(2026, 12, 8),
                    tipo="ASUETO",
                    descripcion="Duplicado",
                )

    def test_catalogos_administrables_y_autorizacion_cargo(self):
        """
        Verifica campos de autorización, días laborables en texto y relación
        opcional a Carrera, CargoCatalogo y TipoAutorizacion.
        """
        cargo = CargoDocente.objects.create(
            docente=self.docente,
            carrera_ref=self.carrera,
            cargo_catalogo=self.cargo_catalogo,
            tipo_autorizacion=self.tipo_autorizacion,
            numero_autorizacion="145/26",
            anio_autorizacion=2026,
            organismo_emisor="MECCyT Chaco",
            dia_lunes="4 hs",
            dia_martes="X",
            dia_miercoles="3",
            dia_jueves="",
            dia_viernes="2 hs",
            observaciones="Carga histórica de planilla",
        )
        self.assertEqual(cargo.carrera_ref, self.carrera)
        self.assertEqual(cargo.cargo_catalogo, self.cargo_catalogo)
        self.assertEqual(cargo.tipo_autorizacion, self.tipo_autorizacion)
        self.assertEqual(cargo.numero_autorizacion, "145/26")
        self.assertEqual(cargo.dia_martes, "X")
        self.assertEqual(cargo.observaciones, "Carga histórica de planilla")


class EspecificacionFuncionalV2Tests(TestCase):
    """
    Pruebas unitarias de la Especificación Funcional v2.0 y Reglas de Negocio
    RN-01 a RN-11 del proyecto Zunin:
    - Catálogo de Licencias (IL-01 / IL-02, hoja_pdf, autocompletar)
    - Asistencia Diaria (cargo opcional, MARCA_DIARIA_CHOICES, justificación)
    - RenglonPlanillaMensual y motor generar_planilla_mes
    - Contador y Alerta de Inasistencias (Docente.obtener_resumen_inasistencias)
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bedel_v2",
            email="bedel.v2@iesetyfp.edu.ar",
            password="password123",
        )
        self.docente_a = Docente.objects.create(
            dni="20100100",
            apellido="Álvarez",
            nombre="Ana",
            sexo="F",
            creado_por=self.user,
        )
        self.docente_b = Docente.objects.create(
            dni="20200200",
            apellido="Benítez",
            nombre="Carlos",
            sexo="M",
            creado_por=self.user,
        )
        self.materia_prog = EspacioCurricular.objects.create(
            codigo="PR-101",
            nombre="Programación I",
            carrera="Desarrollo de Software",
            anio=1,
        )
        self.materia_bd = EspacioCurricular.objects.create(
            codigo="BD-102",
            nombre="Bases de Datos I",
            carrera="Desarrollo de Software",
            anio=1,
        )

        # Álvarez: Programación (Lunes 4hs, Miércoles 2hs)
        self.cargo_a1 = CargoDocente.objects.create(
            docente=self.docente_a,
            materia=self.materia_prog,
            horas_lunes=4,
            horas_martes=0,
            horas_miercoles=2,
            horas_jueves=0,
            horas_viernes=0,
            creado_por=self.user,
        )
        # Álvarez: Bases de Datos (Martes 3hs, Miércoles 3hs)
        self.cargo_a2 = CargoDocente.objects.create(
            docente=self.docente_a,
            materia=self.materia_bd,
            horas_lunes=0,
            horas_martes=3,
            horas_miercoles=3,
            horas_jueves=0,
            horas_viernes=0,
            creado_por=self.user,
        )
        # Benítez: Programación (Lunes 2hs, Martes 2hs)
        self.cargo_b1 = CargoDocente.objects.create(
            docente=self.docente_b,
            materia=self.materia_prog,
            horas_lunes=2,
            horas_martes=2,
            horas_miercoles=0,
            horas_jueves=0,
            horas_viernes=0,
            creado_por=self.user,
        )

        self.lic_enf = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="Art. 340-A",
            descripcion="Enfermedad de corto tratamiento",
            cuadro_mensual="IL-01",
            hoja_pdf="1-2",
            creado_por=self.user,
        )
        self.lic_mat = TipoLicencia.objects.create(
            codigo="LIC-341",
            articulo="Art. 341",
            descripcion="Maternidad",
            cuadro_mensual="IL-02",
            hoja_pdf="3-6",
            creado_por=self.user,
        )

    def test_tipo_licencia_cuadros_v2_y_hoja_pdf(self):
        """
        1. Catálogo de Licencias: choices IL-01, IL-02, DL-01, DL-02
        y campo hoja_pdf (default='1-2').
        """
        lic_def = TipoLicencia.objects.create(
            codigo="LIC-TEST-DEF",
            descripcion="Licencia Default",
        )
        self.assertEqual(lic_def.cuadro_mensual, "IL-02")
        self.assertEqual(lic_def.hoja_pdf, "1-2")

        # Verificar valores de choices permitidos
        lic_il1 = TipoLicencia.objects.create(
            codigo="LIC-IL1",
            cuadro_mensual="IL-01",
            hoja_pdf="1-2",
        )
        lic_dl1 = TipoLicencia.objects.create(
            codigo="LIC-DL1",
            cuadro_mensual="DL-01",
        )
        lic_dl2 = TipoLicencia.objects.create(
            codigo="LIC-DL2",
            cuadro_mensual="DL-02",
        )
        self.assertEqual(lic_il1.cuadro_mensual, "IL-01")
        self.assertEqual(lic_dl1.cuadro_mensual, "DL-01")
        self.assertEqual(lic_dl2.cuadro_mensual, "DL-02")

    def test_autocompletar_por_articulo_helper_y_classmethod(self):
        """
        1. Catálogo de Licencias: autocompletar_por_articulo retorna dict con
        código, descripción y cuadro (IL-01 o IL-02).
        """
        # Prueba con artículo de salud (IL-01)
        res_340a = autocompletar_por_articulo("340-A")
        self.assertEqual(res_340a["codigo"], "LIC-340A")
        self.assertEqual(res_340a["cuadro"], "IL-01")
        self.assertIn("Enfermedad", res_340a["descripcion"])

        # Prueba con método de clase en TipoLicencia
        res_cls = TipoLicencia.autocompletar_por_articulo("Art. 340-B")
        self.assertEqual(res_cls["codigo"], "LIC-340B")
        self.assertEqual(res_cls["cuadro"], "IL-01")

        # Prueba con artículo especial/permiso (IL-02)
        res_341 = autocompletar_por_articulo("341")
        self.assertEqual(res_341["codigo"], "LIC-341")
        self.assertEqual(res_341["cuadro"], "IL-02")

        res_duelo = autocompletar_por_articulo("Art. 344")
        self.assertEqual(res_duelo["codigo"], "LIC-344")
        self.assertEqual(res_duelo["cuadro"], "IL-02")
        self.assertEqual(res_duelo["descripcion"], "Duelo Familiar")

        # Prueba de coincidencia existente en base de datos
        res_db = autocompletar_por_articulo("Art. 340-A")
        self.assertEqual(res_db["codigo"], "LIC-340A")
        self.assertEqual(res_db["cuadro"], "IL-01")

        # Artículo desconocido o cadena vacía
        res_vacio = autocompletar_por_articulo("")
        self.assertEqual(res_vacio["cuadro"], "IL-02")

    def test_registro_asistencia_rf07_cargo_opcional_y_rf08_marcas(self):
        """
        2. RegistroAsistencia: cargo es opcional (null=True) a nivel agente/jornada
        y validación de marcas en MARCA_DIARIA_CHOICES.
        """
        asistencia = RegistroAsistencia.objects.create(
            docente=self.docente_a,
            cargo=None,  # RF-07: a nivel agente/jornada
            fecha=datetime.date(2026, 10, 5),
            estado="PRESENTE",
            marca_diaria="PR",  # RF-08: Presente
        )
        self.assertIsNone(asistencia.cargo)
        self.assertEqual(asistencia.marca_diaria, "PR")

        # Marcas válidas definidas
        choices_keys = [
            k for k, _ in RegistroAsistencia.MARCA_DIARIA_CHOICES
        ]
        for marca in ["P", "I", "LIC", "LT", "PR", "INA", "PERM"]:
            self.assertIn(marca, choices_keys)

    def test_justificar_con_formulario_rf09_rf11_exitoso(self):
        """
        2. RegistroAsistencia.justificar_con_formulario transiciona de 'I' a 'LIC'
        o a 'P', actualizando modificado_por y justifica=True.
        """
        # Caso 1: Transición de 'I' a 'LIC' con tipo de licencia médica
        asistencia = RegistroAsistencia.objects.create(
            docente=self.docente_a,
            fecha=datetime.date(2026, 10, 6),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            creado_por=self.user,
        )
        asistencia.justificar_con_formulario(
            nueva_marca="LIC",
            tipo_licencia=self.lic_enf,
            usuario=self.user,
        )
        asistencia.refresh_from_db()
        self.assertEqual(asistencia.marca_diaria, "LIC")
        self.assertEqual(asistencia.estado, "LICENCIA")
        self.assertEqual(asistencia.tipo_licencia, self.lic_enf)
        self.assertTrue(asistencia.justifica)
        self.assertEqual(asistencia.modificado_por, self.user)

        # Caso 2: Transición de 'I' a 'P' (Permiso)
        asistencia_p = RegistroAsistencia.objects.create(
            docente=self.docente_b,
            fecha=datetime.date(2026, 10, 6),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            creado_por=self.user,
        )
        asistencia_p.justificar_con_formulario(
            nueva_marca="P",
            usuario=self.user,
        )
        asistencia_p.refresh_from_db()
        self.assertEqual(asistencia_p.marca_diaria, "P")
        self.assertEqual(asistencia_p.estado, "JUSTIFICADO")
        self.assertTrue(asistencia_p.justifica)
        self.assertEqual(asistencia_p.modificado_por, self.user)

    def test_justificar_con_formulario_validaciones_y_errores(self):
        """
        2. Validaciones de justificar_con_formulario ante estados no inasistencia,
        marcas no permitidas o falta de TipoLicencia.
        """
        # Registro ya en estado PRESENTE no debe permitir justificación
        asistencia_presente = RegistroAsistencia.objects.create(
            docente=self.docente_a,
            fecha=datetime.date(2026, 10, 7),
            estado="PRESENTE",
            marca_diaria="PR",
        )
        with self.assertRaises(ValidationError):
            asistencia_presente.justificar_con_formulario("LIC", self.lic_enf)

        # Inasistencia sin especificar tipo_licencia para LIC
        inasistencia = RegistroAsistencia.objects.create(
            docente=self.docente_a,
            fecha=datetime.date(2026, 10, 8),
            estado="AUSENTE",
            marca_diaria="I",
        )
        with self.assertRaises(ValidationError):
            inasistencia.justificar_con_formulario("LIC", tipo_licencia=None)

        # Marca inválida no soportada
        with self.assertRaises(ValidationError):
            inasistencia.justificar_con_formulario("MARCA_INVENTADA")

    def test_resumen_inasistencias_rf18_acumulado_y_niveles_alerta(self):
        """
        4. Docente.obtener_resumen_inasistencias acumula inasistencias ('I') y
        permisos ('P') y retorna nivel de alerta 'NORMAL', 'PRECAUCION', 'CRITICO'.
        """
        docente = self.docente_a

        # Estado inicial: 0 inasistencias y 0 permisos -> NORMAL
        resumen = docente.obtener_resumen_inasistencias(anio=2026)
        self.assertEqual(resumen["inasistencias"], 0)
        self.assertEqual(resumen["permisos"], 0)
        self.assertEqual(resumen["total"], 0)
        self.assertEqual(resumen["total_acumulado"], 0)
        self.assertEqual(resumen["limite"], 10)
        self.assertEqual(resumen["restantes"], 10)
        self.assertEqual(resumen["nivel_alerta"], "NORMAL")

        # Cargar 4 inasistencias y 2 permisos (total 6 < 70% de 10) -> NORMAL
        for dia in range(1, 5):
            RegistroAsistencia.objects.create(
                docente=docente,
                fecha=datetime.date(2026, 3, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )
        for dia in range(5, 7):
            RegistroAsistencia.objects.create(
                docente=docente,
                fecha=datetime.date(2026, 3, dia),
                estado="JUSTIFICADO",
                marca_diaria="P",
            )

        resumen = docente.obtener_resumen_inasistencias(
            anio=2026, limite_reglamentario=10
        )
        self.assertEqual(resumen["inasistencias"], 4)
        self.assertEqual(resumen["permisos"], 2)
        self.assertEqual(resumen["total_acumulado"], 6)
        self.assertEqual(resumen["limite"], 10)
        self.assertEqual(resumen["restantes"], 4)
        self.assertEqual(resumen["nivel_alerta"], "NORMAL")

        # Agregar 1 inasistencia más (total 7 >= 70% de 10) -> PRECAUCION
        RegistroAsistencia.objects.create(
            docente=docente,
            fecha=datetime.date(2026, 3, 7),
            estado="AUSENTE",
            marca_diaria="I",
        )
        resumen = docente.obtener_resumen_inasistencias(
            anio=2026, limite_reglamentario=10
        )
        self.assertEqual(resumen["total_acumulado"], 7)
        self.assertEqual(resumen["restantes"], 3)
        self.assertEqual(resumen["nivel_alerta"], "PRECAUCION")

        # Agregar 3 inasistencias más (total 10 >= límite 10) -> CRITICO
        for dia in range(8, 11):
            RegistroAsistencia.objects.create(
                docente=docente,
                fecha=datetime.date(2026, 3, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )
        resumen = docente.obtener_resumen_inasistencias(
            anio=2026, limite_reglamentario=10
        )
        self.assertEqual(resumen["total_acumulado"], 10)
        self.assertEqual(resumen["restantes"], 0)
        self.assertEqual(resumen["nivel_alerta"], "CRITICO")

    def test_cargo_docente_obtener_horas_en_fecha_rf13(self):
        """
        RF-13: CargoDocente.obtener_horas_en_fecha calcula horas asignadas
        mirando weekday (0: Lunes a 4: Viernes), ya sea por horas numéricas,
        por texto con números o 'X', y 0 en fines de semana.
        """
        # Cargo con horas numéricas
        # self.cargo_a1: Lunes 4hs, Martes 0hs, Miércoles 2hs
        lunes = datetime.date(2026, 10, 5)  # Lunes
        martes = datetime.date(2026, 10, 6)  # Martes
        miercoles = datetime.date(2026, 10, 7)  # Miércoles
        sabado = datetime.date(2026, 10, 10)  # Sábado

        self.assertEqual(self.cargo_a1.obtener_horas_en_fecha(lunes), 4)
        self.assertEqual(self.cargo_a1.obtener_horas_en_fecha(martes), 0)
        self.assertEqual(self.cargo_a1.obtener_horas_en_fecha(miercoles), 2)
        self.assertEqual(self.cargo_a1.obtener_horas_en_fecha(sabado), 0)

        # Cargo con formato texto: dia_jueves="X" y dia_viernes="3 hs"
        cargo_texto = CargoDocente.objects.create(
            docente=self.docente_b,
            materia=self.materia_prog,
            dia_jueves="X",
            dia_viernes="3 hs",
            creado_por=self.user,
        )
        jueves = datetime.date(2026, 10, 8)  # Jueves
        viernes = datetime.date(2026, 10, 9)  # Viernes
        domingo = datetime.date(2026, 10, 11)  # Domingo

        self.assertEqual(cargo_texto.obtener_horas_en_fecha(jueves), 1)
        self.assertEqual(cargo_texto.obtener_horas_en_fecha(viernes), 3)
        self.assertEqual(cargo_texto.obtener_horas_en_fecha(domingo), 0)

    def test_explosion_periodo_licencia_rf12_rf13_rf14_rn10(self):
        """
        RF-12, RF-13, RF-14 y RN-10: Explosión automática de un período continuo
        de licencia (ej. 22/10 al 24/10) en múltiples renglones de
        RenglonPlanillaMensual según las materias y horas cátedra de esos días.
        """
        docente_c = Docente.objects.create(
            dni="11223344",
            apellido="Carrizo",
            nombre="Clara",
            sexo="F",
            creado_por=self.user,
        )
        # Cargo 1: Jueves 3 hs (22/10/2026 es Jueves)
        cargo_c1 = CargoDocente.objects.create(
            docente=docente_c,
            materia=self.materia_prog,
            horas_jueves=3,
            creado_por=self.user,
        )
        # Cargo 2: Viernes 4 hs (23/10/2026 es Viernes)
        cargo_c2 = CargoDocente.objects.create(
            docente=docente_c,
            materia=self.materia_bd,
            horas_viernes=4,
            creado_por=self.user,
        )

        # Cargar registros diarios continuos del 22/10 al 24/10 (Sábado)
        for f in [
            datetime.date(2026, 10, 22),
            datetime.date(2026, 10, 23),
            datetime.date(2026, 10, 24),
        ]:
            RegistroAsistencia.objects.create(
                docente=docente_c,
                cargo=None,
                fecha=f,
                estado="LICENCIA",
                marca_diaria="LIC",
                tipo_licencia=self.lic_enf,
                creado_por=self.user,
            )

        renglones = RenglonPlanillaMensual.generar_planilla_mes(
            mes=10, anio=2026, usuario=self.user
        )

        renglones_carrizo = [
            r for r in renglones if r.docente == docente_c
        ]
        self.assertEqual(len(renglones_carrizo), 2)

        renglon_prog = next(
            r for r in renglones_carrizo if r.cargo == cargo_c1
        )
        renglon_bd = next(
            r for r in renglones_carrizo if r.cargo == cargo_c2
        )

        # Mismo número correlativo de Disposición (RN-11)
        self.assertEqual(
            renglon_prog.numero_instrumento, renglon_bd.numero_instrumento
        )
        self.assertEqual(renglon_prog.cuadro, "IL-01")
        self.assertEqual(renglon_bd.cuadro, "IL-01")
        self.assertEqual(renglon_prog.desde, datetime.date(2026, 10, 22))
        self.assertEqual(renglon_prog.hasta, datetime.date(2026, 10, 24))
        self.assertEqual(renglon_bd.desde, datetime.date(2026, 10, 22))
        self.assertEqual(renglon_bd.hasta, datetime.date(2026, 10, 24))
        self.assertEqual(renglon_prog.horas_afectadas, 3)
        self.assertEqual(renglon_bd.horas_afectadas, 4)

    def test_generar_planilla_mes_rf12_a_rf16_rn10_rn11(self):
        """
        3. Desglose Mensual por Materia y Horas (RenglonPlanillaMensual):
        - Agrupamiento de bloques continuos.
        - Desglose por materia sumando sus horas cátedra (RF-12, RF-13).
        - Asignación de único N° de Disposición correlativo por docente/bloque
          ordenando alfabéticamente los agentes por apellido (RF-16, RN-11).
        """
        # Docente Álvarez (Apellido 'Álvarez' -> primer lugar alfabético)
        # Bloque continuo del 5 al 7 de Octubre de 2026 (Lunes a Miércoles)
        # Cargo A1 (Prog): Lunes 4hs, Miércoles 2hs -> Total 6hs
        # Cargo A2 (BD): Martes 3hs, Miércoles 3hs -> Total 6hs
        for fecha in [
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 6),
            datetime.date(2026, 10, 7),
        ]:
            RegistroAsistencia.objects.create(
                docente=self.docente_a,
                cargo=None,
                fecha=fecha,
                estado="LICENCIA",
                marca_diaria="LIC",
                tipo_licencia=self.lic_enf,
                creado_por=self.user,
            )

        # Docente Benítez (Apellido 'Benítez' -> segundo lugar alfabético)
        # Día Lunes 19 de Octubre de 2026
        # Cargo B1 (Prog): Lunes 2hs -> Total 2hs
        RegistroAsistencia.objects.create(
            docente=self.docente_b,
            cargo=None,
            fecha=datetime.date(2026, 10, 19),
            estado="AUSENTE",
            marca_diaria="I",
            creado_por=self.user,
        )

        renglones = RenglonPlanillaMensual.generar_planilla_mes(
            mes=10, anio=2026, usuario=self.user
        )

        # Se generan 3 renglones en total: 2 para Álvarez y 1 para Benítez
        self.assertEqual(len(renglones), 3)

        renglones_alvarez = [
            r for r in renglones if r.docente == self.docente_a
        ]
        renglones_benitez = [
            r for r in renglones if r.docente == self.docente_b
        ]

        self.assertEqual(len(renglones_alvarez), 2)
        self.assertEqual(len(renglones_benitez), 1)

        # Verificación del orden alfabético y correlativo único de Disposición (RN-11)
        # Álvarez debe recibir la primera disposición: 001/2026
        for renglon in renglones_alvarez:
            self.assertEqual(renglon.numero_instrumento, "001/2026")
            self.assertEqual(renglon.tipo_instrumento, "DISPOSICION")
            self.assertEqual(renglon.cuadro, "IL-01")
            self.assertEqual(renglon.oficina, "1452")
            self.assertEqual(renglon.desde, datetime.date(2026, 10, 5))
            self.assertEqual(renglon.hasta, datetime.date(2026, 10, 7))
            self.assertEqual(renglon.creado_por, self.user)

        # Verificar sumatoria de horas afectadas por materia para Álvarez (RF-13)
        renglon_prog = next(
            r for r in renglones_alvarez if r.cargo == self.cargo_a1
        )
        renglon_bd = next(
            r for r in renglones_alvarez if r.cargo == self.cargo_a2
        )
        self.assertEqual(renglon_prog.horas_afectadas, 6)
        self.assertEqual(renglon_bd.horas_afectadas, 6)

        # Benítez debe recibir la segunda disposición: 002/2026
        renglon_b = renglones_benitez[0]
        self.assertEqual(renglon_b.numero_instrumento, "002/2026")
        self.assertEqual(renglon_b.cuadro, "IL-02")
        self.assertEqual(renglon_b.horas_afectadas, 2)
        self.assertEqual(renglon_b.desde, datetime.date(2026, 10, 19))
        self.assertEqual(renglon_b.hasta, datetime.date(2026, 10, 19))

        # Verificar que los registros diarios actualizaron su número de disposición
        regs_alvarez = RegistroAsistencia.objects.filter(docente=self.docente_a)
        for r in regs_alvarez:
            self.assertEqual(r.numero_disposicion, "001/2026")

        reg_benitez = RegistroAsistencia.objects.get(docente=self.docente_b)
        self.assertEqual(reg_benitez.numero_disposicion, "002/2026")

    def test_renglon_planilla_mensual_representacion_y_campos(self):
        """
        Verifica campos del modelo RenglonPlanillaMensual y su formato __str__.
        """
        renglon = RenglonPlanillaMensual.objects.create(
            docente=self.docente_a,
            cargo=self.cargo_a1,
            tipo_licencia=self.lic_enf,
            cuadro="IL-01",
            mes=10,
            anio=2026,
            oficina="1452",
            desde=datetime.date(2026, 10, 5),
            hasta=datetime.date(2026, 10, 7),
            horas_afectadas=6,
            marca_origen="LIC",
            tipo_instrumento="DISPOSICION",
            numero_instrumento="001/2026",
            creado_por=self.user,
        )
        self.assertEqual(renglon.anio, 2026)
        self.assertEqual(renglon.oficina, "1452")
        self.assertEqual(renglon.marca_origen, "LIC")
        self.assertIn("Álvarez, Ana", str(renglon))
        self.assertIn("6 hs", str(renglon))
        self.assertIn("001/2026", str(renglon))
        self.assertIsNotNone(renglon.creado_en)
        self.assertIsNotNone(renglon.actualizado_en)
        self.assertEqual(renglon.creado_el, renglon.creado_en)
        self.assertEqual(renglon.modificado_el, renglon.actualizado_en)
