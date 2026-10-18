import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from gestion_asistencia.apps import GestionAsistenciaConfig
from gestion_asistencia.models import (
    Docente,
    EspacioCurricular,
    CargoDocente,
    TipoLicencia,
    RegistroAsistencia,
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
        expected = "Art. 340-A (LIC-340A) - Enfermedad de corto tratamiento [C/Goce]"
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
        """Crea un registro de asistencia en LICENCIA con tipo_licencia asignado."""
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
        """Lanza ValidationError si estado es LICENCIA y no se asigna tipo_licencia."""
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 22),
            estado="LICENCIA",
        )
        with self.assertRaises(ValidationError):
            asistencia.full_clean()

    def test_validacion_presente_con_tipo_licencia(self):
        """Lanza ValidationError si estado es PRESENTE y se adjunta tipo_licencia."""
        asistencia = RegistroAsistencia(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 23),
            estado="PRESENTE",
            tipo_licencia=self.tipo_licencia,
        )
        with self.assertRaises(ValidationError):
            asistencia.full_clean()

    def test_unicidad_docente_fecha(self):
        """Verifica que no se dupliquen registros de asistencia en la misma fecha."""
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
