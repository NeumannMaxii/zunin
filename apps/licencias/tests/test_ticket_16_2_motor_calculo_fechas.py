"""
Pruebas automatizadas para el Ticket 16.2: Motor de cálculo de fechas y unidades.

Criterio de Aceptación:
Una licencia de 5 días hábiles calculada un viernes determina correctamente la fecha
de finalización y reintegro saltando el fin de semana.
"""

import datetime
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.asistencia.models import DiaNoLaborable
from apps.licencias.calculador import (
    CalculoFechasLicencia,
    MotorCalculoLicencia,
    UNIDAD_CORRIDOS,
    UNIDAD_HABILES,
    calcular_fecha_reintegro,
    calcular_fechas_licencia,
    contar_dias_corridos,
    contar_dias_habiles,
    es_dia_habil,
    normalizar_unidad,
    obtener_siguiente_dia_habil,
    parse_date_safe,
)
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.personal.models import Docente


class MotorCalculoFechasTests(TestCase):
    """
    Pruebas unitarias de cálculo de fechas, días hábiles/corridos y reintegro.
    """

    def setUp(self):
        # Viernes 13 de Noviembre de 2026
        self.viernes = datetime.date(2026, 11, 13)
        self.sabado = datetime.date(2026, 11, 14)
        self.domingo = datetime.date(2026, 11, 15)
        self.lunes = datetime.date(2026, 11, 16)
        self.martes = datetime.date(2026, 11, 17)
        self.miercoles = datetime.date(2026, 11, 18)
        self.jueves = datetime.date(2026, 11, 19)
        self.viernes_sgte = datetime.date(2026, 11, 20)
        self.lunes_sgte = datetime.date(2026, 11, 23)

    def test_criterio_aceptacion_oficial_5_dias_habiles_un_viernes(self):
        """
        Criterio de Aceptación Ticket 16.2:
        Una licencia de 5 días hábiles calculada un viernes determina
        correctamente la fecha de finalización (jueves) y reintegro (viernes)
        saltando el fin de semana.
        """
        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,  # 2026-11-13 (Viernes)
            dias=5,
            unidad=UNIDAD_HABILES,
            feriados=set(),
        )

        # 5 días hábiles:
        # Día 1: Viernes 13
        # Sábado 14 / Domingo 15: Fin de semana (Omitidos)
        # Día 2: Lunes 16
        # Día 3: Martes 17
        # Día 4: Miércoles 18
        # Día 5: Jueves 19
        self.assertEqual(resultado.fecha_desde, self.viernes)
        self.assertEqual(resultado.fecha_hasta, self.jueves)  # 2026-11-19
        self.assertEqual(resultado.fecha_reintegro, self.viernes_sgte)  # 2026-11-20
        self.assertEqual(resultado.dias_consumidos, 5)
        self.assertEqual(resultado.dias_habiles, 5)
        self.assertEqual(resultado.dias_corridos, 7)  # 13 al 19 inclusive
        self.assertEqual(resultado.fines_de_semana, 2)  # Sábado 14 y Domingo 15
        self.assertEqual(resultado.unidad, UNIDAD_HABILES)

    def test_reintegro_cuando_finaliza_un_viernes_salta_fin_de_semana(self):
        """
        Si una licencia finaliza un viernes, la fecha de reintegro debe ser
        el lunes siguiente, saltando sábado y domingo.
        """
        # 5 días hábiles iniciando lunes 16 -> finaliza viernes 20
        resultado = calcular_fechas_licencia(
            fecha_desde=self.lunes,
            dias=5,
            unidad=UNIDAD_HABILES,
            feriados=set(),
        )

        self.assertEqual(resultado.fecha_hasta, self.viernes_sgte)  # Viernes 20
        self.assertEqual(resultado.fecha_reintegro, self.lunes_sgte)  # Lunes 23
        self.assertEqual(resultado.dias_consumidos, 5)
        self.assertEqual(resultado.dias_habiles, 5)

    def test_licencia_un_solo_dia_habil_un_viernes(self):
        """
        Una licencia de 1 día hábil un viernes finaliza el mismo viernes y
        su reintegro es el lunes inmediato posterior.
        """
        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,
            dias=1,
            unidad=UNIDAD_HABILES,
            feriados=set(),
        )

        self.assertEqual(resultado.fecha_hasta, self.viernes)
        self.assertEqual(resultado.fecha_reintegro, self.lunes)
        self.assertEqual(resultado.dias_consumidos, 1)
        self.assertEqual(resultado.dias_corridos, 1)

    def test_omision_de_feriados_intermedios_en_dias_habiles(self):
        """
        Si existe un feriado entre semana, debe omitirse y extender la fecha
        de finalización al siguiente día hábil disponible.
        """
        # Martes 17 es feriado
        feriado_martes = self.martes
        feriados = {feriado_martes}

        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,  # 13/11
            dias=5,
            unidad=UNIDAD_HABILES,
            feriados=feriados,
        )

        # Días hábiles esperados:
        # Día 1: Viernes 13
        # Fin de semana: Sáb 14 / Dom 15 (Omitidos)
        # Día 2: Lunes 16
        # Feriado: Martes 17 (Omitido)
        # Día 3: Miércoles 18
        # Día 4: Jueves 19
        # Día 5: Viernes 20
        self.assertEqual(resultado.fecha_hasta, self.viernes_sgte)  # 2026-11-20
        # Reintegro: Sáb 21 y Dom 22 omitidos -> Lunes 23
        self.assertEqual(resultado.fecha_reintegro, self.lunes_sgte)  # 2026-11-23
        self.assertEqual(resultado.dias_consumidos, 5)
        self.assertEqual(resultado.dias_habiles, 5)
        self.assertIn(feriado_martes, resultado.dias_feriados)

    def test_feriado_en_dia_de_reintegro_salta_al_siguiente_dia_habil(self):
        """
        Si el día inmediatamente posterior a la licencia es feriado,
        el reintegro debe saltar al próximo día laborable.
        """
        # Viernes 20 es feriado institucional
        feriados = {self.viernes_sgte}

        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,  # 13/11
            dias=5,
            unidad=UNIDAD_HABILES,
            feriados=feriados,
        )

        # Termina el jueves 19
        self.assertEqual(resultado.fecha_hasta, self.jueves)
        # Reintegro: Viernes 20 feriado, fin de semana omitido -> Lunes 23
        self.assertEqual(resultado.fecha_reintegro, self.lunes_sgte)

    def test_dias_corridos_calculo_y_reintegro(self):
        """
        En licencias por días corridos (ej: Maternidad o afecciones largas),
        se cuentan todos los días calendario para la duración, pero el reintegro
        siempre es en un día hábil.
        """
        # 5 días corridos desde Viernes 13:
        # 1: Vie 13, 2: Sáb 14, 3: Dom 15, 4: Lun 16, 5: Mar 17
        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,
            dias=5,
            unidad=UNIDAD_CORRIDOS,
            feriados=set(),
        )

        self.assertEqual(resultado.fecha_hasta, self.martes)  # 2026-11-17
        self.assertEqual(resultado.fecha_reintegro, self.miercoles)  # 2026-11-18
        self.assertEqual(resultado.dias_consumidos, 5)
        self.assertEqual(resultado.dias_corridos, 5)
        self.assertEqual(resultado.dias_habiles, 3)  # Vie 13, Lun 16, Mar 17
        self.assertEqual(resultado.unidad, UNIDAD_CORRIDOS)

    def test_dias_corridos_finalizando_en_fin_de_semana(self):
        """
        Si una licencia por días corridos finaliza un sábado o domingo,
        el reintegro se traslada al lunes.
        """
        # 3 días corridos desde Jueves 12 -> Jue 12, Vie 13, Sáb 14
        jueves_12 = datetime.date(2026, 11, 12)
        resultado = calcular_fechas_licencia(
            fecha_desde=jueves_12,
            dias=3,
            unidad=UNIDAD_CORRIDOS,
            feriados=set(),
        )

        self.assertEqual(resultado.fecha_hasta, self.sabado)  # Sábado 14
        # Lunes 16 (salta domingo 15)
        self.assertEqual(resultado.fecha_reintegro, self.lunes)
        self.assertEqual(resultado.dias_consumidos, 3)

    def test_calculo_con_rango_explicito_fecha_desde_y_fecha_hasta(self):
        """
        Cuando se proporciona un intervalo [fecha_desde, fecha_hasta], calcula
        exactamente los días hábiles y corridos consumidos según la unidad.
        """
        # Rango Viernes 13 a Jueves 19 (7 días corridos, 5 días hábiles)
        res_hab = calcular_fechas_licencia(
            fecha_desde=self.viernes,
            fecha_hasta=self.jueves,
            unidad=UNIDAD_HABILES,
            feriados=set(),
        )
        self.assertEqual(res_hab.dias_consumidos, 5)
        self.assertEqual(res_hab.dias_habiles, 5)
        self.assertEqual(res_hab.dias_corridos, 7)
        self.assertEqual(res_hab.fecha_reintegro, self.viernes_sgte)

        res_corr = calcular_fechas_licencia(
            fecha_desde=self.viernes,
            fecha_hasta=self.jueves,
            unidad=UNIDAD_CORRIDOS,
            feriados=set(),
        )
        self.assertEqual(res_corr.dias_consumidos, 7)
        self.assertEqual(res_corr.dias_habiles, 5)
        self.assertEqual(res_corr.dias_corridos, 7)
        self.assertEqual(res_corr.fecha_reintegro, self.viernes_sgte)

    def test_consulta_automatica_a_dianolaborable_en_base_de_datos(self):
        """
        Verifica que si no se suministra el set de feriados explícito,
        el motor consulte automáticamente el modelo DiaNoLaborable en la BD.
        """
        # Crear feriado en BD
        feriado_db = DiaNoLaborable.objects.create(
            fecha=self.martes,
            tipo="FERIADO",
            descripcion="Día Festivo Institucional",
        )

        resultado = calcular_fechas_licencia(
            fecha_desde=self.viernes,
            dias=5,
            unidad=UNIDAD_HABILES,
        )

        # Debe omitir Martes 17 y finalizar el Viernes 20
        self.assertEqual(resultado.fecha_hasta, self.viernes_sgte)
        self.assertIn(feriado_db.fecha, resultado.dias_feriados)

    def test_integracion_con_tipo_licencia_y_deteccion_de_unidad(self):
        """
        Verifica que la unidad se determine automáticamente a partir de la
        instancia de TipoLicencia si no se especifica explícitamente.
        """
        # Licencia por Maternidad (Días Corridos según modelo Ley 647-E)
        tipo_maternidad = TipoLicencia.objects.create(
            codigo="TEST-MAT",
            articulo="Art. 341",
            descripcion="Maternidad 135 días corridos",
            cantidad_duracion="135 días corridos",
            unidad="Corridos",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
        )
        self.assertEqual(tipo_maternidad.unidad_calculo, UNIDAD_CORRIDOS)

        res_mat = tipo_maternidad.calcular_fechas(
            fecha_desde=self.viernes,
            dias=10,
            feriados=set(),
        )
        self.assertEqual(res_mat.unidad, UNIDAD_CORRIDOS)
        self.assertEqual(res_mat.dias_consumidos, 10)
        self.assertEqual(
            res_mat.fecha_hasta,
            self.viernes + datetime.timedelta(days=9),
        )

        # Licencia de Corto Tratamiento (Días Hábiles según modelo Ley 647-E)
        tipo_corto = TipoLicencia.objects.create(
            codigo="TEST-CORTO",
            articulo="Art. 340-A",
            descripcion="Enfermedad de Corto Tratamiento",
            cantidad_duracion="30 días hábiles",
            unidad="Hábiles",
            categoria="LICENCIA",
            forma_pago="CON_GOCE",
        )
        self.assertEqual(tipo_corto.unidad_calculo, UNIDAD_HABILES)

        res_corto = tipo_corto.calcular_fechas(
            fecha_desde=self.viernes,
            dias=5,
            feriados=set(),
        )
        self.assertEqual(res_corto.unidad, UNIDAD_HABILES)
        self.assertEqual(res_corto.fecha_hasta, self.jueves)
        self.assertEqual(res_corto.fecha_reintegro, self.viernes_sgte)

    def test_integracion_con_licencia_otorgada_ticket_16_1(self):
        """
        Verifica que una instancia de LicenciaOtorgada calcule sus fechas
        y fecha de reintegro delegando al motor de cálculo.
        """
        docente = Docente.objects.create(
            nombre="Laura",
            apellido="Gómez",
            dni="31999888",
            activo=True,
        )
        tipo = TipoLicencia.objects.create(
            codigo="TEST-16-1-INTEG",
            articulo="Art. 342",
            descripcion="Paternidad o cuidados familiares",
            unidad="Hábiles",
            categoria="Ordinaria",
            forma_pago="CON_GOCE",
        )
        lic = LicenciaOtorgada.objects.create(
            docente=docente,
            tipo_licencia=tipo,
            fecha_desde=self.viernes,  # 2026-11-13 (Viernes)
            fecha_hasta_prevista=self.jueves,  # 2026-11-19 (Jueves)
        )
        calc = lic.calcular_fechas(feriados=set())
        self.assertEqual(calc.dias_consumidos, 5)
        self.assertEqual(calc.fecha_reintegro, self.viernes_sgte)
        self.assertEqual(lic.calcular_reintegro(feriados=set()), self.viernes_sgte)

    def test_interfaz_orientada_a_objetos_motor_calculo_licencia(self):
        """
        Verifica los métodos auxiliares expuestos por MotorCalculoLicencia.
        """
        self.assertTrue(MotorCalculoLicencia.es_dia_habil(self.viernes))
        self.assertFalse(MotorCalculoLicencia.es_dia_habil(self.sabado))
        self.assertFalse(MotorCalculoLicencia.es_dia_habil(self.domingo))

        # Feriado
        feriados = {self.viernes}
        self.assertFalse(
            MotorCalculoLicencia.es_dia_habil(self.viernes, feriados=feriados)
        )

        # Siguiente día hábil desde jueves 19 -> viernes 20
        self.assertEqual(
            MotorCalculoLicencia.siguiente_dia_habil(self.jueves),
            self.viernes_sgte,
        )
        # Siguiente día hábil desde viernes 13 -> lunes 16
        self.assertEqual(
            MotorCalculoLicencia.siguiente_dia_habil(self.viernes),
            self.lunes,
        )

        # Conteo entre fechas
        self.assertEqual(
            MotorCalculoLicencia.contar_corridos(self.viernes, self.jueves),
            7,
        )
        self.assertEqual(
            MotorCalculoLicencia.contar_habiles(self.viernes, self.jueves),
            5,
        )

    def test_funciones_auxiliares_nivel_modulo(self):
        """Verifica las funciones directas a nivel de módulo."""
        self.assertTrue(es_dia_habil(self.viernes))
        self.assertFalse(es_dia_habil(self.sabado))
        self.assertEqual(
            obtener_siguiente_dia_habil(self.jueves), self.viernes_sgte
        )
        self.assertEqual(calcular_fecha_reintegro(self.jueves), self.viernes_sgte)
        calc = calcular_fechas_licencia(self.viernes, dias=1)
        self.assertIsInstance(calc, CalculoFechasLicencia)
        self.assertEqual(calc["fecha_hasta"], calc.fecha_hasta)

    def test_parse_date_safe_formatos_soportados(self):
        """Verifica compatibilidad con strings ISO, date y datetime."""
        d = datetime.date(2026, 11, 13)
        dt = datetime.datetime(2026, 11, 13, 14, 30, 0)
        iso_str = "2026-11-13"

        self.assertEqual(parse_date_safe(d), d)
        self.assertEqual(parse_date_safe(dt), d)
        self.assertEqual(parse_date_safe(iso_str), d)

        with self.assertRaises(ValidationError):
            parse_date_safe("")
        with self.assertRaises(ValidationError):
            parse_date_safe("fecha-invalida")
        with self.assertRaises(ValidationError):
            parse_date_safe(12345)

    def test_validaciones_de_negocio_excepciones(self):
        """Verifica que se eleven ValidationErrors ante datos ilógicos."""
        # Días menor o igual a cero
        with self.assertRaises(ValidationError):
            calcular_fechas_licencia(fecha_desde=self.viernes, dias=0)
        with self.assertRaises(ValidationError):
            calcular_fechas_licencia(fecha_desde=self.viernes, dias=-3)

        # Fecha hasta anterior a fecha desde
        with self.assertRaises(ValidationError):
            calcular_fechas_licencia(
                fecha_desde=self.lunes,
                fecha_hasta=self.viernes,  # anterior
            )

        # Ni días ni fecha_hasta suministrados
        with self.assertRaises(ValidationError):
            calcular_fechas_licencia(fecha_desde=self.viernes)

        # Conteo con rango invertido
        with self.assertRaises(ValidationError):
            contar_dias_habiles(self.lunes, self.viernes)
        with self.assertRaises(ValidationError):
            contar_dias_corridos(self.lunes, self.viernes)

    def test_normalizar_unidad(self):
        """Verifica variantes léxicas y normalización a HABILES o CORRIDOS."""
        self.assertEqual(normalizar_unidad("habiles"), UNIDAD_HABILES)
        self.assertEqual(normalizar_unidad("HÁBILES"), UNIDAD_HABILES)
        self.assertEqual(normalizar_unidad("laborable"), UNIDAD_HABILES)
        self.assertEqual(normalizar_unidad("corridos"), UNIDAD_CORRIDOS)
        self.assertEqual(normalizar_unidad("DÍAS CORRIDOS"), UNIDAD_CORRIDOS)
        self.assertEqual(normalizar_unidad(None), UNIDAD_HABILES)


