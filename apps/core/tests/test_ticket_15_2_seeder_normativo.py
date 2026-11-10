"""
Pruebas automatizadas para Ticket 15.2:
Carga inicial (Seeder) del Catálogo Normativo completo según Ley 647-E
(Estatuto del Docente del Chaco) para Titular (TIT), Interino (INT) y Suplente (SUP).
"""

from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from apps.core.seeder import poblar_catalogo_normativo_ley647e
from apps.licencias.models import TipoLicencia


class SeederCatalogoNormativoLey647ETests(TestCase):
    """
    Suite de validación exhaustiva para el Seeder Normativo de la Ley 647-E.
    """

    def test_seeder_puebla_catalogo_completo(self):
        """
        Verifica que el seeder normativo cree todos los registros esperados
        y cubra los tres regímenes de revista (TIT, INT, SUP).
        """
        resumen = poblar_catalogo_normativo_ley647e()

        self.assertGreaterEqual(resumen["total"], 70)
        self.assertEqual(resumen["creados"], resumen["total"])
        self.assertEqual(resumen["actualizados"], 0)

        total_db = TipoLicencia.objects.count()
        self.assertGreaterEqual(total_db, 70)

        # Regímenes presentes
        regimenes = set(
            TipoLicencia.objects.values_list("regimen", flat=True)
        )
        self.assertIn("TIT", regimenes)
        self.assertIn("INT", regimenes)
        self.assertIn("SUP", regimenes)

        # Categorías presentes
        categorias = set(
            TipoLicencia.objects.values_list("categoria", flat=True)
        )
        self.assertIn("Ordinaria", categorias)
        self.assertIn("Extraordinaria", categorias)
        self.assertIn("Permiso", categorias)

    def test_catalogo_normativo_personal_titular(self):
        """
        Valida que el personal titular cuente con sus licencias ordinarias,
        extraordinarias y permisos conforme Arts. 307 - 318, 320.
        """
        poblar_catalogo_normativo_ley647e()

        # Ordinarias: Descanso anual (Art. 307)
        descanso = TipoLicencia.objects.get(codigo="TIT-ORD-307")
        self.assertEqual(descanso.regimen, "TIT")
        self.assertEqual(descanso.categoria, "Ordinaria")
        self.assertEqual(descanso.duracion_maxima, 60)
        self.assertEqual(descanso.unidad, "Corridos")
        self.assertEqual(descanso.forma_goce, "100%")
        self.assertTrue(descanso.goce_haberes)

        # Enfermedad común (Art. 308 - 45 días continuos o discontinuos)
        enf_comun = TipoLicencia.objects.get(codigo="TIT-ORD-308")
        self.assertEqual(enf_comun.duracion_maxima, 45)
        self.assertEqual(enf_comun.unidad, "Corridos")
        self.assertEqual(enf_comun.cuadro_mensual, "IL-01")

        # Largo tratamiento (Art. 309 - 2 años al 100%, 1 año al 50%)
        largo_100 = TipoLicencia.objects.get(codigo="TIT-ORD-309-100")
        self.assertEqual(largo_100.duracion_maxima, 730)
        self.assertEqual(largo_100.forma_goce, "100%")
        self.assertEqual(largo_100.forma_pago, "CON_GOCE")

        largo_50 = TipoLicencia.objects.get(codigo="TIT-ORD-309-50")
        self.assertEqual(largo_50.duracion_maxima, 365)
        self.assertEqual(largo_50.forma_goce, "50%")
        self.assertEqual(largo_50.forma_pago, "CINCUENTA_PORCIENTO")

        # Accidente / ocupacional (Art. 310 - 2 años al 100%, 1 año al 50%)
        acc_100 = TipoLicencia.objects.get(codigo="TIT-ORD-310-100")
        self.assertEqual(acc_100.duracion_maxima, 730)
        self.assertEqual(acc_100.forma_goce, "100%")

        acc_50 = TipoLicencia.objects.get(codigo="TIT-ORD-310-50")
        self.assertEqual(acc_50.duracion_maxima, 365)
        self.assertEqual(acc_50.forma_goce, "50%")

        # Gravidez / Maternidad (Art. 312 - 180 días con ampliaciones)
        mat = TipoLicencia.objects.get(codigo="TIT-ORD-312-MAT")
        self.assertEqual(mat.duracion_maxima, 180)
        self.assertEqual(mat.unidad, "Corridos")

        mat_mult = TipoLicencia.objects.get(codigo="TIT-ORD-312-MULT")
        self.assertEqual(mat_mult.duracion_maxima, 30)

        mat_disc = TipoLicencia.objects.get(codigo="TIT-ORD-312-DISC")
        self.assertEqual(mat_disc.duracion_maxima, 90)

        mat_def = TipoLicencia.objects.get(codigo="TIT-ORD-312-DEF")
        self.assertEqual(mat_def.duracion_maxima, 60)

        mat_pat = TipoLicencia.objects.get(codigo="TIT-ORD-312-PAT")
        self.assertEqual(mat_pat.duracion_maxima, 180)

        # Familiar enfermo (Art. 314 - 28 días prorrogables por 30)
        fam = TipoLicencia.objects.get(codigo="TIT-ORD-314-FAM")
        self.assertEqual(fam.duracion_maxima, 28)
        fam_ext = TipoLicencia.objects.get(codigo="TIT-ORD-314-EXT")
        self.assertEqual(fam_ext.duracion_maxima, 30)

        # Adopción (Art. 316 - 180 días)
        adop = TipoLicencia.objects.get(codigo="TIT-ORD-316-ADOP")
        self.assertEqual(adop.duracion_maxima, 180)

        # Extraordinarias (Art. 318):
        # Asuntos particulares: sin goce, 1 año antigüedad, 1 año por decenio
        as_part = TipoLicencia.objects.get(codigo="TIT-EXT-318-A")
        self.assertEqual(as_part.categoria, "Extraordinaria")
        self.assertEqual(as_part.forma_goce, "Sin goce")
        self.assertFalse(as_part.goce_haberes)
        self.assertEqual(as_part.duracion_maxima, 365)
        self.assertEqual(as_part.periodo_tope, "Decenio")
        self.assertEqual(as_part.antiguedad_minima_meses, 12)

        # Fuerza mayor: hasta 90 días sin goce
        fm = TipoLicencia.objects.get(codigo="TIT-EXT-318-B")
        self.assertEqual(fm.duracion_maxima, 90)
        self.assertEqual(fm.forma_goce, "Sin goce")

        # Perfeccionamiento: 3 años con goce con 3 años antigüedad
        perf_largo = TipoLicencia.objects.get(codigo="TIT-EXT-318-C-MAY")
        self.assertEqual(perf_largo.duracion_maxima, 1095)
        self.assertEqual(perf_largo.forma_goce, "100%")
        self.assertEqual(perf_largo.antiguedad_minima_meses, 36)

        # Perfeccionamiento: <20 días con goce sin antigüedad
        perf_corto = TipoLicencia.objects.get(codigo="TIT-EXT-318-C-MEN")
        self.assertEqual(perf_corto.duracion_maxima, 20)
        self.assertEqual(perf_corto.antiguedad_minima_meses, 0)
        self.assertEqual(perf_corto.unidad, "Laborables")

        # Matrimonio: 10 días hábiles
        matr = TipoLicencia.objects.get(codigo="TIT-EXT-318-G")
        self.assertEqual(matr.duracion_maxima, 10)
        self.assertEqual(matr.unidad, "Hábiles")
        self.assertEqual(matr.tope_anual, 10)
        self.assertEqual(matr.cantidad_duracion, "10 días hábiles")

        # Exámenes preventivos: 1 día
        prev = TipoLicencia.objects.get(codigo="TIT-EXT-318-H")
        self.assertEqual(prev.duracion_maxima, 1)

        # Rendir exámenes: hasta 30 días laborales
        exam = TipoLicencia.objects.get(codigo="TIT-EXT-318-I")
        self.assertEqual(exam.duracion_maxima, 30)
        self.assertEqual(exam.unidad, "Laborables")

        # Concursos: 15 días hábiles
        conc = TipoLicencia.objects.get(codigo="TIT-EXT-318-J")
        self.assertEqual(conc.duracion_maxima, 15)
        self.assertEqual(conc.unidad, "Hábiles")

        # Incompatibilidad: hasta 2 años sin goce
        incomp = TipoLicencia.objects.get(codigo="TIT-EXT-318-K")
        self.assertEqual(incomp.duracion_maxima, 730)
        self.assertEqual(incomp.forma_goce, "Sin goce")

        # Violencia de género: con goce
        viol = TipoLicencia.objects.get(codigo="TIT-EXT-318-N")
        self.assertEqual(viol.forma_goce, "100%")
        self.assertTrue(viol.goce_haberes)

        # Permisos (Art. 320):
        # Nacimiento: 15 días hábiles, 30 si prematuro/múltiple
        nac = TipoLicencia.objects.get(codigo="TIT-PER-320-A")
        self.assertEqual(nac.categoria, "Permiso")
        self.assertEqual(nac.duracion_maxima, 15)
        self.assertEqual(nac.unidad, "Hábiles")

        nac_m = TipoLicencia.objects.get(codigo="TIT-PER-320-A-MULT")
        self.assertEqual(nac_m.duracion_maxima, 30)
        self.assertEqual(nac_m.unidad, "Hábiles")

        # Adopción guardador: 30 días corridos
        guard = TipoLicencia.objects.get(codigo="TIT-PER-320-B")
        self.assertEqual(guard.duracion_maxima, 30)
        self.assertEqual(guard.unidad, "Corridos")

        # Donación de sangre: 1 día
        sang = TipoLicencia.objects.get(codigo="TIT-PER-320-C")
        self.assertEqual(sang.duracion_maxima, 1)

        # Lactancia: 60 min diarios
        lact = TipoLicencia.objects.get(codigo="TIT-PER-320-D")
        self.assertEqual(lact.duracion_maxima, 1)
        self.assertEqual(lact.unidad, "Horas")

        # Duelo 1er grado: 8 días
        duel_1 = TipoLicencia.objects.get(codigo="TIT-PER-320-F-1")
        self.assertEqual(duel_1.duracion_maxima, 8)

        # Natalicio: 1 día
        nat = TipoLicencia.objects.get(codigo="TIT-PER-320-H")
        self.assertEqual(nat.duracion_maxima, 1)

    def test_catalogo_normativo_personal_interino(self):
        """
        Valida que el personal interino cuente con sus reglas y topes
        conforme Arts. 329 al 337.
        """
        poblar_catalogo_normativo_ley647e()

        # Descanso proporcional
        desc = TipoLicencia.objects.get(codigo="INT-ORD-329")
        self.assertEqual(desc.regimen, "INT")
        self.assertEqual(desc.duracion_maxima, 60)

        # Enfermedad común: 30 días con antigüedad >= 4 meses, 10 con < 4 meses
        enf_may = TipoLicencia.objects.get(codigo="INT-ORD-330-MAY")
        self.assertEqual(enf_may.regimen, "INT")
        self.assertEqual(enf_may.duracion_maxima, 30)
        self.assertEqual(enf_may.antiguedad_minima_meses, 4)

        enf_men = TipoLicencia.objects.get(codigo="INT-ORD-330-MEN")
        self.assertEqual(enf_men.duracion_maxima, 10)
        self.assertEqual(enf_men.antiguedad_minima_meses, 0)

        # Accidente: 730 días 100%, 365 días 50%
        acc_100 = TipoLicencia.objects.get(codigo="INT-ORD-331-100")
        self.assertEqual(acc_100.duracion_maxima, 730)
        self.assertEqual(acc_100.forma_goce, "100%")

        acc_50 = TipoLicencia.objects.get(codigo="INT-ORD-331-50")
        self.assertEqual(acc_50.duracion_maxima, 365)
        self.assertEqual(acc_50.forma_goce, "50%")

        # Maternidad y Adopción: 180 días corridos
        mat = TipoLicencia.objects.get(codigo="INT-ORD-332-MAT")
        self.assertEqual(mat.duracion_maxima, 180)

        adop = TipoLicencia.objects.get(codigo="INT-ORD-333-ADOP")
        self.assertEqual(adop.duracion_maxima, 180)

        # Familiar enfermo: requiere 4 meses, hasta 10 días
        fam = TipoLicencia.objects.get(codigo="INT-ORD-334-FAM")
        self.assertEqual(fam.duracion_maxima, 10)
        self.assertEqual(fam.antiguedad_minima_meses, 4)

        # Exámenes de estudio: hasta 16 días laborales
        exam = TipoLicencia.objects.get(codigo="INT-EXT-335-EXAM")
        self.assertEqual(exam.duracion_maxima, 16)
        self.assertEqual(exam.unidad, "Laborables")

        # Matrimonio: 10 días hábiles
        matr = TipoLicencia.objects.get(codigo="INT-EXT-335-MATR")
        self.assertEqual(matr.duracion_maxima, 10)
        self.assertEqual(matr.unidad, "Hábiles")
        self.assertEqual(matr.tope_anual, 10)
        self.assertEqual(matr.cantidad_duracion, "10 días hábiles")

    def test_catalogo_normativo_personal_suplente(self):
        """
        Valida que el personal suplente cuente con sus reglas y topes
        conforme Arts. 338 al 346.
        """
        poblar_catalogo_normativo_ley647e()

        # Descanso proporcional
        desc = TipoLicencia.objects.get(codigo="SUP-ORD-338")
        self.assertEqual(desc.regimen, "SUP")

        # Enfermedad común: 15 días con antigüedad >= 4 meses, 5 con < 4 meses
        enf_may = TipoLicencia.objects.get(codigo="SUP-ORD-339-MAY")
        self.assertEqual(enf_may.regimen, "SUP")
        self.assertEqual(enf_may.duracion_maxima, 15)
        self.assertEqual(enf_may.antiguedad_minima_meses, 4)

        enf_men = TipoLicencia.objects.get(codigo="SUP-ORD-339-MEN")
        self.assertEqual(enf_men.duracion_maxima, 5)
        self.assertEqual(enf_men.antiguedad_minima_meses, 0)

        # Accidente: hasta 6 meses al 100% (180 días) y 3 meses al 50% (90 días)
        acc_100 = TipoLicencia.objects.get(codigo="SUP-ORD-340-100")
        self.assertEqual(acc_100.duracion_maxima, 180)
        self.assertEqual(acc_100.forma_goce, "100%")

        acc_50 = TipoLicencia.objects.get(codigo="SUP-ORD-340-50")
        self.assertEqual(acc_50.duracion_maxima, 90)
        self.assertEqual(acc_50.forma_goce, "50%")

        # Maternidad y Adopción: 180 días corridos con extensión de cobro
        mat = TipoLicencia.objects.get(codigo="SUP-ORD-341-MAT")
        self.assertEqual(mat.duracion_maxima, 180)

        adop = TipoLicencia.objects.get(codigo="SUP-ORD-342-ADOP")
        self.assertEqual(adop.duracion_maxima, 180)

        # Familiar enfermo: requiere 4 meses, 5 días corridos
        fam = TipoLicencia.objects.get(codigo="SUP-ORD-343-FAM")
        self.assertEqual(fam.duracion_maxima, 5)
        self.assertEqual(fam.antiguedad_minima_meses, 4)

        # Perfeccionamiento: hasta 10 días laborales
        perf = TipoLicencia.objects.get(codigo="SUP-EXT-344-PERF")
        self.assertEqual(perf.duracion_maxima, 10)
        self.assertEqual(perf.unidad, "Laborables")

        # Matrimonio: 2 días hábiles
        matr = TipoLicencia.objects.get(codigo="SUP-EXT-344-MATR")
        self.assertEqual(matr.duracion_maxima, 2)
        self.assertEqual(matr.unidad, "Hábiles")
        self.assertEqual(matr.tope_anual, 2)
        self.assertEqual(matr.cantidad_duracion, "2 días hábiles")

    def test_seeder_normativo_idempotencia(self):
        """
        Verifica que ejecutar el seeder normativo múltiples veces
        no genere duplicados ni modifique la integridad de los registros.
        """
        res1 = poblar_catalogo_normativo_ley647e()
        total_1 = TipoLicencia.objects.count()

        res2 = poblar_catalogo_normativo_ley647e()
        total_2 = TipoLicencia.objects.count()

        self.assertEqual(total_1, total_2)
        self.assertEqual(res2["creados"], 0)
        self.assertEqual(res2["actualizados"], res1["total"])

    def test_management_command_poblar_catalogo_normativo(self):
        """
        Verifica que el comando 'python manage.py poblar_catalogo_normativo'
        se ejecute exitosamente y reporte las estadísticas en stdout.
        """
        out = StringIO()
        call_command("poblar_catalogo_normativo", stdout=out)
        output = out.getvalue()

        self.assertIn("Iniciando carga del Catálogo Normativo", output)
        self.assertIn("Catálogo Normativo cargado exitosamente", output)
        self.assertIn("Total especificaciones:", output)
        self.assertGreaterEqual(TipoLicencia.objects.count(), 70)

    def test_vista_catalogo_muestra_tope_y_duracion_correctamente(self):
        """
        Verifica que la vista TipoLicenciaListView renderice los días hábiles
        y el período tope para INT-EXT-335-MATR en vez de 'Sin tope'.
        """
        poblar_catalogo_normativo_ley647e()

        user = get_user_model().objects.create_user(
            username="testuser",
            password="testpassword",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("licencias:tipolicencia_list"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn("INT-EXT-335-MATR", content)
        self.assertIn("10 días hábiles", content)
        self.assertIn("por hecho", content)
