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
        request = self.factory.post("/asistencia/diaria/")
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
        group_consulta, _ = Group.objects.get_or_create(name="Consulta_Directiva")
        self.user_consulta.groups.add(group_consulta)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_user", password="password123"
        )
        group_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.user_bedelia.groups.add(group_bedelia)

        self.user_admin = User.objects.create_superuser(
            username="admin_asist",
            password="password123",
            email="admin@test.com",
        )

    def test_botones_carga_masiva_ocultos_para_consulta_directiva(self):
        """
        Valida que un usuario de Consulta_Directiva no vea los botones
        de '+ Cargar Asistencia Diaria' ni 'Justificaciones por Lote'.
        """
        from django.urls import reverse

        self.client.login(username="consulta_user", password="password123")
        response = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "+ Cargar Asistencia Diaria")
        self.assertNotContains(response, "+ Carga Masiva")
        self.assertNotContains(response, "Justificaciones por Lote")
        self.assertNotContains(response, reverse("asistencia:asistencia_diaria"))
        self.assertNotContains(response, reverse("asistencia:justificaciones_lote"))

    def test_botones_carga_masiva_visibles_para_bedelia_y_admin(self):
        """
        Valida que usuarios con privilegios operativos (Bedelía) o de administración
        sí visualicen los botones de acción en el listado con la etiqueta
        '+ Cargar Asistencia Diaria'.
        """
        from django.urls import reverse

        self.client.login(username="bedelia_user", password="password123")
        resp_bedelia = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(resp_bedelia.status_code, 200)
        self.assertContains(resp_bedelia, "+ Cargar Asistencia Diaria")
        self.assertContains(resp_bedelia, reverse("asistencia:asistencia_diaria"))
        self.assertContains(resp_bedelia, "Justificaciones por Lote")

        self.client.login(username="admin_asist", password="password123")
        resp_admin = self.client.get(reverse("asistencia:asistencia_list"))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "+ Cargar Asistencia Diaria")
        self.assertContains(resp_admin, reverse("asistencia:asistencia_diaria"))
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
        from django.contrib.auth.models import Group

        self.user = User.objects.create_user(
            username="operador_bedelia",
            password="password123",
            email="operador@iesetyfp.edu.ar",
        )
        admin_group, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.user.groups.add(admin_group)
        self.otro_user = User.objects.create_user(
            username="otro_operador",
            password="password123",
            email="otro@iesetyfp.edu.ar",
        )
        bedelia_group, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.otro_user.groups.add(bedelia_group)
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
            any("Día no laborable registrado con éxito." in m.message for m in messages)
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
            any("Día no laborable modificado con éxito." in m.message for m in messages)
        )

    def test_delete_view_feriado(self):
        """Valida confirmación GET y eliminación física mediante POST."""
        self.client.login(username="operador_bedelia", password="password123")
        delete_url = reverse("asistencia:feriado_delete", args=[self.feriado.pk])

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
        self.assertFalse(DiaNoLaborable.objects.filter(pk=self.feriado.pk).exists())

        messages = list(resp_post.context["messages"])
        self.assertTrue(any("eliminado correctamente" in m.message for m in messages))

    def test_create_view_error_validacion_fecha_duplicada(self):
        """Valida que una fecha duplicada rechace el formulario y muestre error."""
        self.client.login(username="operador_bedelia", password="password123")
        data = {
            "fecha": "2026-12-08",  # Misma fecha que self.feriado
            "tipo": "FERIADO",
            "descripcion": "Otro feriado duplicado",
        }
        resp = self.client.post(reverse("asistencia:feriado_create"), data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context["form"],
            "fecha",
            "Ya existe un día no laborable registrado para esta fecha.",
        )

    def test_alias_compatibles_dianolaborable(self):
        """
        Ticket 12.11: Valida que al consultar las rutas dias-no-laborables/*,
        el servidor responda con HTTP 301 permanente y cabecera Location
        apuntando a la URL canónica de feriados/.
        """
        resp_list = self.client.get("/asistencia/dias-no-laborables/")
        self.assertEqual(resp_list.status_code, 301)
        self.assertEqual(resp_list.url, reverse("asistencia:feriado_list"))

        resp_create = self.client.get("/asistencia/dias-no-laborables/crear/")
        self.assertEqual(resp_create.status_code, 301)
        self.assertEqual(resp_create.url, reverse("asistencia:feriado_create"))

        resp_update = self.client.get(
            f"/asistencia/dias-no-laborables/{self.feriado.pk}/editar/"
        )
        self.assertEqual(resp_update.status_code, 301)
        self.assertEqual(
            resp_update.url,
            reverse("asistencia:feriado_update", args=[self.feriado.pk]),
        )

        resp_delete = self.client.get(
            f"/asistencia/dias-no-laborables/{self.feriado.pk}/eliminar/"
        )
        self.assertEqual(resp_delete.status_code, 301)
        self.assertEqual(
            resp_delete.url,
            reverse("asistencia:feriado_delete", args=[self.feriado.pk]),
        )

    test_alias_urls_dianolaborable = test_alias_compatibles_dianolaborable


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
        response = self.client.get("/asistencia/diaria/")
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
            f"/asistencia/diaria/?fecha={fecha_feriado.isoformat()}"
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

        response = self.client.post("/asistencia/diaria/", post_data)
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
        res_crear = self.client.post("/asistencia/diaria/", post_data_crear)
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
        res_act = self.client.post("/asistencia/diaria/", post_data_actualizar)
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


