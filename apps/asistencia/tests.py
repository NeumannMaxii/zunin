"""
Pruebas automatizadas para apps.asistencia:
- Formularios del módulo de Asistencia (Ticket 3).
- Transaccionalidad Atómica en Carga Masiva (Ticket 5) y Justificaciones (Ticket 7).
- Criterio: Fallo en registro 3 de 5 revierte todo (0 asistencias guardadas).
- Notificación al usuario mediante django.contrib.messages.error().
- Paginación obligatoria en RegistroAsistenciaListView (paginate_by = 25).
"""

import datetime
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from apps.asistencia.forms import DiaNoLaborableForm, RegistroAsistenciaForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import (
    guardar_asistencia_diaria_masiva,
    justificar_lote_asistencias,
)
from apps.asistencia.views import RegistroAsistenciaListView
from apps.licencias.models import TipoLicencia
from apps.personal.models import Docente


class AsistenciaFormsTests(TestCase):
    def setUp(self):
        self.docente = Docente.objects.create(
            dni="20123456",
            apellido="Álvarez",
            nombre="Laura",
            sexo="F",
        )
        self.tipo_lic = TipoLicencia.objects.create(
            codigo="LIC-340A",
            articulo="340-A",
            descripcion="Enfermedad Corto Tratamiento",
            categoria="LICENCIA",
            cuadro_mensual="IL-01",
        )
        self.tipo_inasistencia = TipoLicencia.objects.create(
            codigo="INA-INJ",
            articulo="348",
            descripcion="Inasistencia Injustificada",
            categoria="INASISTENCIA",
            cuadro_mensual="IL-02",
        )

    # --- Pruebas DiaNoLaborableForm ---

    def test_dia_no_laborable_form_valido(self):
        """Valida alta exitosa de un día no laborable."""
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "FERIADO",
                "descripcion": "Día de la Revolución de Mayo",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.descripcion, "Día de la Revolución de Mayo")

    def test_dia_no_laborable_form_descripcion_vacia_rechazada(self):
        """Rechaza descripción en blanco o con espacios únicamente."""
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "FERIADO",
                "descripcion": "   ",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("descripcion", form.errors)

    def test_dia_no_laborable_form_fecha_duplicada_rechazada(self):
        """Rechaza fechas de días no laborables repetidas."""
        DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 5, 25),
            tipo="FERIADO",
            descripcion="Feriado Preexistente",
        )
        form = DiaNoLaborableForm(
            data={
                "fecha": "2026-05-25",
                "tipo": "ASUETO",
                "descripcion": "Asueto Duplicado",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha", form.errors)
        self.assertIn("Ya existe un día no laborable", form.errors["fecha"][0])

    # --- Pruebas RegistroAsistenciaForm ---

    def test_registro_asistencia_form_presente_valido(self):
        """Valida registro normal en estado PRESENTE."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "PRESENTE",
                "marca_diaria": "PR",
                "oficina": "1452",
                "anio_planilla": 2026,
                "justifica": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        registro = form.save()
        self.assertEqual(registro.estado, "PRESENTE")

    def test_registro_asistencia_form_licencia_sin_tipo_rechazado(self):
        """Rechaza estado LICENCIA si no se indica el Tipo de Licencia."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn(
            "Debe especificar el Tipo de Licencia", form.errors["tipo_licencia"][0]
        )

    def test_registro_asistencia_form_presente_con_tipo_licencia_rechazado(self):
        """Rechaza estado PRESENTE si se le adjudica un Tipo de Licencia."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "PRESENTE",
                "marca_diaria": "PR",
                "tipo_licencia": self.tipo_lic.pk,
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tipo_licencia", form.errors)
        self.assertIn(
            "No debe asignar un Tipo de Licencia", form.errors["tipo_licencia"][0]
        )

    def test_registro_asistencia_form_inasistencia_multidia_rechazada_rn06(self):
        """RN-06: Las inasistencias solamente pueden ser por un día."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "fecha_hasta": "2026-04-12",
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_hasta", form.errors)
        self.assertIn("RN-06", form.errors["fecha_hasta"][0])

    def test_registro_asistencia_form_fecha_hasta_anterior_a_fecha(self):
        """Rechaza fecha_hasta anterior a la fecha de inicio."""
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "fecha_hasta": "2026-04-05",
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "tipo_licencia": self.tipo_lic.pk,
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_hasta", form.errors)

    def test_registro_asistencia_form_docente_fecha_duplicado(self):
        """Rechaza duplicar la asistencia del mismo docente en la misma fecha."""
        RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 4, 10),
            estado="PRESENTE",
        )
        form = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "fecha": "2026-04-10",
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha", form.errors)
        self.assertIn("Ya existe un registro", form.errors["fecha"][0])