class CalcularFechasLicenciaAPITests(TestCase):
    """
    Pruebas para el endpoint REST API /api/licencias/calcular-fechas/.
    """

    def setUp(self):
        self.url = reverse("api_licencias:calcular_fechas")
        self.viernes = "2026-11-13"

    def test_api_calculo_exitoso_get(self):
        """GET con fecha_desde y dias calcula y devuelve JSON con status 200."""
        resp = self.client.get(
            self.url,
            {"fecha_desde": self.viernes, "dias": 5, "unidad": "HABILES"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["fecha_hasta"], "2026-11-19")  # Jueves
        self.assertEqual(data["data"]["fecha_reintegro"], "2026-11-20")  # Viernes
        self.assertEqual(data["data"]["dias_consumidos"], 5)
        self.assertEqual(data["data"]["dias_habiles"], 5)
        self.assertEqual(data["data"]["dias_corridos"], 7)

    def test_api_calculo_exitoso_post(self):
        """POST con parámetros form-data calcula y devuelve JSON con status 200."""
        resp = self.client.post(
            self.url,
            {"fecha_desde": self.viernes, "dias": 3, "unidad": "CORRIDOS"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["fecha_hasta"], "2026-11-15")  # Domingo
        self.assertEqual(data["data"]["fecha_reintegro"], "2026-11-16")  # Lunes
        self.assertEqual(data["data"]["dias_consumidos"], 3)

    def test_api_error_falta_fecha_desde(self):
        """Falta parámetro obligatorio fecha_desde -> HTTP 400."""
        resp = self.client.get(self.url, {"dias": 5})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)

    def test_api_error_falta_dias_y_fecha_hasta(self):
        """Solo fecha_desde sin dias ni fecha_hasta -> HTTP 400."""
        resp = self.client.get(self.url, {"fecha_desde": self.viernes})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)

    def test_api_error_fecha_hasta_anterior_a_desde(self):
        """fecha_hasta anterior a fecha_desde -> HTTP 400."""
        resp = self.client.get(
            self.url,
            {"fecha_desde": "2026-11-20", "fecha_hasta": "2026-11-13"},
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["status"], "error")