class Ticket10_5RendimientoTests(TestCase):
    """
    Pruebas para el Ticket 10.5:
    - Optimización de Rendimiento y Erradicación de Consultas N+1.
    - Precarga con in_bulk en AsistenciaDiariaView.post.
    - Criterio de Aceptación: Guardar la asistencia de 20 docentes consume
      menos de 15 queries SQL totales.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin_perf",
            password="password123",
            email="admin_perf@test.com",
        )
        self.client.login(username="admin_perf", password="password123")

        # Crear 20 docentes activos
        self.docentes_20 = [
            Docente.objects.create(
                dni=f"300000{i:02d}",
                apellido=f"DOCENTE_{i:02d}",
                nombre=f"Nombre_{i:02d}",
                sexo="M",
                activo=True,
            )
            for i in range(1, 21)
        ]

    def test_criterio_guardar_asistencia_20_docentes_menos_de_15_queries(self):
        """
        Criterio de Aceptación:
        El test de rendimiento con CaptureQueriesContext confirma que guardar
        la asistencia de 20 docentes consume menos de 15 queries SQL totales.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        fecha_prueba = datetime.date(2026, 11, 2)
        post_data = {
            "fecha": fecha_prueba.isoformat(),
            "docente_ids": [d.id for d in self.docentes_20],
        }
        for d in self.docentes_20:
            post_data[f"estado_{d.id}"] = "PRESENTE"
            post_data[f"marca_diaria_{d.id}"] = "PR"
            post_data[f"observaciones_{d.id}"] = "Carga rápida masiva"

        # 1. Medir queries SQL al crear masivamente 20 registros
        with CaptureQueriesContext(connection) as queries_context:
            response = self.client.post("/asistencia/diaria/", post_data)

        self.assertEqual(response.status_code, 302)
        total_queries = len(queries_context)
        self.assertLess(
            total_queries,
            15,
            f"Criterio de Aceptación no cumplido: se ejecutaron {total_queries} "
            f"queries para 20 docentes (debe ser estrictamente menor a 15).",
        )

        # Verificar que se crearon los 20 registros
        self.assertEqual(
            RegistroAsistencia.objects.filter(fecha=fecha_prueba).count(),
            20,
        )

        # 2. Medir queries SQL al actualizar masivamente los 20 registros existentes
        post_data_act = {
            "fecha": fecha_prueba.isoformat(),
            "docente_ids": [d.id for d in self.docentes_20],
        }
        for d in self.docentes_20:
            post_data_act[f"estado_{d.id}"] = "AUSENTE"
            post_data_act[f"marca_diaria_{d.id}"] = "I"
            post_data_act[f"observaciones_{d.id}"] = "Rectificación masiva"

        with CaptureQueriesContext(connection) as queries_act_context:
            resp_act = self.client.post("/asistencia/diaria/", post_data_act)

        self.assertEqual(resp_act.status_code, 302)
        total_queries_act = len(queries_act_context)
        self.assertLess(
            total_queries_act,
            15,
            f"Criterio de Aceptación no cumplido al actualizar: se ejecutaron "
            f"{total_queries_act} queries (debe ser menor a 15).",
        )

        # Siguen siendo 20 registros actualizados a AUSENTE
        self.assertEqual(
            RegistroAsistencia.objects.filter(
                fecha=fecha_prueba, estado="AUSENTE"
            ).count(),
            20,
        )

    def test_procesar_justificacion_rango_precarga_fecha_range_una_sola_query(
        self,
    ):
        """
        Valida que procesar_justificacion_rango precargue todas las
        asistencias del intervalo en una sola consulta SQL usando fecha__range.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.licencias.services import procesar_justificacion_rango

        docente = self.docentes_20[0]
        # Crear 5 asistencias previas
        for dia in range(1, 6):
            RegistroAsistencia.objects.create(
                docente=docente,
                fecha=datetime.date(2026, 8, dia),
                estado="AUSENTE",
                marca_diaria="I",
            )

        f_desde = datetime.date(2026, 8, 1)
        f_hasta = datetime.date(2026, 8, 7)

        # Monitorear consultas durante la justificación del rango
        with CaptureQueriesContext(connection) as ctx:
            procesar_justificacion_rango(
                docente=docente,
                fecha_desde=f_desde,
                fecha_hasta=f_hasta,
                nueva_marca="P",
                usuario=self.user,
            )

        # Verificar que se realizó el SELECT con fecha__range
        queries_sql = [q["sql"] for q in ctx.captured_queries]
        select_range = [
            sql
            for sql in queries_sql
            if "registroasistencia" in sql.lower() and "between" in sql.lower()
        ]
        self.assertGreaterEqual(
            len(select_range),
            1,
            "Debe existir al menos una consulta con fecha__range (BETWEEN).",
        )


class Ticket10_6BlindajePermisosTests(TestCase):
    """
    Pruebas para el Ticket 10.6:
    Blindaje de Permisos Backend y Rechazo 403 Estricto en Asistencia y Feriados.
    Criterios de Aceptación:
    1. Un usuario Consulta_Directiva recibe error 403 al enviar POST a los
       endpoints de asistencia y feriados.
    2. Un usuario Bedelia_Operadoras recibe error 403 al intentar eliminar un feriado.
    3. Bedelía y Admin pueden operar y crear/editar feriados y cargar asistencia.
    """

    def setUp(self):
        User = get_user_model()
        from django.contrib.auth.models import Group

        self.grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.grupo_consulta, _ = Group.objects.get_or_create(name="Consulta_Directiva")

        self.user_consulta = User.objects.create_user(
            username="consulta_asist", password="password123"
        )
        self.user_consulta.groups.add(self.grupo_consulta)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_asist", password="password123"
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_admin = User.objects.create_user(
            username="admin_asist_perm", password="password123"
        )
        self.user_admin.groups.add(self.grupo_admin)

        self.docente = Docente.objects.create(
            dni="29000111",
            apellido="FERRER",
            nombre="Lucas",
            sexo="M",
            activo=True,
        )
        self.feriado = DiaNoLaborable.objects.create(
            fecha=datetime.date(2026, 11, 20),
            tipo="FERIADO",
            descripcion="Día de la Soberanía",
            creado_por=self.user_admin,
        )

    def test_criterio_consulta_directiva_recibe_403_post_asistencia_diaria(self):
        """
        Criterio de Aceptación:
        Consulta_Directiva recibe HTTP 403 al enviar POST a AsistenciaDiariaView.
        """
        self.client.login(username="consulta_asist", password="password123")
        url = reverse("asistencia:asistencia_diaria")
        response = self.client.post(
            url,
            {
                "fecha": "2026-11-03",
                f"estado_{self.docente.id}": "PRESENTE",
                f"marca_diaria_{self.docente.id}": "PR",
            },
        )
        self.assertEqual(
            response.status_code,
            403,
            (
                "Consulta_Directiva debe recibir 403 Forbidden "
                "al hacer POST a asistencia diaria."
            ),
        )

    def test_criterio_consulta_directiva_recibe_403_post_carga_masiva(self):
        """
        Criterio de Aceptación:
        Consulta_Directiva recibe HTTP 403 al enviar POST a AsistenciaDiariaView.
        """
        self.client.login(username="consulta_asist", password="password123")
        url = reverse("asistencia:asistencia_diaria")
        response = self.client.post(
            url,
            {
                "fecha": "2026-11-03",
                f"estado_{self.docente.id}": "PRESENTE",
                f"marca_diaria_{self.docente.id}": "PR",
            },
        )
        self.assertEqual(
            response.status_code,
            403,
            (
                "Consulta_Directiva debe recibir 403 Forbidden "
                "al hacer POST a carga masiva."
            ),
        )

    def test_criterio_consulta_directiva_recibe_403_post_justificaciones_lote(
        self,
    ):
        """
        Criterio de Aceptación:
        Consulta_Directiva recibe HTTP 403 al enviar POST a JustificacionesLoteView.
        """
        self.client.login(username="consulta_asist", password="password123")
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.post(url, {"items": ["item1"]})
        self.assertEqual(
            response.status_code,
            403,
            (
                "Consulta_Directiva debe recibir 403 Forbidden "
                "al hacer POST a justificaciones lote."
            ),
        )

    def test_criterio_consulta_directiva_recibe_403_en_feriados_create_update_delete(
        self,
    ):
        """
        Consulta_Directiva recibe HTTP 403 al intentar crear, editar
        o eliminar feriados.
        """
        self.client.login(username="consulta_asist", password="password123")

        # Create
        resp_create = self.client.post(
            reverse("asistencia:feriado_create"),
            {
                "fecha": "2026-12-25",
                "tipo": "FERIADO",
                "descripcion": "Navidad",
            },
        )
        self.assertEqual(resp_create.status_code, 403)

        # Update
        resp_update = self.client.post(
            reverse("asistencia:feriado_update", args=[self.feriado.pk]),
            {
                "fecha": "2026-11-20",
                "tipo": "ASUETO",
                "descripcion": "Modificado",
            },
        )
        self.assertEqual(resp_update.status_code, 403)

        # Delete
        resp_delete = self.client.post(
            reverse("asistencia:feriado_delete", args=[self.feriado.pk])
        )
        self.assertEqual(resp_delete.status_code, 403)

    def test_criterio_bedelia_operadoras_recibe_403_eliminar_feriado(self):
        """
        Criterio de Aceptación:
        Un usuario Bedelia_Operadoras recibe error 403 al intentar eliminar un feriado.
        """
        self.client.login(username="bedelia_asist", password="password123")
        delete_url = reverse("asistencia:feriado_delete", args=[self.feriado.pk])

        # GET confirmación debe dar 403
        resp_get = self.client.get(delete_url)
        self.assertEqual(
            resp_get.status_code,
            403,
            "Bedelía debe recibir 403 en GET confirmación de eliminar feriado.",
        )

        # POST eliminación debe dar 403 y no borrar el registro
        resp_post = self.client.post(delete_url)
        self.assertEqual(
            resp_post.status_code,
            403,
            "Bedelía debe recibir 403 al ejecutar POST para eliminar feriado.",
        )
        self.assertTrue(DiaNoLaborable.objects.filter(pk=self.feriado.pk).exists())

    def test_bedelia_operadoras_puede_cargar_asistencia_y_crear_editar_feriado(
        self,
    ):
        """
        Valida que Bedelia_Operadoras sí tenga acceso operativo a POST de asistencia
        y a Crear / Editar feriados.
        """
        self.client.login(username="bedelia_asist", password="password123")

        # Cargar asistencia
        resp_asist = self.client.post(
            reverse("asistencia:asistencia_diaria"),
            {
                "fecha": "2026-11-03",
                f"estado_{self.docente.id}": "PRESENTE",
                f"marca_diaria_{self.docente.id}": "PR",
            },
            follow=False,
        )
        self.assertEqual(resp_asist.status_code, 302)

        # Crear feriado
        resp_create = self.client.post(
            reverse("asistencia:feriado_create"),
            {
                "fecha": "2026-12-25",
                "tipo": "FERIADO",
                "descripcion": "Navidad 2026",
            },
            follow=False,
        )
        self.assertEqual(resp_create.status_code, 302)

        # Editar feriado
        resp_update = self.client.post(
            reverse("asistencia:feriado_update", args=[self.feriado.pk]),
            {
                "fecha": "2026-11-20",
                "tipo": "ASUETO",
                "descripcion": "Soberanía Nacional",
            },
            follow=False,
        )
        self.assertEqual(resp_update.status_code, 302)

    def test_admin_institucional_puede_eliminar_feriado(self):
        """
        Valida que un usuario de Admin_Institucional pueda eliminar un
        feriado con éxito.
        """
        self.client.login(username="admin_asist_perm", password="password123")
        delete_url = reverse("asistencia:feriado_delete", args=[self.feriado.pk])

        resp_get = self.client.get(delete_url)
        self.assertEqual(resp_get.status_code, 200)

        resp_post = self.client.post(delete_url, follow=False)
        self.assertEqual(resp_post.status_code, 302)
        self.assertFalse(DiaNoLaborable.objects.filter(pk=self.feriado.pk).exists())


class Ticket1210UnificacionAsistenciaDiariaTests(TestCase):
    """
    Ticket 12.10: Unificación Canónica de Asistencia Diaria y Redirección 301.
    """

    def test_redireccion_301_carga_masiva_a_asistencia_diaria(self):
        """
        Una petición a /asistencia/carga-masiva/ responde con HTTP 301 permanente
        apuntando a /asistencia/diaria/.
        """
        response = self.client.get("/asistencia/carga-masiva/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("asistencia:asistencia_diaria"))

    def test_redireccion_301_carga_masiva_por_reverse(self):
        """
        reverse('asistencia:carga_masiva') resuelve a /asistencia/carga-masiva/
        y redirige 301 a /asistencia/diaria/.
        """
        url = reverse("asistencia:carga_masiva")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("asistencia:asistencia_diaria"))

    def test_redireccion_301_consultar_a_consulta_asistencia(self):
        """
        Una petición a /asistencia/consultar/ responde con HTTP 301 permanente
        apuntando a /asistencia/consulta/.
        """
        response = self.client.get("/asistencia/consultar/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("asistencia:consulta_asistencia"))


class GranularidadMultiTurnoAsistenciaTests(TestCase):
    """
    Auditoría de Compliance: Reglas de Negocio y Granularidad Multi-Turno.
    Valida el Requerimiento Operativo Crítico (SIE / Bedelía):
    "Un docente debe poder registrar diferentes estados de asistencia
    (ej. Presente y Ausente) el mismo día, siempre que correspondan
    a materias/turnos (Cargos) distintos".
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.personal.models import CargoDocente, Carrera, EspacioCurricular

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin_multiturno",
            password="password123",
            email="admin_multiturno@test.com",
        )
        self.client.login(username="admin_multiturno", password="password123")

        self.carrera = Carrera.objects.create(
            codigo="TSDS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
        )

        self.docente = Docente.objects.create(
            dni="28999888",
            apellido="Gómez",
            nombre="Carlos",
            sexo="M",
            activo=True,
        )

        self.espacio_matematica = EspacioCurricular.objects.create(
            codigo="MAT-101",
            nombre="Matemática I",
            carrera=self.carrera,
            anio=1,
            turno="MANANA",
        )
        self.espacio_programacion = EspacioCurricular.objects.create(
            codigo="PROG-102",
            nombre="Programación Web",
            carrera=self.carrera,
            anio=2,
            turno="TARDE",
        )

        self.cargo_manana = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio_matematica,
            turno="M",
            situacion_revista="TIT",
            activo=True,
        )
        self.cargo_tarde = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio_programacion,
            turno="T",
            situacion_revista="INT",
            activo=True,
        )

    def test_docente_mismo_dia_dos_cargos_distintos_estados_diferentes_orm(self):
        """
        ORM / Base de Datos: Un docente puede tener un registro 'PRESENTE'
        a la mañana en un cargo y un 'AUSENTE' a la tarde en otro cargo el mismo día.
        """
        fecha = datetime.date(2026, 6, 15)

        reg_manana = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=fecha,
            estado="PRESENTE",
            marca_diaria="PR",
            justifica=True,
        )

        reg_tarde = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_tarde,
            fecha=fecha,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )

        registros = RegistroAsistencia.objects.filter(
            docente=self.docente, fecha=fecha
        ).order_by("cargo__turno")

        self.assertEqual(registros.count(), 2)
        self.assertEqual(reg_manana.estado, "PRESENTE")
        self.assertEqual(reg_manana.marca_diaria, "PR")
        self.assertEqual(reg_tarde.estado, "AUSENTE")
        self.assertEqual(reg_tarde.marca_diaria, "I")

    def test_docente_mismo_dia_mismo_cargo_duplicado_bloqueado_por_constraint(self):
        """
        Integridad SQL: Intentar guardar dos registros para el mismo docente,
        fecha y CARGO idéntico debe ser rechazado por UniqueConstraint.
        """
        from django.db import IntegrityError

        fecha = datetime.date(2026, 6, 15)

        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=fecha,
            estado="PRESENTE",
            marca_diaria="PR",
        )

        with self.assertRaises(IntegrityError):
            RegistroAsistencia.objects.create(
                docente=self.docente,
                cargo=self.cargo_manana,
                fecha=fecha,
                estado="AUSENTE",
                marca_diaria="I",
            )

    def test_asistencia_diaria_view_get_renderiza_ambos_cargos(self):
        """
        Vista AsistenciaDiariaView (GET): La grilla diaria contiene una fila
        por cada CargoDocente vigente del docente, no solo una por docente.
        """
        fecha = datetime.date(2026, 6, 15)
        url = f"{reverse('asistencia:asistencia_diaria')}?fecha={fecha.isoformat()}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        grilla = response.context["grilla"]
        cargos_en_grilla = [fila["cargo"].id for fila in grilla]
        self.assertIn(self.cargo_manana.id, cargos_en_grilla)
        self.assertIn(self.cargo_tarde.id, cargos_en_grilla)

    def test_asistencia_diaria_view_post_guarda_estados_distintos_por_cargo(self):
        """
        Vista AsistenciaDiariaView (POST): Permite enviar en el mismo formulario
        'PRESENTE' para el cargo de la mañana y 'AUSENTE' para el de la tarde.
        """
        fecha = datetime.date(2026, 6, 15)
        post_data = {
            "fecha": fecha.isoformat(),
            f"estado_{self.cargo_manana.id}": "PRESENTE",
            f"marca_diaria_{self.cargo_manana.id}": "PR",
            f"estado_{self.cargo_tarde.id}": "AUSENTE",
            f"marca_diaria_{self.cargo_tarde.id}": "I",
        }

        response = self.client.post(
            reverse("asistencia:asistencia_diaria"), post_data
        )
        self.assertEqual(response.status_code, 302)

        reg_m = RegistroAsistencia.objects.get(
            docente=self.docente, cargo=self.cargo_manana, fecha=fecha
        )
        reg_t = RegistroAsistencia.objects.get(
            docente=self.docente, cargo=self.cargo_tarde, fecha=fecha
        )

        self.assertEqual(reg_m.estado, "PRESENTE")
        self.assertEqual(reg_m.marca_diaria, "PR")
        self.assertEqual(reg_t.estado, "AUSENTE")
        self.assertEqual(reg_t.marca_diaria, "I")

    def test_registro_asistencia_form_permite_cargos_distintos_mismo_dia(self):
        """
        Formulario RegistroAsistenciaForm: Permite registrar asistencia para
        un segundo cargo del docente en la misma fecha, y rechaza duplicados
        si el cargo coincide.
        """
        fecha = datetime.date(2026, 6, 15)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=fecha,
            estado="PRESENTE",
            marca_diaria="PR",
        )

        # Formulario para el segundo cargo (Tarde): Debe ser VÁLIDO
        form_segundo_cargo = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "cargo": self.cargo_tarde.pk,
                "fecha": fecha.isoformat(),
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertTrue(
            form_segundo_cargo.is_valid(),
            form_segundo_cargo.errors,
        )

        # Formulario para el MISMO cargo (Mañana): Debe ser INVÁLIDO
        form_mismo_cargo = RegistroAsistenciaForm(
            data={
                "docente": self.docente.pk,
                "cargo": self.cargo_manana.pk,
                "fecha": fecha.isoformat(),
                "estado": "AUSENTE",
                "marca_diaria": "I",
                "oficina": "1452",
                "anio_planilla": 2026,
            }
        )
        self.assertFalse(form_mismo_cargo.is_valid())
        self.assertIn("fecha", form_mismo_cargo.errors)
        self.assertIn(
            "Ya existe un registro", form_mismo_cargo.errors["fecha"][0]
        )