class AtomicidadAsistenciaTests(TestCase):
    """
    Criterio de Aceptación Ticket 3.8:
    Test Atomicidad: Simular un fallo en el registro 3 de un lote de 5 asistencias
    y verificar mediante assert que el sistema revirtió la operación completa
    (0 asistencias guardadas).
    """

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="28444555",
            apellido="Valenzuela",
            nombre="Roberto",
            sexo="M",
        )
        self.factory = RequestFactory()

    def test_atomicidad_fallo_registro_3_revierte_operacion_completa(self):
        """
        Simula un lote de 5 asistencias donde el registro 3 contiene un dato
        inválido que genera ValidationError. Se verifica con assert que el rollback
        fue total y quedaron 0 asistencias guardadas en la base de datos.
        """
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

        # Lote de 5 registros (registro 1 y 2 válidos, 3 inválido, 4 y 5 válidos)
        lote_5 = [
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 1),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 2),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 3),
                estado="ESTADO_INVALIDO",  # Registro 3 fallará en full_clean()
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 4),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
            RegistroAsistencia(
                docente=self.docente,
                fecha=datetime.date(2026, 10, 5),
                estado="PRESENTE",
                marca_diaria="PR",
            ),
        ]

        with self.assertRaises(ValidationError):
            guardar_asistencia_diaria_masiva(lote_5)

        # Aserción obligatoria del criterio de aceptación: 0 asistencias guardadas
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

    def test_atomicidad_notifica_error_con_messages_al_usuario(self):
        """
        Verifica que ante un fallo en el lote, si se provee el objeto request,
        se agregue un mensaje con nivel ERROR mediante django.contrib.messages.error().
        """
        request = self.factory.post("/asistencia/carga-masiva/")
        setattr(request, "session", "session")
        messages_storage = FallbackStorage(request)
        setattr(request, "_messages", messages_storage)

        lote_invalido = [
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 10),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 11),
                "estado": "ESTADO_NO_EXISTENTE",  # Inválido
                "marca_diaria": "PR",
            },
        ]

        with self.assertRaises(ValidationError):
            guardar_asistencia_diaria_masiva(lote_invalido, request=request)

        # 0 registros persistidos
        self.assertEqual(RegistroAsistencia.objects.count(), 0)

        # Verificación del mensaje registrado
        lista_mensajes = list(get_messages(request))
        self.assertTrue(len(lista_mensajes) > 0)
        self.assertEqual(lista_mensajes[0].level_tag, "error")
        self.assertIn("Error al procesar la carga masiva", str(lista_mensajes[0]))

    def test_atomicidad_lote_valido_guarda_todos_los_registros(self):
        """
        Verifica que cuando todas las filas son válidas, se guarden íntegramente
        todos los registros del lote.
        """
        lote_valido = [
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 20),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 21),
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "justifica": False,
            },
            {
                "docente": self.docente,
                "fecha": datetime.date(2026, 10, 22),
                "estado": "PRESENTE",
                "marca_diaria": "PR",
            },
        ]

        guardados = guardar_asistencia_diaria_masiva(lote_valido)
        self.assertEqual(len(guardados), 3)
        self.assertEqual(RegistroAsistencia.objects.count(), 3)

    def test_atomicidad_justificaciones_por_lote_revierte_ante_fallo(self):
        """
        Verifica que si en un lote de justificaciones falla un registro
        (ej: intentar justificar un registro ya presente), se revierta todo el lote.
        """
        licencia = TipoLicencia.objects.create(
            codigo="LIC_MED_AT",
            descripcion="Licencia Médica",
            categoria="LICENCIA",
        )
        asist1 = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 1),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        asist2 = RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 11, 2),
            estado="PRESENTE",  # No se puede justificar un 'PRESENTE'
            marca_diaria="PR",
            justifica=True,
        )

        lote = [
            {"asistencia": asist1, "nueva_marca": "LIC", "tipo_licencia": licencia},
            {"asistencia": asist2, "nueva_marca": "LIC", "tipo_licencia": licencia},
        ]

        with self.assertRaises(ValidationError):
            justificar_lote_asistencias(lote)

        # asist1 debe haber mantenido su estado previo sin modificar (rollback)
        asist1.refresh_from_db()
        self.assertEqual(asist1.estado, "AUSENTE")
        self.assertEqual(asist1.marca_diaria, "I")
        self.assertFalse(asist1.justifica)

    def test_asistencia_listview_paginate_by_25(self):
        """Verifica que RegistroAsistenciaListView tenga paginate_by = 25."""
        self.assertEqual(RegistroAsistenciaListView.paginate_by, 25)


