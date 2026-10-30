"""
Pruebas automatizadas para los formularios del módulo de Licencias (apps.licencias.forms).
"""

import datetime
from django.test import TestCase
from apps.asistencia.models import RegistroAsistencia
from apps.licencias.forms import JustificacionDiferidaForm, TipoLicenciaSearchForm
from apps.licencias.models import TipoLicencia
from apps.personal.models import Docente


class LicenciasFormsTests(TestCase):
    def setUp(self):
        self.docente = Docente.objects.create(
            dni="27999111",
            apellido="RAMÍREZ",
            nombre="Estela",
            sexo="F",
        )
        self.lic_enf = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.lic_mat = TipoLicencia.objects.create(
            codigo="LIC-341",
            articulo="341",
            descripcion="Licencia por Maternidad",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
            cuadro_mensual="IL-02",
            activo=True,
        )
        self.lic_inactiva = TipoLicencia.objects.create(
            codigo="LIC-VIEJA",
            articulo="999",
            descripcion="Licencia Histórica Inactiva",
            categoria="PERMISO",
            forma_pago="SIN_GOCE",
            cuadro_mensual="IL-02",
            activo=False,
        )

    # --- Pruebas TipoLicenciaSearchForm ---

    def test_search_form_sin_filtros_retorna_todos(self):
        """Búsqueda sin parámetros retorna el catálogo completo."""
        form = TipoLicenciaSearchForm(data={})
        self.assertTrue(form.is_valid())
        resultados = form.filtrar()
        self.assertEqual(resultados.count(), 3)

    def test_search_form_filtra_por_texto_q(self):
        """Búsqueda por texto filtra en código, artículo o descripción."""
        form = TipoLicenciaSearchForm(data={"q": "340-A"})
        self.assertTrue(form.is_valid())
        resultados = form.filtrar()
        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first().codigo, "LIC-340A")

    def test_search_form_filtra_por_cuadro_y_activo(self):
        """Búsqueda combinando cuadro mensual y estado activo."""
        form = TipoLicenciaSearchForm(data={"cuadro_mensual": "IL-02", "activo": "1"})
        self.assertTrue(form.is_valid())
        resultados = form.filtrar()
        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first().codigo, "LIC-341")

    # --- Pruebas JustificacionDiferidaForm ---

    def test_justificacion_diferida_form_valida_licencia(self):
        """RF-09, RF-11: Justificación exitosa de inasistencia ('I') con licencia médica."""
        inasistencia = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 15),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        form = JustificacionDiferidaForm(
            data={
                "registro": inasistencia.pk,
                "nueva_marca": "LIC",
                "tipo_licencia": self.lic_enf.pk,
                "numero_disposicion": "Disp. 055/26",
                "observaciones": "Certificado médico presentado en Bedelía",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        registro_actualizado = form.save()

        self.assertEqual(registro_actualizado.estado, "LICENCIA")
        self.assertEqual(registro_actualizado.marca_diaria, "LIC")
        self.assertEqual(registro_actualizado.tipo_licencia, self.lic_enf)
        self.assertTrue(registro_actualizado.justifica)
        self.assertEqual(registro_actualizado.numero_disposicion, "Disp. 055/26")
        self.assertIn("Certificado médico", registro_actualizado.observaciones)

    def test_justificacion_diferida_form_valida_permiso(self):
        """Justificación exitosa como Permiso ('P') sin necesidad de tipo de licencia."""
        inasistencia = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 16),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        form = JustificacionDiferidaForm(
            data={
                "registro": inasistencia.pk,
                "nueva_marca": "P",
                "observaciones": "Nota firmada por Rectoría",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        registro_actualizado = form.save()

        self.assertEqual(registro_actualizado.estado, "JUSTIFICADO")
        self.assertEqual(registro_actualizado.marca_diaria, "P")
        self.assertTrue(registro_actualizado.justifica)

    def test_justificacion_diferida_licencia_sin_tipo_rechazada(self):
        """Rechaza justificar con marca LIC si no se suministra el Tipo de Licencia."""
        inasistencia = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 17),
            estado="AUSENTE",
            marca_diaria="I",
        )
        form = JustificacionDiferidaForm(
            data={
                "registro": inasistencia.pk,
                "nueva_marca": "LIC",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn("Debe especificar un Tipo de Licencia", form.errors["tipo_licencia"][0])

    def test_justificacion_diferida_registro_no_inasistencia_rechazado(self):
        """Rechaza intentar justificar un registro que ya figura como PRESENTE."""
        presente = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 18),
            estado="PRESENTE",
            marca_diaria="PR",
        )
        form = JustificacionDiferidaForm(
            data={
                "registro": presente.pk,
                "nueva_marca": "P",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("registro", form.errors)
        self.assertIn("Solo se pueden justificar registros en estado de inasistencia", form.errors["registro"][0])