class JustificacionesLoteViewTests(TestCase):
    """
    Pruebas integrales de la vista JustificacionesLoteView (GET/POST),
    validación de estado/licencias, preservación de selección ante errores
    y atomicidad del procesamiento por lote.
    """

    def setUp(self):
        from django.contrib.auth.models import Group
        from apps.personal.models import CargoCatalogo, CargoDocente, EspacioCurricular

        User = get_user_model()
        grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.user_bedelia = User.objects.create_user(
            username="bedelia_lote", password="password123"
        )
        self.user_bedelia.groups.add(grupo_bedelia)
        self.client.login(username="bedelia_lote", password="password123")

        self.docente = Docente.objects.create(
            dni="31222333",
            apellido="Benítez",
            nombre="Sofía",
            sexo="F",
            activo=True,
        )
        self.materia = EspacioCurricular.objects.create(
            codigo="IA-101",
            nombre="Matemática Aplicada a IA",
            carrera="IA",
            anio=1,
            turno="MANANA",
        )
        self.cargo_materia = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            situacion_revista="TIT",
            activo=True,
        )
        self.cargo_catalogo = CargoCatalogo.objects.create(
            codigo="BED-T",
            descripcion="Bedel de Turno Tarde",
        )
        self.cargo_adm = CargoDocente.objects.create(
            docente=self.docente,
            tipo_cargo="CARGO_ADM",
            cargo_catalogo=self.cargo_catalogo,
            situacion_revista="INT",
            activo=True,
        )

        self.tipo_lic = TipoLicencia.objects.create(
            codigo="TIT-ORD-311-A",
            articulo="Art. 311 inc. a",
            descripcion="Enfermedad común titular hasta 45 días corridos",
            categoria="Ordinaria",
            cuadro_mensual="IL-01",
            activo=True,
        )

        self.ausente_1 = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_materia,
            fecha=datetime.date(2026, 10, 20),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        self.ausente_2 = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_adm,
            fecha=datetime.date(2026, 10, 21),
            estado="AUSENTE",
            marca_diaria="INA",
            justifica=False,
        )
        self.presente = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_materia,
            fecha=datetime.date(2026, 10, 22),
            estado="PRESENTE",
            marca_diaria="PR",
            justifica=True,
        )

    def test_get_justificaciones_lote_renderiza_200_sin_field_error(self):
        """
        Verifica que GET /asistencia/justificaciones-lote/ responda HTTP 200
        mostrando inasistencias pendientes (con materia y cargo de catálogo)
        y omitiendo registros ya presentes.
        """
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "asistencia/justificaciones_lote.html")
        self.assertEqual(response.context["total_pendientes"], 2)
        self.assertContains(response, "Benítez, Sofía")
        self.assertContains(response, "Matemática Aplicada a IA")
        self.assertContains(response, "Bedel de Turno Tarde")
        self.assertContains(response, "TIT-ORD-311-A (Art. 311 inc. a)")
        self.assertContains(response, 'value="LT"')
        self.assertNotContains(response, f'value="{self.presente.id}"')

    def test_post_justificar_lote_con_permiso_p(self):
        """
        Verifica que seleccionar inasistencias con marca 'P' las justifique
        correctamente y deje las no seleccionadas intactas.
        """
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.post(
            url,
            {
                "nueva_marca": "P",
                "tipo_licencia": "",
                "items": [str(self.ausente_1.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("asistencia:asistencia_list"))

        self.ausente_1.refresh_from_db()
        self.ausente_2.refresh_from_db()

        self.assertEqual(self.ausente_1.estado, "JUSTIFICADO")
        self.assertEqual(self.ausente_1.marca_diaria, "P")
        self.assertTrue(self.ausente_1.justifica)
        self.assertEqual(self.ausente_1.modificado_por, self.user_bedelia)

        # No seleccionado permanece pendiente
        self.assertEqual(self.ausente_2.estado, "AUSENTE")
        self.assertFalse(self.ausente_2.justifica)

    def test_post_justificar_lote_con_lic_y_lt(self):
        """
        Verifica la justificación por lote con marcas 'LIC' y 'LT'
        asociando el TipoLicencia elegido.
        """
        url = reverse("asistencia:justificaciones_lote")

        resp_lic = self.client.post(
            url,
            {
                "nueva_marca": "LIC",
                "tipo_licencia": str(self.tipo_lic.id),
                "items": [str(self.ausente_1.id)],
            },
        )
        self.assertEqual(resp_lic.status_code, 302)
        self.ausente_1.refresh_from_db()
        self.assertEqual(self.ausente_1.estado, "LICENCIA")
        self.assertEqual(self.ausente_1.marca_diaria, "LIC")
        self.assertEqual(self.ausente_1.tipo_licencia, self.tipo_lic)
        self.assertTrue(self.ausente_1.justifica)

        resp_lt = self.client.post(
            url,
            {
                "nueva_marca": "LT",
                "tipo_licencia": str(self.tipo_lic.id),
                "items": [str(self.ausente_2.id)],
            },
        )
        self.assertEqual(resp_lt.status_code, 302)
        self.ausente_2.refresh_from_db()
        self.assertEqual(self.ausente_2.estado, "LICENCIA")
        self.assertEqual(self.ausente_2.marca_diaria, "LT")
        self.assertEqual(self.ausente_2.tipo_licencia, self.tipo_lic)
        self.assertTrue(self.ausente_2.justifica)

    def test_post_lic_sin_tipo_licencia_devuelve_400_y_preserva_seleccion(self):
        """
        Verifica que enviar 'LIC' sin tipo_licencia responda HTTP 400 (sin 500),
        no modifique ningún registro y preserve la selección del usuario.
        """
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.post(
            url,
            {
                "nueva_marca": "LIC",
                "tipo_licencia": "",
                "items": [str(self.ausente_1.id)],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["error"])
        self.assertIn(str(self.ausente_1.id), response.context["selected_ids"])
        self.assertEqual(response.context["selected_nueva_marca"], "LIC")

        self.ausente_1.refresh_from_db()
        self.assertEqual(self.ausente_1.estado, "AUSENTE")
        self.assertFalse(self.ausente_1.justifica)

    def test_post_items_vacios_permanece_en_justificaciones_lote(self):
        """
        Verifica que al enviar sin seleccionar inasistencias se redirija a
        justificaciones_lote con mensaje de advertencia.
        """
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.post(url, {"nueva_marca": "P"})
        self.assertRedirects(response, url)

    def test_post_lote_mixto_fallo_en_segundo_registro_revierte_primero(self):
        """
        Verifica atomicidad vía HTTP POST: si el lote mezcla un ausente y un
        presente, el ausente no debe persistir justificado.
        """
        url = reverse("asistencia:justificaciones_lote")
        response = self.client.post(
            url,
            {
                "nueva_marca": "P",
                "items": [str(self.ausente_1.id), str(self.presente.id)],
            },
        )
        self.assertEqual(response.status_code, 400)

        self.ausente_1.refresh_from_db()
        self.assertEqual(self.ausente_1.estado, "AUSENTE")
        self.assertEqual(self.ausente_1.marca_diaria, "I")
        self.assertFalse(self.ausente_1.justifica)

    def test_post_items_json_con_respaldo_de_marca_y_licencia_id(self):
        """
        Verifica compatibilidad cuando items contiene JSON parcial delegando
        nueva_marca y tipo_licencia al servicio de justificación.
        """
        import json

        url = reverse("asistencia:justificaciones_lote")
        payload = json.dumps({
            "asistencia": self.ausente_1.id,
            "tipo_licencia": self.tipo_lic.id,
        })
        response = self.client.post(
            url,
            {
                "nueva_marca": "LIC",
                "items": [payload],
            },
        )
        self.assertEqual(response.status_code, 302)

        self.ausente_1.refresh_from_db()
        self.assertEqual(self.ausente_1.estado, "LICENCIA")
        self.assertEqual(self.ausente_1.marca_diaria, "LIC")
        self.assertEqual(self.ausente_1.tipo_licencia, self.tipo_lic)


class RegistroAsistenciaUpdateAndSyncTests(TestCase):
    """
    Pruebas para edición individual de registros de asistencia (dos vías:
    Presente <-> Ausente <-> Licencia <-> Justificado), aislamiento por cargo,
    preservación de filtros (?next=), rectificación automática de planillas
    mensuales preexistentes (RN-03) y correcciones en AsistenciaDiariaView.
    """

    def setUp(self):
        from django.contrib.auth.models import Group
        from apps.personal.models import CargoDocente, EspacioCurricular

        User = get_user_model()
        self.grupo_admin, _ = Group.objects.get_or_create(name="Admin_Institucional")
        self.grupo_bedelia, _ = Group.objects.get_or_create(name="Bedelia_Operadoras")
        self.grupo_consulta, _ = Group.objects.get_or_create(name="Consulta_Directiva")

        self.user_admin = User.objects.create_user(
            username="admin_edit_asist", password="password123"
        )
        self.user_admin.groups.add(self.grupo_admin)

        self.user_bedelia = User.objects.create_user(
            username="bedelia_edit_asist", password="password123"
        )
        self.user_bedelia.groups.add(self.grupo_bedelia)

        self.user_consulta = User.objects.create_user(
            username="consulta_edit_asist", password="password123"
        )
        self.user_consulta.groups.add(self.grupo_consulta)

        self.docente = Docente.objects.create(
            dni="32111222",
            apellido="Benítez",
            nombre="Sofía",
            sexo="F",
            activo=True,
        )
        self.otro_docente = Docente.objects.create(
            dni="32999888",
            apellido="Peralta",
            nombre="Diego",
            sexo="M",
            activo=True,
        )

        self.mat_1 = EspacioCurricular.objects.create(
            codigo="PROG-301",
            nombre="Programación III",
            carrera="TSDS",
            anio=2,
            turno="MANANA",
        )
        self.mat_2 = EspacioCurricular.objects.create(
            codigo="BD-302",
            nombre="Bases de Datos II",
            carrera="TSDS",
            anio=2,
            turno="TARDE",
        )
        self.cargo_manana = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.mat_1,
            turno="M",
            situacion_revista="TIT",
            horas_lunes=4,
            horas_miercoles=4,
            activo=True,
        )
        self.cargo_tarde = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.mat_2,
            turno="T",
            situacion_revista="INT",
            horas_lunes=3,
            horas_miercoles=3,
            activo=True,
        )
        self.cargo_otro = CargoDocente.objects.create(
            docente=self.otro_docente,
            materia=self.mat_1,
            turno="N",
            situacion_revista="TIT",
            horas_lunes=2,
            activo=True,
        )

        self.lic_ordinaria = TipoLicencia.objects.create(
            codigo="TIT-ORD-311-A",
            articulo="Art. 311 inc. a",
            descripcion="Enfermedad común titular",
            categoria="Ordinaria",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.lic_largo = TipoLicencia.objects.create(
            codigo="LT-340B",
            articulo="Art. 340 inc. b",
            descripcion="Largo Tratamiento",
            categoria="Especial",
            cuadro_mensual="IL-01",
            activo=True,
        )
        self.lic_particular = TipoLicencia.objects.create(
            codigo="ART-350-P",
            articulo="Art. 350",
            descripcion="Asuntos particulares sin goce",
            categoria="Particular",
            cuadro_mensual="IL-02",
            activo=True,
        )

        self.fecha_lunes = datetime.date(2026, 9, 7)

    def test_rbac_y_visibilidad_boton_editar(self):
        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=self.fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        edit_url = reverse("asistencia:asistencia_update", args=[reg.pk])
        list_url = reverse("asistencia:asistencia_list")

        # Anónimo -> 302 al login
        resp_anon_get = self.client.get(edit_url)
        self.assertEqual(resp_anon_get.status_code, 302)
        self.assertIn("/accounts/login/", resp_anon_get.url)

        resp_anon_post = self.client.post(edit_url, {"estado": "PRESENTE"})
        self.assertEqual(resp_anon_post.status_code, 302)
        self.assertIn("/accounts/login/", resp_anon_post.url)

        # Consulta_Directiva -> 403 en GET/POST y no ve botón Editar
        self.client.login(username="consulta_edit_asist", password="password123")
        resp_cons_list = self.client.get(list_url)
        self.assertEqual(resp_cons_list.status_code, 200)
        self.assertNotContains(resp_cons_list, edit_url)

        resp_cons_get = self.client.get(edit_url)
        self.assertEqual(resp_cons_get.status_code, 403)

        resp_cons_post = self.client.post(edit_url, {"estado": "PRESENTE"})
        self.assertEqual(resp_cons_post.status_code, 403)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")

        # Bedelia_Operadoras -> ve botón Editar, GET 200 y POST 302
        self.client.login(username="bedelia_edit_asist", password="password123")
        resp_bed_list = self.client.get(list_url)
        self.assertEqual(resp_bed_list.status_code, 200)
        self.assertContains(resp_bed_list, edit_url)

        resp_bed_get = self.client.get(edit_url)
        self.assertEqual(resp_bed_get.status_code, 200)
        self.assertTemplateUsed(resp_bed_get, "asistencia/registroasistencia_form.html")

        resp_bed_post = self.client.post(edit_url, {"estado": "PRESENTE"})
        self.assertEqual(resp_bed_post.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "PRESENTE")

        # Admin_Institucional -> GET 200 y POST 302
        self.client.login(username="admin_edit_asist", password="password123")
        resp_adm_get = self.client.get(edit_url)
        self.assertEqual(resp_adm_get.status_code, 200)
        resp_adm_post = self.client.post(edit_url, {"estado": "AUSENTE"})
        self.assertEqual(resp_adm_post.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")

    def test_corregir_ausente_a_presente_actualiza_metricas_y_aisla_otros_cargos(self):
        from apps.core.services import obtener_panel_alertas_docentes

        reg_objetivo = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=self.fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            numero_disposicion="001/2026",
            creado_por=self.user_admin,
        )
        reg_mismo_doc_otro_cargo = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_tarde,
            fecha=self.fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            creado_por=self.user_admin,
        )
        reg_otro_docente = RegistroAsistencia.objects.create(
            docente=self.otro_docente,
            cargo=self.cargo_otro,
            fecha=self.fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
            creado_por=self.user_admin,
        )

        alerta_antes = obtener_panel_alertas_docentes(anio=2026).get(
            pk=self.docente.pk
        )
        self.assertEqual(alerta_antes.faltas_count, 2)
        resumen_antes = self.docente.obtener_resumen_inasistencias(anio=2026)
        self.assertEqual(resumen_antes["inasistencias"], 2)

        self.client.login(username="bedelia_edit_asist", password="password123")
        edit_url = reverse("asistencia:asistencia_update", args=[reg_objetivo.pk])
        resp = self.client.post(
            edit_url,
            {
                "estado": "PRESENTE",
                "marca_diaria": "I",
                "tipo_licencia": str(self.lic_ordinaria.pk),
                "numero_disposicion": "001/2026",
                "observaciones": "Corrección: firmó planilla",
            },
        )
        self.assertEqual(resp.status_code, 302)

        reg_objetivo.refresh_from_db()
        self.assertEqual(reg_objetivo.estado, "PRESENTE")
        self.assertEqual(reg_objetivo.marca_diaria, "PR")
        self.assertTrue(reg_objetivo.justifica)
        self.assertIsNone(reg_objetivo.tipo_licencia)
        self.assertEqual(reg_objetivo.numero_disposicion, "")
        self.assertEqual(reg_objetivo.creado_por, self.user_admin)
        self.assertEqual(reg_objetivo.modificado_por, self.user_bedelia)

        # Otros cargos/docentes permanecen intactos
        reg_mismo_doc_otro_cargo.refresh_from_db()
        reg_otro_docente.refresh_from_db()
        self.assertEqual(reg_mismo_doc_otro_cargo.estado, "AUSENTE")
        self.assertEqual(reg_mismo_doc_otro_cargo.marca_diaria, "I")
        self.assertFalse(reg_mismo_doc_otro_cargo.justifica)
        self.assertEqual(reg_otro_docente.estado, "AUSENTE")

        alerta_despues = obtener_panel_alertas_docentes(anio=2026).get(
            pk=self.docente.pk
        )
        self.assertEqual(alerta_despues.faltas_count, 1)
        resumen_despues = self.docente.obtener_resumen_inasistencias(anio=2026)
        self.assertEqual(resumen_despues["inasistencias"], 1)

    def test_transiciones_presente_a_ausente_y_licencia_con_validacion(self):
        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=self.fecha_lunes,
            fecha_hasta=self.fecha_lunes + datetime.timedelta(days=1),
            estado="PRESENTE",
            marca_diaria="PR",
            justifica=True,
        )
        self.client.login(username="bedelia_edit_asist", password="password123")
        edit_url = reverse("asistencia:asistencia_update", args=[reg.pk])

        # PRESENTE -> AUSENTE (también limpia fecha_hasta por RN-06)
        resp_aus = self.client.post(
            edit_url,
            {
                "estado": "AUSENTE",
                "marca_diaria": "PR",
                "observaciones": "Ausencia constatada",
            },
        )
        self.assertEqual(resp_aus.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")
        self.assertEqual(reg.marca_diaria, "I")
        self.assertFalse(reg.justifica)
        self.assertIsNone(reg.fecha_hasta)

        # AUSENTE -> LICENCIA sin tipo_licencia -> 200 con error y DB intacta
        resp_err = self.client.post(
            edit_url,
            {
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "tipo_licencia": "",
                "next": "/asistencia/?estado=AUSENTE",
            },
        )
        self.assertEqual(resp_err.status_code, 200)
        self.assertFormError(
            resp_err.context["form"],
            "tipo_licencia",
            "Debe especificar el Tipo de Licencia cuando el estado es LICENCIA.",
        )
        self.assertEqual(resp_err.context["next_url"], "/asistencia/?estado=AUSENTE")
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")

        # AUSENTE -> LICENCIA (con LT-340B asigna marca LT)
        resp_lic = self.client.post(
            edit_url,
            {
                "estado": "LICENCIA",
                "marca_diaria": "I",
                "tipo_licencia": str(self.lic_largo.pk),
                "numero_disposicion": "Res. MEC 500/2026",
            },
        )
        self.assertEqual(resp_lic.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "LICENCIA")
        self.assertEqual(reg.marca_diaria, "LT")
        self.assertEqual(reg.tipo_licencia, self.lic_largo)
        self.assertTrue(reg.justifica)

        # LICENCIA -> AUSENTE (limpia tipo_licencia y disposición previa sin cambios)
        resp_lic_aus = self.client.post(
            edit_url,
            {
                "estado": "AUSENTE",
                "marca_diaria": "LT",
                "tipo_licencia": str(self.lic_largo.pk),
                "numero_disposicion": "Res. MEC 500/2026",
            },
        )
        self.assertEqual(resp_lic_aus.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "AUSENTE")
        self.assertEqual(reg.marca_diaria, "I")
        self.assertIsNone(reg.tipo_licencia)
        self.assertEqual(reg.numero_disposicion, "")
        self.assertFalse(reg.justifica)

        # AUSENTE -> JUSTIFICADO
        resp_just = self.client.post(
            edit_url,
            {
                "estado": "JUSTIFICADO",
                "marca_diaria": "I",
                "tipo_licencia": "",
            },
        )
        self.assertEqual(resp_just.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "JUSTIFICADO")
        self.assertEqual(reg.marca_diaria, "P")
        self.assertTrue(reg.justifica)

    def test_preserva_filtros_next_y_protege_contra_redireccion_externa(self):
        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=self.fecha_lunes,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        self.client.login(username="bedelia_edit_asist", password="password123")
        next_valid = "/asistencia/?dni_o_apellido=Ben%C3%ADtez&estado=AUSENTE"
        edit_url = reverse("asistencia:asistencia_update", args=[reg.pk])

        resp_valid = self.client.post(
            edit_url,
            {"estado": "PRESENTE", "next": next_valid},
        )
        self.assertRedirects(resp_valid, next_valid, fetch_redirect_response=False)

        resp_unsafe = self.client.post(
            edit_url,
            {"estado": "AUSENTE", "next": "https://evil.example/phish"},
        )
        self.assertRedirects(
            resp_unsafe,
            reverse("asistencia:asistencia_list"),
            fetch_redirect_response=False,
        )

    def test_rectificacion_rn03_ausente_a_presente_y_cambio_licencia_en_planilla(self):
        from apps.licencias.models import RenglonPlanillaMensual
        from apps.licencias.services import generar_planilla_mes

        # Mes sin planilla previa -> editar NO debe autogenerar renglones prematuros
        reg_sin_planilla = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=datetime.date(2026, 8, 3),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        self.client.login(username="bedelia_edit_asist", password="password123")
        self.client.post(
            reverse("asistencia:asistencia_update", args=[reg_sin_planilla.pk]),
            {"estado": "PRESENTE"},
        )
        self.assertEqual(
            RenglonPlanillaMensual.objects.filter(mes=8, anio=2026).count(), 0
        )

        # Mes con planilla mensual ya generada (septiembre 2026)
        reg_aus = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=datetime.date(2026, 9, 7),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        reg_lic = RegistroAsistencia.objects.create(
            docente=self.otro_docente,
            cargo=self.cargo_otro,
            fecha=datetime.date(2026, 9, 7),
            estado="LICENCIA",
            marca_diaria="LIC",
            tipo_licencia=self.lic_particular,
            justifica=True,
        )
        generar_planilla_mes(mes=9, anio=2026, usuario=self.user_admin)

        vigentes_ini = RenglonPlanillaMensual.objects.vigentes().filter(
            mes=9, anio=2026
        )
        self.assertEqual(vigentes_ini.count(), 2)
        renglon_aus_orig = vigentes_ini.get(docente=self.docente)
        inst_orig_aus = renglon_aus_orig.numero_instrumento

        # 1. GET muestra aviso RN-03
        edit_aus_url = reverse("asistencia:asistencia_update", args=[reg_aus.pk])
        resp_get = self.client.get(edit_aus_url)
        self.assertTrue(resp_get.context["planilla_existente"])
        self.assertContains(resp_get, "RN-03")

        # 2. Corregir Benítez AUSENTE -> PRESENTE
        resp_post = self.client.post(
            edit_aus_url,
            {"estado": "PRESENTE", "numero_disposicion": inst_orig_aus},
        )
        self.assertEqual(resp_post.status_code, 302)

        renglon_aus_orig.refresh_from_db()
        self.assertTrue(renglon_aus_orig.desactualizada)
        self.assertEqual(renglon_aus_orig.numero_instrumento, inst_orig_aus)

        vigentes_post_1 = RenglonPlanillaMensual.objects.vigentes().filter(
            mes=9, anio=2026
        )
        self.assertEqual(vigentes_post_1.count(), 1)
        self.assertFalse(vigentes_post_1.filter(docente=self.docente).exists())

        csv_resp = self.client.get(
            f"{reverse('licencias:exportar_planilla_csv')}?mes=9&anio=2026"
        )
        self.assertEqual(csv_resp.status_code, 200)
        self.assertNotIn("Benítez", csv_resp.content.decode("utf-8"))

        # 3. Cambiar tipo de licencia equivocado en reg_lic (IL-02 -> IL-01)
        renglon_lic_orig = vigentes_post_1.get(docente=self.otro_docente)
        inst_lic_orig = renglon_lic_orig.numero_instrumento
        edit_lic_url = reverse("asistencia:asistencia_update", args=[reg_lic.pk])
        resp_lic_fix = self.client.post(
            edit_lic_url,
            {
                "estado": "LICENCIA",
                "marca_diaria": "LIC",
                "tipo_licencia": str(self.lic_ordinaria.pk),
                "numero_disposicion": inst_lic_orig,
            },
        )
        self.assertEqual(resp_lic_fix.status_code, 302)

        renglon_lic_orig.refresh_from_db()
        self.assertTrue(renglon_lic_orig.desactualizada)
        self.assertEqual(renglon_lic_orig.numero_instrumento, inst_lic_orig)

        vigentes_post_2 = RenglonPlanillaMensual.objects.vigentes().filter(
            mes=9, anio=2026
        )
        self.assertEqual(vigentes_post_2.count(), 1)
        nuevo_renglon = vigentes_post_2.get(docente=self.otro_docente)
        self.assertEqual(nuevo_renglon.tipo_licencia, self.lic_ordinaria)
        self.assertEqual(nuevo_renglon.cuadro, "IL-01")
        self.assertNotEqual(nuevo_renglon.numero_instrumento, inst_lic_orig)

    def test_justificaciones_lote_rectifica_planilla_preexistente(self):
        from apps.licencias.models import RenglonPlanillaMensual
        from apps.licencias.services import generar_planilla_mes

        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=datetime.date(2026, 10, 5),
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        generar_planilla_mes(mes=10, anio=2026, usuario=self.user_admin)
        renglon_orig = RenglonPlanillaMensual.objects.vigentes().get(
            mes=10, anio=2026, docente=self.docente
        )
        self.assertIsNone(renglon_orig.tipo_licencia)

        self.client.login(username="bedelia_edit_asist", password="password123")
        resp = self.client.post(
            reverse("asistencia:justificaciones_lote"),
            {
                "nueva_marca": "LIC",
                "tipo_licencia": str(self.lic_ordinaria.pk),
                "items": [str(reg.pk)],
            },
        )
        self.assertEqual(resp.status_code, 302)

        renglon_orig.refresh_from_db()
        self.assertTrue(renglon_orig.desactualizada)

        renglon_nuevo = RenglonPlanillaMensual.objects.vigentes().get(
            mes=10, anio=2026, docente=self.docente
        )
        self.assertEqual(renglon_nuevo.tipo_licencia, self.lic_ordinaria)
        self.assertEqual(renglon_nuevo.cuadro, "IL-01")

    def test_asistencia_diaria_justifica_en_licencia_y_redirect_fecha_error(self):
        from apps.licencias.models import RenglonPlanillaMensual
        from apps.licencias.services import generar_planilla_mes

        fecha = datetime.date(2026, 9, 9)
        reg = RegistroAsistencia.objects.create(
            docente=self.docente,
            cargo=self.cargo_manana,
            fecha=fecha,
            estado="AUSENTE",
            marca_diaria="I",
            justifica=False,
        )
        generar_planilla_mes(mes=9, anio=2026, usuario=self.user_admin)
        renglon_orig = RenglonPlanillaMensual.objects.vigentes().get(
            mes=9, anio=2026, docente=self.docente
        )

        self.client.login(username="bedelia_edit_asist", password="password123")

        # 1. Error al elegir LICENCIA sin tipo_licencia preserva ?fecha=...
        resp_err = self.client.post(
            reverse("asistencia:asistencia_diaria"),
            {
                "fecha": fecha.isoformat(),
                f"estado_{self.cargo_manana.pk}": "LICENCIA",
                f"marca_diaria_{self.cargo_manana.pk}": "LIC",
            },
        )
        self.assertRedirects(
            resp_err,
            f"{reverse('asistencia:asistencia_diaria')}?fecha={fecha.isoformat()}",
            fetch_redirect_response=False,
        )

        # 2. Corregir AUSENTE -> LICENCIA asigna justifica=True y rectifica planilla
        resp_ok = self.client.post(
            reverse("asistencia:asistencia_diaria"),
            {
                "fecha": fecha.isoformat(),
                f"estado_{self.cargo_manana.pk}": "LICENCIA",
                f"marca_diaria_{self.cargo_manana.pk}": "LIC",
                f"licencia_{self.cargo_manana.pk}": str(self.lic_ordinaria.pk),
            },
        )
        self.assertEqual(resp_ok.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.estado, "LICENCIA")
        self.assertTrue(reg.justifica)
        self.assertEqual(reg.tipo_licencia, self.lic_ordinaria)

        renglon_orig.refresh_from_db()
        self.assertTrue(renglon_orig.desactualizada)
        renglon_nuevo = RenglonPlanillaMensual.objects.vigentes().get(
            mes=9, anio=2026, docente=self.docente
        )
        self.assertEqual(renglon_nuevo.tipo_licencia, self.lic_ordinaria)


# Importación de pruebas del Ticket 12.6 (Consulta Avanzada Multicriterio)
from apps.asistencia.tests_ticket_12_6 import (  # noqa: F401, E402
    ConsultaAvanzadaMulticriterioTests,
)