class AsistenciaPermisosVisualesTests(TestCase):
    """
    Pruebas para el control de permisos visuales en el listado de asistencia:
    Ocultamiento de botones de Carga Masiva y Justificaciones por Lote
    para usuarios del grupo Consulta_Directiva.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        self.user_consulta = User.objects.create_user(
            username="consulta_user", password="password123"
        )
        group_consulta, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )
        self.user_consulta.groups.add(group_consulta)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_user", password="password123"
        )
        group_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.user_bedelia.groups.add(group_bedelia)

        self.user_admin = User.objects.create_superuser(
            username="admin_asist",
            password="password123",
            email="admin@test.com",
        )

    def test_botones_carga_masiva_ocultos_para_consulta_directiva(self):
        """
        Valida que un usuario de Consulta_Directiva no vea los botones
        de '+ Carga Masiva' ni 'Justificaciones por Lote'.
        """
        from django.urls import reverse

        self.client.login(username="consulta_user", password="password123")
        response = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "+ Carga Masiva")
        self.assertNotContains(response, "Justificaciones por Lote")
        self.assertNotContains(response, reverse("asistencia:carga_masiva"))
        self.assertNotContains(
            response, reverse("asistencia:justificaciones_lote")
        )

    def test_botones_carga_masiva_visibles_para_bedelia_y_admin(self):
        """
        Valida que usuarios con privilegios operativos (Bedelía) o de administración
        sí visualicen los botones de acción en el listado.
        """
        from django.urls import reverse

        self.client.login(username="bedelia_user", password="password123")
        resp_bedelia = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(resp_bedelia.status_code, 200)
        self.assertContains(resp_bedelia, "+ Carga Masiva")
        self.assertContains(resp_bedelia, "Justificaciones por Lote")

        self.client.login(username="admin_asist", password="password123")
        resp_admin = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "+ Carga Masiva")
        self.assertContains(resp_admin, "Justificaciones por Lote")


class DiaNoLaborableABMTests(TestCase):
    """
    Pruebas integrales para el ABM de Feriados y Días No Laborables (Ticket 4).
    Valida:
    - Vistas CBV: List, Create, Update, Delete.
    - Integración con AuditoriaFormMixin (creado_por asignado automáticamente).
    - Protección de rutas con LoginRequiredMixin.
    - Redirecciones y mensajes de notificación django.contrib.messages.
    - Paginación obligatoria (paginate_by = 25).
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="operador_bedelia",
            password="password123",
            email="operador@iesetyfp.edu.ar",
        )
        self.otro_user = User.objects.create_user(
            username="otro_operador",
            password="password123",
            email="otro@iesetyfp.edu.ar",
        )
        self.feriado = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 12, 8),
            tipo="FERIADO",
            descripcion="Inmaculada Concepción de María",
            creado_por=self.user,
        )

    def test_rutas_requieren_autenticacion(self):
        """Verifica que usuarios anónimos sean redirigidos al login."""
        urls = [
            reverse("asistencia:feriado_list"),
            reverse("asistencia:feriado_create"),
            reverse("asistencia:feriado_update", args=[self.feriado.pk]),
            reverse("asistencia:feriado_delete", args=[self.feriado.pk]),
        ]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/accounts/login/", resp.url)

    def test_list_view_feriados(self):
        """Valida que el listado responda 200 y contenga los feriados creados."""
        self.client.login(username="operador_bedelia", password="password123")
        resp = self.client.get(reverse("asistencia:feriado_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "asistencia/dianolaborable_list.html")
        self.assertContains(resp, "Inmaculada Concepción de María")
        self.assertContains(resp, "08/12/2026")
        self.assertEqual(resp.context["view"].paginate_by, 25)

    def test_create_view_feriado_con_auditoria(self):
        """
        Valida creación vía POST de DiaNoLaborable y que AuditoriaFormMixin
        inyecte automáticamente a request.user como creado_por.
        """
        self.client.login(username="operador_bedelia", password="password123")
        data = {
            "fecha": "2026-07-09",
            "tipo": "FERIADO",
            "descripcion": "Día de la Independencia",
        }
        resp = self.client.post(
            reverse("asistencia:feriado_create"),
            data=data,
            follow=True,
        )
        self.assertRedirects(resp, reverse("asistencia:feriado_list"))

        nuevo = DiaNoLaborable.objects.get(fecha=datetime.date(2026, 7, 9))
        self.assertEqual(nuevo.tipo, "FERIADO")
        self.assertEqual(nuevo.descripcion, "Día de la Independencia")
        self.assertEqual(nuevo.creado_por, self.user)

        messages = list(resp.context["messages"])
        self.assertTrue(
            any(
                "Día no laborable registrado con éxito." in m.message
                for m in messages
            )
        )

    def test_update_view_feriado_con_auditoria(self):
        """
        Valida que un usuario pueda editar el feriado y que creado_por
        permanezca inalterado.
        """
        self.client.login(username="otro_operador", password="password123")
        data = {
            "fecha": "2026-12-08",
            "tipo": "ASUETO",
            "descripcion": "Feriado / Asueto Institucional Modificado",
        }
        resp = self.client.post(
            reverse("asistencia:feriado_update", args=[self.feriado.pk]),
            data=data,
            follow=True,
        )
        self.assertRedirects(resp, reverse("asistencia:feriado_list"))

        self.feriado.refresh_from_db()
        self.assertEqual(self.feriado.tipo, "ASUETO")
        self.assertEqual(
            self.feriado.descripcion,
            "Feriado / Asueto Institucional Modificado",
        )
        # El creador original no se sobrescribe
        self.assertEqual(self.feriado.creado_por, self.user)

        messages = list(resp.context["messages"])
        self.assertTrue(
            any(
                "Día no laborable modificado con éxito." in m.message
                for m in messages
            )
        )

    def test_delete_view_feriado(self):
        """Valida confirmación GET y eliminación física mediante POST."""
        self.client.login(username="operador_bedelia", password="password123")
        delete_url = reverse(
            "asistencia:feriado_delete", args=[self.feriado.pk]
        )

        # GET renderiza plantilla de confirmación
        resp_get = self.client.get(delete_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertTemplateUsed(
            resp_get, "asistencia/dianolaborable_confirm_delete.html"
        )
        self.assertContains(resp_get, "¿Confirmar eliminación?")

        # POST elimina el registro y redirige
        resp_post = self.client.post(delete_url, follow=True)
        self.assertRedirects(resp_post, reverse("asistencia:feriado_list"))
        self.assertFalse(
            DiaNoLaborable.objects.filter(pk=self.feriado.pk).exists()
        )

        messages = list(resp_post.context["messages"])
        self.assertTrue(
            any("eliminado correctamente" in m.message for m in messages)
        )

    def test_create_view_error_validacion_fecha_duplicada(self):
        """Valida que una fecha duplicada rechace el formulario y muestre error."""
        self.client.login(username="operador_bedelia", password="password123")
        data = {
            "fecha": "2026-12-08",  # Misma fecha que self.feriado
            "tipo": "FERIADO",
            "descripcion": "Otro feriado duplicado",
        }
        resp = self.client.post(
            reverse("asistencia:feriado_create"), data=data
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context["form"],
            "fecha",
            "Ya existe un día no laborable registrado para esta fecha.",
        )

    def test_alias_urls_dianolaborable(self):
        """
        Verifica que los alias con prefijo dianolaborable_* resuelvan
        correctamente.
        """
        self.assertEqual(
            reverse("asistencia:dianolaborable_list"),
            "/asistencia/dias-no-laborables/",
        )
        self.assertEqual(
            reverse("asistencia:dianolaborable_create"),
            "/asistencia/dias-no-laborables/crear/",
        )
        self.assertEqual(
            reverse("asistencia:dianolaborable_update", args=[1]),
            "/asistencia/dias-no-laborables/1/editar/",
        )
        self.assertEqual(
            reverse("asistencia:dianolaborable_delete", args=[1]),
            "/asistencia/dias-no-laborables/1/eliminar/",
        )


class Ticket5AsistenciaDiariaTests(TestCase):
    """
    Pruebas automatizadas para Ticket 5 (Pantalla 3 - Asistencia Diaria RF-10):
    - Criterio 1: Un docente inactivo no aparece en la grilla.
    - Criterio 2: Cargar asistencia en un feriado guarda el registro
      correctamente sin bloquear al usuario (no devolver error 400).
    - Criterio 3: Feriados se advierten visualmente en rojo en la interfaz.
    - Criterio 4: Creación y actualización de registros diarios mediante
      audit_save().
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="bedelia_ticket5",
            password="password123",
            email="bedelia5@test.com",
        )
        self.client.login(username="bedelia_ticket5", password="password123")

        self.docente_activo = Docente.objects.create(
            dni="30111222",
            apellido="Bermúdez",
            nombre="Carlos",
            sexo="M",
            activo=True,
        )
        self.docente_inactivo = Docente.objects.create(
            dni="40999888",
            apellido="González",
            nombre="Mirta",
            sexo="F",
            activo=False,
        )

    def test_docente_inactivo_no_aparece_en_grilla(self):
        """
        Criterio de Aceptación:
        Un docente inactivo (activo=False) no debe aparecer en la grilla.
        """
        response = self.client.get("/asistencia/carga-masiva/")
        self.assertEqual(response.status_code, 200)

        docentes_en_contexto = response.context["docentes"]
        self.assertIn(self.docente_activo, docentes_en_contexto)
        self.assertNotIn(self.docente_inactivo, docentes_en_contexto)

        self.assertContains(response, self.docente_activo.apellido)
        self.assertContains(response, self.docente_activo.dni)
        self.assertNotContains(response, self.docente_inactivo.apellido)
        self.assertNotContains(response, self.docente_inactivo.dni)

    def test_feriado_se_advierte_visualmente_en_rojo(self):
        """
        Regla de Feriados:
        En la interfaz, los feriados se pintan de rojo visualmente para advertir.
        """
        fecha_feriado = datetime.date(2026, 5, 25)
        feriado = DiaNoLaborable.objects.create(
            fecha=fecha_feriado,
            tipo="FERIADO",
            descripcion="Revolución de Mayo",
        )

        response = self.client.get(
            f"/asistencia/carga-masiva/?fecha={fecha_feriado.isoformat()}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["es_feriado"])
        self.assertEqual(response.context["feriado"], feriado)

        # Validación de indicadores visuales en rojo
        self.assertContains(response, "border-red")
        self.assertContains(response, "bg-red")
        self.assertContains(response, "Revolución de Mayo")
        self.assertContains(response, "Día No Laborable / Feriado")

    def test_cargar_asistencia_en_feriado_guarda_sin_bloquear(self):
        """
        Criterio de Aceptación:
        Cargar asistencia en un feriado guarda el registro correctamente
        sin bloquear al usuario (no devolver error 400).
        """
        fecha_feriado = datetime.date(2026, 7, 9)
        DiaNoLaborable.objects.create(
            fecha=fecha_feriado,
            tipo="FERIADO",
            descripcion="Día de la Independencia",
        )

        post_data = {
            "fecha": fecha_feriado.isoformat(),
            "docente_ids": [self.docente_activo.id],
            f"estado_{self.docente_activo.id}": "PRESENTE",
            f"marca_diaria_{self.docente_activo.id}": "PR",
            f"observaciones_{self.docente_activo.id}": "Actividad en feriado",
        }

        response = self.client.post("/asistencia/carga-masiva/", post_data)
        # No debe devolver error 400
        self.assertNotEqual(response.status_code, 400)
        self.assertEqual(response.status_code, 302)

        # Verificación de persistencia en la base de datos
        registro = RegistroAsistencia.objects.filter(
            docente=self.docente_activo, fecha=fecha_feriado
        ).first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.estado, "PRESENTE")
        self.assertEqual(registro.marca_diaria, "PR")
        self.assertEqual(registro.observaciones, "Actividad en feriado")
        # Verificación de trazabilidad con audit_save()
        self.assertEqual(registro.creado_por, self.user)

    def test_post_crea_o_actualiza_con_audit_save(self):
        """
        POST: Crear o actualizar los registros diarios usando audit_save().
        """
        fecha_jornada = datetime.date(2026, 11, 10)

        # 1. Crear registro inicial
        post_data_crear = {
            "fecha": fecha_jornada.isoformat(),
            "docente_ids": [self.docente_activo.id],
            f"estado_{self.docente_activo.id}": "PRESENTE",
            f"marca_diaria_{self.docente_activo.id}": "PR",
        }
        res_crear = self.client.post(
            "/asistencia/carga-masiva/", post_data_crear
        )
        self.assertEqual(res_crear.status_code, 302)

        reg = RegistroAsistencia.objects.get(
            docente=self.docente_activo, fecha=fecha_jornada
        )
        self.assertEqual(reg.estado, "PRESENTE")
        self.assertEqual(reg.creado_por, self.user)

        # 2. Actualizar registro existente sin error de duplicado
        post_data_actualizar = {
            "fecha": fecha_jornada.isoformat(),
            "docente_ids": [self.docente_activo.id],
            f"estado_{self.docente_activo.id}": "AUSENTE",
            f"marca_diaria_{self.docente_activo.id}": "I",
            f"observaciones_{self.docente_activo.id}": "Novedad rectificada",
        }
        res_act = self.client.post(
            "/asistencia/carga-masiva/", post_data_actualizar
        )
        self.assertEqual(res_act.status_code, 302)

        # Sigue existiendo un único registro actualizado
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                docente=self.docente_activo, fecha=fecha_jornada
            ).count(),
            1,
        )
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")
        self.assertEqual(reg.marca_diaria, "I")
        self.assertEqual(reg.observaciones, "Novedad rectificada")
        self.assertEqual(reg.modificado_por, self.user)
