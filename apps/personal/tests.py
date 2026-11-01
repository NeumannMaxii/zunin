"""
Pruebas automatizadas para el Ticket 0.2:
- Saneamiento de Modelos, Baja Lógica e Integridad Referencial.
"""

import datetime
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from apps.asistencia.models import RegistroAsistencia
from apps.personal.forms import CargoDocenteForm, DocenteForm
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    TipoAutorizacion,
)


class SaneamientoModelosIntegridadTests(TestCase):
    """
    Validaciones de candados de borrado físico, vigencia por fecha de baja
    y normalización de situación de revista (Ticket 0.2).
    """

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="30111222",
            apellido="Gómez",
            nombre="Martín",
            sexo="M",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="PR-301",
            nombre="Programación Avanzada",
            carrera="Tecnicatura Superior en Desarrollo de Software",
            anio=3,
        )

    def test_eliminar_docente_con_asistencia_levanta_protected_error(self):
        """
        1. Verificar que intentar eliminar físicamente un Docente con registros
        de asistencia asociados levante django.db.models.ProtectedError.
        """
        RegistroAsistencia.objects.create(
            docente=self.docente,
            fecha=datetime.date(2026, 10, 20),
            estado="PRESENTE",
        )
        with self.assertRaises(ProtectedError):
            self.docente.delete()

    def test_es_designacion_vigente_falso_si_fecha_baja_pasada(self):
        """
        2. Verificar que es_designacion_vigente devuelva False si fecha_baja ya
        pasó, aunque hasta_texto contenga 'SIN TERMINO'.
        """
        hoy = timezone.now().date()
        fecha_baja_pasada = hoy - datetime.timedelta(days=5)

        cargo = CargoDocente.objects.create(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TIT",
            activo=True,
            hasta_texto="SIN TERMINO",
            fecha_baja=fecha_baja_pasada,
        )

        self.assertFalse(cargo.es_designacion_vigente(fecha_referencia=hoy))

    def test_guardar_cargo_titular_normaliza_a_tit(self):
        """
        3. Verificar que al guardar un cargo con situacion_revista='TITULAR',
        quede guardado y persistido normalizado como 'TIT'.
        """
        cargo = CargoDocente(
            docente=self.docente,
            materia=self.espacio,
            situacion_revista="TITULAR",
            horas_lunes=4,
        )
        cargo.save()
        cargo.refresh_from_db()

        self.assertEqual(cargo.situacion_revista, "TIT")


class PersonalFormsTests(TestCase):
    """Pruebas unitarias para DocenteForm y CargoDocenteForm."""

    def setUp(self):
        self.docente = Docente.objects.create(
            dni="22333444",
            apellido="BENÍTEZ",
            nombre="Carlos",
            sexo="M",
        )
        self.docente_suplente = Docente.objects.create(
            dni="25666777",
            apellido="FERNÁNDEZ",
            nombre="Mariana",
            sexo="F",
        )
        self.espacio = EspacioCurricular.objects.create(
            codigo="BD-101",
            nombre="Bases de Datos I",
            carrera="Software",
            anio=1,
        )

    def test_docente_form_valido(self):
        """Valida alta de docente con limpieza de DNI y nombres."""
        form = DocenteForm(
            data={
                "dni": "35.888.999",
                "tipo_documento": "DNI",
                "apellido": "sánchez",
                "nombre": "rodrigo manuel",
                "sexo": "M",
                "nacionalidad": "Argentina",
                "activo": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        docente = form.save()
        self.assertEqual(docente.dni, "35888999")
        self.assertEqual(docente.apellido, "SÁNCHEZ")
        self.assertEqual(docente.nombre, "Rodrigo Manuel")

    def test_docente_form_dni_duplicado_rechazado(self):
        """Rechaza DNI existente en otro registro."""
        form = DocenteForm(
            data={
                "dni": "22333444",
                "apellido": "OTRO",
                "nombre": "Persona",
                "sexo": "F",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)
        self.assertIn("Ya existe un docente", form.errors["dni"][0])

    def test_docente_form_fecha_nacimiento_futura_rechazada(self):
        """Rechaza fechas de nacimiento en el futuro."""
        futuro = datetime.date.today() + datetime.timedelta(days=10)
        form = DocenteForm(
            data={
                "dni": "40111222",
                "apellido": "LÓPEZ",
                "nombre": "Ana",
                "sexo": "F",
                "fecha_nacimiento": futuro.strftime("%Y-%m-%d"),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.errors)

    def test_cargo_docente_form_valido(self):
        """Valida creación exitosa de un cargo titular."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "tipo_cargo": "HORAS_CATEDRA",
                "situacion_revista": "TIT",
                "horas_lunes": 3,
                "horas_martes": 2,
                "activo": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        cargo = form.save()
        self.assertEqual(cargo.total_horas_semanales, 5)

    def test_cargo_docente_form_suplente_sin_reemplazado_rechazado_dp01(self):
        """RF-04: Exige docente reemplazado según formulario DP-01 para suplentes."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente_suplente.pk,
                "materia": self.espacio.pk,
                "tipo_cargo": "HORAS_CATEDRA",
                "situacion_revista": "SUPLENTE",
                "horas_lunes": 4,
                "activo": True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("docente_reemplazado", form.errors)
        self.assertIn("DP-01", form.errors["docente_reemplazado"][0])

    def test_cargo_docente_form_fecha_baja_anterior_a_alta_rechazada(self):
        """Rechaza fecha_baja menor que fecha_alta."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "situacion_revista": "INT",
                "fecha_alta": "2026-06-01",
                "fecha_baja": "2026-05-15",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_baja", form.errors)

    def test_cargo_docente_form_horas_negativas_rechazadas(self):
        """Rechaza horas cátedra menores a cero."""
        form = CargoDocenteForm(
            data={
                "docente": self.docente.pk,
                "materia": self.espacio.pk,
                "situacion_revista": "INT",
                "horas_lunes": -2,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("horas_lunes", form.errors)


class ImportadorCSVSincronizacionDualTests(TestCase):
    """
    Criterio de Aceptación Ticket 3.8:
    Test Importador: Verificar que una fecha real ingresada en el CSV popule
    simultáneamente fecha_baja y hasta_texto.
    """

    def test_importador_csv_fecha_real_popula_fecha_baja_y_hasta_texto(self):
        """
        Verifica que al parsear un CSV con fecha válida (ej: '31/12/2026'),
        se asigne datetime.date a fecha_baja Y TAMBIÉN el string a hasta_texto.
        """
        from apps.personal.importar_csv import importar_legajos_csv

        csv_data = (
            "DNI;APELLIDO;NOMBRE;DESDE;HASTA;SITUACION;MATERIA\n"
            "20333444;Alvarez;Carlos;15/03/2026;31/12/2026;INTERINO;Matemática I\n"
        )

        stats = importar_legajos_csv(csv_data)
        self.assertEqual(stats["docentes_creados"], 1)
        self.assertEqual(stats["cargos_creados"], 1)

        docente = Docente.objects.get(dni="20333444")
        self.assertEqual(docente.apellido, "Alvarez")
        self.assertEqual(docente.nombre, "Carlos")

        cargo = CargoDocente.objects.get(docente=docente)

        # Sincronización dual en HASTA
        self.assertEqual(cargo.fecha_baja, datetime.date(2026, 12, 31))
        self.assertEqual(cargo.hasta_texto, "31/12/2026")

        # Sincronización dual en DESDE
        self.assertEqual(cargo.fecha_alta, datetime.date(2026, 3, 15))
        self.assertEqual(cargo.desde_texto, "15/03/2026")

    def test_importador_csv_sin_termino_o_vacio_asigna_fecha_baja_none(self):
        """
        Verifica que si HASTA contiene 'SIN TERMINO', 'SIN TÉRMINO' o está vacío:
        asignar fecha_baja = None y hasta_texto = 'SIN TÉRMINO'.
        """
        from apps.personal.importar_csv import (
            importar_legajos_csv,
            parsear_fecha_hasta,
        )

        # Prueba directa del parser
        f_baja, h_txt = parsear_fecha_hasta("SIN TERMINO")
        self.assertIsNone(f_baja)
        self.assertEqual(h_txt, "SIN TÉRMINO")

        f_baja, h_txt = parsear_fecha_hasta("SIN TÉRMINO")
        self.assertIsNone(f_baja)
        self.assertEqual(h_txt, "SIN TÉRMINO")

        f_baja, h_txt = parsear_fecha_hasta("")
        self.assertIsNone(f_baja)
        self.assertEqual(h_txt, "SIN TÉRMINO")

        f_baja, h_txt = parsear_fecha_hasta(None)
        self.assertIsNone(f_baja)
        self.assertEqual(h_txt, "SIN TÉRMINO")

        # Prueba vía importación CSV
        csv_data = (
            "DNI;APELLIDO;NOMBRE;DESDE;HASTA\n"
            "40111222;Benitez;Laura;01/04/2026;SIN TERMINO\n"
            "40111333;Canteros;Marcos;01/04/2026;SIN TÉRMINO\n"
            "40111444;Duarte;Elena;01/04/2026;\n"
        )
        importar_legajos_csv(csv_data)

        c1 = CargoDocente.objects.get(docente__dni="40111222")
        self.assertIsNone(c1.fecha_baja)
        self.assertEqual(c1.hasta_texto, "SIN TÉRMINO")

        c2 = CargoDocente.objects.get(docente__dni="40111333")
        self.assertIsNone(c2.fecha_baja)
        self.assertEqual(c2.hasta_texto, "SIN TÉRMINO")

        c3 = CargoDocente.objects.get(docente__dni="40111444")
        self.assertIsNone(c3.fecha_baja)
        self.assertEqual(c3.hasta_texto, "SIN TÉRMINO")


class DocenteListViewPaginacionTests(TestCase):
    """
    Verifica que DocenteListView configure obligatoriamente paginate_by = 25
    y funcione la paginación con más de 25 registros.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="operador", password="pass123")
        self.client.login(username="operador", password="pass123")

    def test_docente_listview_paginate_by_25(self):
        from apps.personal.views import DocenteListView
        self.assertEqual(DocenteListView.paginate_by, 25)

    def test_docente_listview_paginacion_30_elementos(self):
        from django.urls import reverse
        for i in range(30):
            Docente.objects.create(
                dni=f"90000{i:03d}",
                apellido=f"DocenteApellido{i:03d}",
                nombre=f"DocenteNombre{i:03d}",
            )

        response = self.client.get(reverse("personal:docente_list"))
        self.assertEqual(response.status_code, 200)

        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.num_pages, 2)
        self.assertEqual(len(page_obj.object_list), 25)
        self.assertEqual(page_obj.paginator.count, 30)

        # Página 2
        url_p2 = reverse("personal:docente_list") + "?page=2"
        response_p2 = self.client.get(url_p2)
        self.assertEqual(len(response_p2.context["page_obj"].object_list), 5)


class ImportarCSVWebTests(TestCase):
    """
    Pruebas para la vista y permisos de importación masiva de CSV en Personal:
    - Acceso permitido únicamente a superusuarios y Admin_Institucional.
    - Rechazo con HTTP 403 Forbidden para Bedelia_Operadoras y Consulta_Directiva.
    - Procesamiento exitoso de archivo CSV válido.
    - Visibilidad condicional del botón 'Importar CSV' en docente_list.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        self.user_admin = User.objects.create_user(
            username="admin_inst_user", password="password123"
        )
        group_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.user_admin.groups.add(group_admin)

        self.superuser = User.objects.create_superuser(
            username="super_personal",
            password="password123",
            email="super@iesetyfp.edu.ar",
        )

        self.user_bedelia = User.objects.create_user(
            username="bedelia_user", password="password123"
        )
        group_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.user_bedelia.groups.add(group_bedelia)

        self.user_consulta = User.objects.create_user(
            username="consulta_user", password="password123"
        )
        group_consulta, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )
        self.user_consulta.groups.add(group_consulta)

    def test_acceso_formulario_permitido_admin_institucional_y_superuser(self):
        """Valida que Admin_Institucional y superusuario accedan con HTTP 200."""
        from django.urls import reverse

        self.client.login(username="admin_inst_user", password="password123")
        response = self.client.get(reverse("personal:importar_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importar Personal y Cargos")
        self.assertContains(response, 'type="file"')

        self.client.login(username="super_personal", password="password123")
        response_super = self.client.get(reverse("personal:importar_csv"))
        self.assertEqual(response_super.status_code, 200)

    def test_acceso_denegado_403_bedelia_y_consulta(self):
        """
        Valida que Bedelia_Operadoras y Consulta_Directiva reciban HTTP 403 Forbidden.
        """
        from django.urls import reverse

        # Bedelía recibe 403 en GET y POST
        self.client.login(username="bedelia_user", password="password123")
        resp_bedelia_get = self.client.get(reverse("personal:importar_csv"))
        self.assertEqual(resp_bedelia_get.status_code, 403)
        resp_bedelia_post = self.client.post(reverse("personal:importar_csv"))
        self.assertEqual(resp_bedelia_post.status_code, 403)

        # Consulta Directiva recibe 403 en GET y POST
        self.client.login(username="consulta_user", password="password123")
        resp_cons_get = self.client.get(reverse("personal:importar_csv"))
        self.assertEqual(resp_cons_get.status_code, 403)
        resp_cons_post = self.client.post(reverse("personal:importar_csv"))
        self.assertEqual(resp_cons_post.status_code, 403)

    def test_procesar_archivo_csv_valido_exitosamente(self):
        """
        Valida que subir un archivo CSV válido procese los docentes y cargos,
        aplique mapeo 'TITULAR' -> 'TIT', y redirija a personal:docente_list.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse

        contenido_csv = (
            "DNI;APELLIDO;NOMBRE;SITUACION_REVISTA;MATERIA;HORAS_LUNES;DESDE;HASTA\n"
            "45111222;Sosa;Esteban;TITULAR;Algoritmos;4;01/03/2026;31/12/2026\n"
        )
        csv_file = SimpleUploadedFile(
            "docentes_test.csv",
            contenido_csv.encode("utf-8-sig"),
            content_type="text/csv",
        )

        self.client.login(username="admin_inst_user", password="password123")
        response = self.client.post(
            reverse("personal:importar_csv"),
            {"archivo": csv_file},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("personal:docente_list"))

        # Verificar creación del Docente
        docente = Docente.objects.get(dni="45111222")
        self.assertEqual(docente.apellido, "Sosa")
        self.assertEqual(docente.nombre, "Esteban")

        # Verificar creación y mapeo del CargoDocente
        cargo = CargoDocente.objects.get(docente=docente)
        self.assertEqual(cargo.situacion_revista, "TIT")
        self.assertEqual(cargo.horas_lunes, 4)

    def test_visibilidad_boton_importar_csv_en_docente_list(self):
        """
        Valida que el botón 'Importar CSV' solo sea visible en la lista
        para administradores y superusuarios.
        """
        from django.urls import reverse

        # Admin ve el botón
        self.client.login(username="admin_inst_user", password="password123")
        resp_admin = self.client.get(reverse("personal:docente_list"))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "Importar CSV")
        self.assertContains(resp_admin, reverse("personal:importar_csv"))

        # Bedelía y Consulta no lo ven
        self.client.login(username="bedelia_user", password="password123")
        resp_bedelia = self.client.get(reverse("personal:docente_list"))
        self.assertNotContains(resp_bedelia, reverse("personal:importar_csv"))

        self.client.login(username="consulta_user", password="password123")
        resp_consulta = self.client.get(reverse("personal:docente_list"))
        self.assertNotContains(resp_consulta, reverse("personal:importar_csv"))


class CargoDocenteAdminSecurityTests(TestCase):
    """
    Validaciones de seguridad para Ticket 3.9.2:
    Candado de eliminación física de cargos desde el panel admin de Django.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        self.factory = RequestFactory()
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin_cargo_sec",
            password="adminpassword123",
            email="admin@iesetyfp.edu.ar",
        )
        self.docente = Docente.objects.create(
            dni="29999888",
            apellido="SeguridadDocente",
            nombre="Juan",
            sexo="M",
        )
        self.cargo = CargoDocente.objects.create(
            docente=self.docente,
            situacion_revista="TIT",
            horas_lunes=3,
        )

    def test_cargodocente_admin_has_delete_permission_false(self):
        """Verifica que has_delete_permission retorne False siempre."""
        from django.contrib import admin

        request = self.factory.get("/admin/")
        request.user = self.admin_user
        cargo_admin = admin.site._registry[CargoDocente]

        self.assertFalse(cargo_admin.has_delete_permission(request))
        self.assertFalse(
            cargo_admin.has_delete_permission(request, obj=self.cargo)
        )

    def test_cargodocente_admin_sin_acciones_borrado_masivo(self):
        """Verifica que 'delete_selected' no esté presente en acciones admin."""
        from django.contrib import admin

        request = self.factory.get("/admin/")
        request.user = self.admin_user
        cargo_admin = admin.site._registry[CargoDocente]

        acciones = cargo_admin.get_actions(request)
        self.assertNotIn("delete_selected", acciones)

    def test_cargodocente_admin_vistas_bloquean_borrado(self):
        """Verifica que el form no tenga botón de borrar y la vista delete dé 403."""
        from django.urls import reverse

        self.client.login(
            username="admin_cargo_sec", password="adminpassword123"
        )

        url_change = reverse(
            "admin:personal_cargodocente_change", args=[self.cargo.pk]
        )
        url_delete = reverse(
            "admin:personal_cargodocente_delete", args=[self.cargo.pk]
        )

        resp_change = self.client.get(url_change)
        self.assertEqual(resp_change.status_code, 200)
        self.assertNotContains(resp_change, "deletelink-box")
        self.assertNotContains(resp_change, url_delete)

        resp_delete = self.client.get(url_delete)
        self.assertEqual(resp_delete.status_code, 403)


class DocenteCRUDSeguridadTests(TestCase):
    """
    Pruebas para el Ticket 6: Pantalla 1 — CRUD Personal (SEGURIDAD).
    1. Bedelia en el UpdateView no puede ver ni cambiar el estado 'activo'.
    2. Administrador ('director') ejecuta exitosamente /baja/ (activo=False).
    3. Bedelia ('zaquino') recibe 403 Forbidden al ejecutar el endpoint /baja/.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group, Permission

        User = get_user_model()

        # Grupos de seguridad
        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_consulta, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )

        # Asignar permisos básicos a Bedelia (add_docente, change_docente, view_docente)
        perms_bedelia = Permission.objects.filter(
            codename__in=[
                "add_docente",
                "change_docente",
                "view_docente",
            ]
        )
        self.grupo_bedelia.permissions.set(perms_bedelia)

        # Asignar permisos de visualización a Consulta
        perms_consulta = Permission.objects.filter(codename="view_docente")
        self.grupo_consulta.permissions.set(perms_consulta)

        # Usuario Administrador: director
        self.director = User.objects.create_user(
            username="director",
            password="password123",
            is_staff=True,
        )
        self.director.groups.add(self.grupo_admin)

        # Usuario Bedelia: zaquino
        self.zaquino = User.objects.create_user(
            username="zaquino",
            password="password123",
            is_staff=True,
        )
        self.zaquino.groups.add(self.grupo_bedelia)

        # Usuario Consulta: msosa
        self.msosa = User.objects.create_user(
            username="msosa",
            password="password123",
            is_staff=True,
        )
        self.msosa.groups.add(self.grupo_consulta)

        # Docente de prueba
        self.docente = Docente.objects.create(
            dni="20111222",
            apellido="GONZÁLEZ",
            nombre="Laura Beatriz",
            sexo="F",
            contacto="laura@iesetyfp.edu.ar",
            activo=True,
        )

    def test_bedelia_update_view_no_puede_ver_ni_cambiar_activo(self):
        """
        Validación 1 (Ticket 6):
        Bedelia en el UpdateView no puede ver el campo 'activo' en el formulario
        ni modificar su estado mediante peticiones POST.
        """
        from django.urls import reverse

        self.client.login(username="zaquino", password="password123")
        url_update = reverse(
            "personal:docente_update", kwargs={"pk": self.docente.pk}
        )

        # 1. GET: el campo 'activo' no debe estar presente en el form ni en el HTML
        response = self.client.get(url_update)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("activo", response.context["form"].fields)
        self.assertNotContains(response, 'name="activo"')

        # 2. POST intentando desactivar al docente activo: debe ignorar 'activo'
        post_data = {
            "dni": self.docente.dni,
            "tipo_documento": "DNI",
            "apellido": "GONZÁLEZ",
            "nombre": "Laura Editada",
            "sexo": "F",
            "contacto": "editada@iesetyfp.edu.ar",
            "activo": False,
        }
        resp_post = self.client.post(url_update, post_data)
        self.assertEqual(resp_post.status_code, 302)

        self.docente.refresh_from_db()
        self.assertEqual(self.docente.nombre, "Laura Editada")
        self.assertTrue(
            self.docente.activo,
            "Bedelía no debe poder cambiar el estado activo a False.",
        )

        # 3. Caso inverso: si el docente está inactivo, Bedelía no puede activarlo
        self.docente.activo = False
        self.docente.save()

        post_data_activar = {
            "dni": self.docente.dni,
            "tipo_documento": "DNI",
            "apellido": "GONZÁLEZ",
            "nombre": "Laura Modificada",
            "sexo": "F",
            "contacto": "editada@iesetyfp.edu.ar",
            "activo": True,
        }
        resp_post2 = self.client.post(url_update, post_data_activar)
        self.assertEqual(resp_post2.status_code, 302)

        self.docente.refresh_from_db()
        self.assertFalse(
            self.docente.activo,
            "Bedelía no debe poder cambiar el estado inactivo a True.",
        )

    def test_admin_director_ejecuta_exitosamente_baja(self):
        """
        Validación 2 (Ticket 6):
        Un usuario Administrador ('director') ejecuta exitosamente /baja/
        y el Docente pasa a activo=False con auditoría.
        """
        from django.urls import reverse

        self.client.login(username="director", password="password123")
        url_baja = reverse(
            "personal:docente_baja", kwargs={"pk": self.docente.pk}
        )

        # GET a baja muestra la confirmación de baja
        resp_get = self.client.get(url_baja)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "¿Confirmar baja lógica del docente?")

        # POST a baja ejecuta la baja lógica
        response = self.client.post(url_baja)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("personal:docente_list"))

        self.docente.refresh_from_db()
        self.assertFalse(self.docente.activo)
        self.assertEqual(self.docente.modificado_por, self.director)

    def test_bedelia_zaquino_recibe_403_al_intentar_baja(self):
        """
        Validación 3 (Ticket 6):
        Un usuario de Bedelia ('zaquino') recibe 403 Forbidden al intentar
        ejecutar el endpoint /baja/ tanto por GET como por POST.
        """
        from django.urls import reverse

        self.client.login(username="zaquino", password="password123")
        url_baja = reverse(
            "personal:docente_baja", kwargs={"pk": self.docente.pk}
        )

        # GET debe retornar 403
        resp_get = self.client.get(url_baja)
        self.assertEqual(resp_get.status_code, 403)

        # POST debe retornar 403
        resp_post = self.client.post(url_baja)
        self.assertEqual(resp_post.status_code, 403)

        # El docente debe continuar activo
        self.docente.refresh_from_db()
        self.assertTrue(self.docente.activo)

    def test_consulta_recibe_403_al_intentar_baja(self):
        """
        Valida que un usuario de Consulta_Directiva reciba 403 Forbidden
        al intentar dar de baja a un docente.
        """
        from django.urls import reverse

        self.client.login(username="msosa", password="password123")
        url_baja = reverse(
            "personal:docente_baja", kwargs={"pk": self.docente.pk}
        )

        resp_post = self.client.post(url_baja)
        self.assertEqual(resp_post.status_code, 403)

        self.docente.refresh_from_db()
        self.assertTrue(self.docente.activo)

    def test_admin_director_puede_modificar_activo_en_update_view(self):
        """
        Valida que un administrador institucional sí vea y pueda cambiar el
        campo 'activo' desde el formulario de edición.
        """
        from django.urls import reverse

        self.client.login(username="director", password="password123")
        url_update = reverse(
            "personal:docente_update", kwargs={"pk": self.docente.pk}
        )

        response = self.client.get(url_update)
        self.assertEqual(response.status_code, 200)
        self.assertIn("activo", response.context["form"].fields)
        self.assertContains(response, 'name="activo"')

        post_data = {
            "dni": self.docente.dni,
            "tipo_documento": "DNI",
            "apellido": "GONZÁLEZ",
            "nombre": "Laura Admin",
            "sexo": "F",
            "contacto": "admin_edit@iesetyfp.edu.ar",
            "activo": False,
        }
        resp_post = self.client.post(url_update, post_data)
        self.assertEqual(resp_post.status_code, 302)

        self.docente.refresh_from_db()
        self.assertFalse(self.docente.activo)

    def test_docente_create_view_bedelia_alta_exitosa(self):
        """
        Valida que un usuario de Bedelía pueda crear un nuevo docente
        y que quede activo por defecto.
        """
        from django.urls import reverse

        self.client.login(username="zaquino", password="password123")
        url_create = reverse("personal:docente_create")

        # GET: activo no está en el form de Bedelía
        resp_get = self.client.get(url_create)
        self.assertEqual(resp_get.status_code, 200)
        self.assertNotIn("activo", resp_get.context["form"].fields)

        post_data = {
            "dni": "39999888",
            "tipo_documento": "DNI",
            "apellido": "MOLINA",
            "nombre": "Marcos",
            "sexo": "M",
            "nacionalidad": "Argentina",
        }
        resp_post = self.client.post(url_create, post_data)
        self.assertEqual(resp_post.status_code, 302)

        doc_creado = Docente.objects.get(dni="39999888")
        self.assertTrue(doc_creado.activo)
        self.assertEqual(doc_creado.creado_por, self.zaquino)

    def test_docente_list_view_paginacion_obligatoria(self):
        """
        Valida que DocenteListView configure paginate_by = 25.
        """
        from apps.personal.views import DocenteListView

        self.assertEqual(DocenteListView.paginate_by, 25)


class ABMCCatalogosInstitucionalesTests(TestCase):
    """
    Pruebas automatizadas para el Ticket 10.1:
    - ABMC de Catálogos Institucionales (Carrera, CargoCatalogo, TipoAutorizacion).
    - Criterios de Aceptación:
      * Bedelía recibe HTTP 403 Forbidden al intentar entrar a las rutas.
      * Consulta Directiva recibe HTTP 403 Forbidden.
      * Usuarios anónimos son redirigidos a login (HTTP 302).
      * El Administrador puede listar, crear y actualizar los catálogos.
    """

    def setUp(self):
        from django.contrib.auth.models import Group, User

        self.grupo_admin, _ = Group.objects.get_or_create(
            name="Admin_Institucional"
        )
        self.grupo_bedelia, _ = Group.objects.get_or_create(
            name="Bedelia_Operadoras"
        )
        self.grupo_consulta, _ = Group.objects.get_or_create(
            name="Consulta_Directiva"
        )

        self.director = User.objects.create_user(
            username="director_catalogos",
            password="password123",
            is_staff=True,
        )
        self.director.groups.add(self.grupo_admin)

        self.zaquino = User.objects.create_user(
            username="zaquino_catalogos",
            password="password123",
            is_staff=True,
        )
        self.zaquino.groups.add(self.grupo_bedelia)

        self.msosa = User.objects.create_user(
            username="msosa_catalogos",
            password="password123",
            is_staff=True,
        )
        self.msosa.groups.add(self.grupo_consulta)

        self.superuser = User.objects.create_superuser(
            username="admin_catalogos",
            password="password123",
            email="admin@iesetyfp.edu.ar",
        )

        # Registros iniciales
        self.carrera = Carrera.objects.create(
            codigo="TEC-DS",
            nombre="Tecnicatura Superior en Desarrollo de Software",
            activo=True,
        )
        self.cargo_cat = CargoCatalogo.objects.create(
            codigo="MEP",
            descripcion="Maestro de Enseñanza Práctica",
            activo=True,
        )
        self.tipo_aut = TipoAutorizacion.objects.create(
            nombre="RESOLUCIÓN",
            activo=True,
        )

    def test_usuario_anonimo_es_redirigido_a_login(self):
        """
        Los usuarios anónimos que intentan acceder a cualquier pantalla
        de catálogos deben ser redirigidos (302) a la pantalla de login.
        """
        from django.urls import reverse

        urls = [
            reverse("personal:catalogos_hub"),
            reverse("personal:carrera_list"),
            reverse("personal:carrera_create"),
            reverse("personal:carrera_update", kwargs={"pk": self.carrera.pk}),
            reverse("personal:cargocatalogo_list"),
            reverse("personal:cargocatalogo_create"),
            reverse(
                "personal:cargocatalogo_update",
                kwargs={"pk": self.cargo_cat.pk},
            ),
            reverse("personal:tipoautorizacion_list"),
            reverse("personal:tipoautorizacion_create"),
            reverse(
                "personal:tipoautorizacion_update",
                kwargs={"pk": self.tipo_aut.pk},
            ),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                302,
                f"La URL {url} no redirigió a login para usuario anónimo.",
            )

    def test_bedelia_recibe_403_en_todas_las_rutas_de_catalogos(self):
        """
        Criterio de Aceptación:
        Bedelia recibe HTTP 403 al intentar entrar a las rutas de catálogos.
        """
        from django.urls import reverse

        self.client.login(username="zaquino_catalogos", password="password123")

        rutas_get = [
            reverse("personal:catalogos_hub"),
            reverse("personal:carrera_list"),
            reverse("personal:carrera_create"),
            reverse("personal:carrera_update", kwargs={"pk": self.carrera.pk}),
            reverse("personal:cargocatalogo_list"),
            reverse("personal:cargocatalogo_create"),
            reverse(
                "personal:cargocatalogo_update",
                kwargs={"pk": self.cargo_cat.pk},
            ),
            reverse("personal:tipoautorizacion_list"),
            reverse("personal:tipoautorizacion_create"),
            reverse(
                "personal:tipoautorizacion_update",
                kwargs={"pk": self.tipo_aut.pk},
            ),
        ]
        for url in rutas_get:
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code,
                403,
                f"Bedelía no recibió 403 en GET {url}",
            )

        rutas_post = [
            (
                reverse("personal:carrera_create"),
                {"codigo": "X1", "nombre": "Carrera X", "activo": True},
            ),
            (
                reverse(
                    "personal:carrera_update", kwargs={"pk": self.carrera.pk}
                ),
                {"codigo": "TEC-DS", "nombre": "Cambio", "activo": True},
            ),
            (
                reverse("personal:cargocatalogo_create"),
                {"codigo": "X2", "descripcion": "Cargo X", "activo": True},
            ),
            (
                reverse(
                    "personal:cargocatalogo_update",
                    kwargs={"pk": self.cargo_cat.pk},
                ),
                {"codigo": "MEP", "descripcion": "Cambio", "activo": True},
            ),
            (
                reverse("personal:tipoautorizacion_create"),
                {"nombre": "AUT-X", "activo": True},
            ),
            (
                reverse(
                    "personal:tipoautorizacion_update",
                    kwargs={"pk": self.tipo_aut.pk},
                ),
                {"nombre": "RESOL-CAMBIO", "activo": True},
            ),
        ]
        for url, data in rutas_post:
            resp = self.client.post(url, data)
            self.assertEqual(
                resp.status_code,
                403,
                f"Bedelía no recibió 403 en POST {url}",
            )

    def test_consulta_directiva_recibe_403_en_todas_las_rutas(self):
        """
        Consulta_Directiva tampoco puede acceder a la gestión de catálogos base.
        """
        from django.urls import reverse

        self.client.login(username="msosa_catalogos", password="password123")
        url_hub = reverse("personal:catalogos_hub")
        response = self.client.get(url_hub)
        self.assertEqual(response.status_code, 403)

    def test_admin_institucional_y_superuser_acceden_con_200(self):
        """
        Admin_Institucional y superusuarios acceden con HTTP 200 al Hub y listas.
        """
        from django.urls import reverse

        # Admin Institucional
        self.client.login(username="director_catalogos", password="password123")
        resp_admin = self.client.get(reverse("personal:catalogos_hub"))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "Catálogos Institucionales")

        # Superusuario
        self.client.login(username="admin_catalogos", password="password123")
        resp_su = self.client.get(reverse("personal:catalogos_hub"))
        self.assertEqual(resp_su.status_code, 200)

    def test_carrera_list_y_busqueda(self):
        """
        El Administrador puede listar y filtrar carreras por término de búsqueda.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_list = reverse("personal:carrera_list")

        # Listado completo
        resp = self.client.get(url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TEC-DS")
        self.assertContains(resp, "Desarrollo de Software")

        # Búsqueda por término coincidente
        resp_search = self.client.get(url_list, {"q": "Software"})
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, "TEC-DS")

        # Búsqueda sin coincidencias
        resp_empty = self.client.get(url_list, {"q": "Inexistente"})
        self.assertEqual(resp_empty.status_code, 200)
        self.assertNotContains(resp_empty, "TEC-DS")

    def test_carrera_crear_exitosa_y_validacion_unicidad(self):
        """
        El Administrador puede crear una nueva Carrera y se valida unicidad de código.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_create = reverse("personal:carrera_create")

        # GET formulario de creación
        resp_get = self.client.get(url_create)
        self.assertEqual(resp_get.status_code, 200)

        # POST alta exitosa
        data_nueva = {
            "codigo": "TEC-REDES",
            "nombre": "Tecnicatura Superior en Redes e Infraestructura",
            "activo": True,
        }
        resp_post = self.client.post(url_create, data_nueva)
        self.assertEqual(resp_post.status_code, 302)
        self.assertTrue(Carrera.objects.filter(codigo="TEC-REDES").exists())

        # POST duplicado: debe fallar con error de validación
        resp_dup = self.client.post(url_create, data_nueva)
        self.assertEqual(resp_dup.status_code, 200)
        self.assertFormError(
            resp_dup.context["form"],
            "codigo",
            "Ya existe una carrera registrada con este código.",
        )

    def test_carrera_editar_exitosa(self):
        """
        El Administrador puede actualizar una Carrera existente.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_update = reverse(
            "personal:carrera_update", kwargs={"pk": self.carrera.pk}
        )

        resp_get = self.client.get(url_update)
        self.assertEqual(resp_get.status_code, 200)

        data_update = {
            "codigo": "TEC-DS",
            "nombre": "Tecnicatura Superior en Software (Plan Renovado)",
            "activo": False,
        }
        resp_post = self.client.post(url_update, data_update)
        self.assertEqual(resp_post.status_code, 302)

        self.carrera.refresh_from_db()
        self.assertEqual(
            self.carrera.nombre,
            "Tecnicatura Superior en Software (Plan Renovado)",
        )
        self.assertFalse(self.carrera.activo)

    def test_cargocatalogo_list_y_busqueda(self):
        """
        El Administrador puede listar y filtrar cargos de catálogo.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_list = reverse("personal:cargocatalogo_list")

        resp = self.client.get(url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "MEP")

        resp_search = self.client.get(url_list, {"q": "Práctica"})
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, "MEP")

    def test_cargocatalogo_crear_exitosa_y_validacion_unicidad(self):
        """
        El Administrador puede crear cargos de catálogo y se valida código único.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_create = reverse("personal:cargocatalogo_create")

        data_nuevo = {
            "codigo": "DIR",
            "descripcion": "Director / Rectora de Instituto",
            "activo": True,
        }
        resp = self.client.post(url_create, data_nuevo)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CargoCatalogo.objects.filter(codigo="DIR").exists())

        # Duplicado
        resp_dup = self.client.post(url_create, data_nuevo)
        self.assertEqual(resp_dup.status_code, 200)
        self.assertFormError(
            resp_dup.context["form"],
            "codigo",
            "Ya existe un cargo registrado con este código.",
        )

    def test_cargocatalogo_editar_exitosa(self):
        """
        El Administrador puede actualizar la descripción y estado de un cargo.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_update = reverse(
            "personal:cargocatalogo_update", kwargs={"pk": self.cargo_cat.pk}
        )

        data_update = {
            "codigo": "MEP",
            "descripcion": "Maestro de Taller y Enseñanza Práctica",
            "activo": True,
        }
        resp = self.client.post(url_update, data_update)
        self.assertEqual(resp.status_code, 302)

        self.cargo_cat.refresh_from_db()
        self.assertEqual(
            self.cargo_cat.descripcion,
            "Maestro de Taller y Enseñanza Práctica",
        )

    def test_tipoautorizacion_list_y_busqueda(self):
        """
        El Administrador puede listar y filtrar tipos de autorización.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_list = reverse("personal:tipoautorizacion_list")

        resp = self.client.get(url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "RESOLUCIÓN")

        resp_search = self.client.get(url_list, {"q": "RESOL"})
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, "RESOLUCIÓN")

    def test_tipoautorizacion_crear_exitosa_y_validacion_unicidad(self):
        """
        El Administrador puede crear un tipo de autorización y se valida nombre único.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_create = reverse("personal:tipoautorizacion_create")

        data_nuevo = {
            "nombre": "DISPOSICIÓN",
            "activo": True,
        }
        resp = self.client.post(url_create, data_nuevo)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            TipoAutorizacion.objects.filter(nombre="DISPOSICIÓN").exists()
        )

        # Duplicado
        resp_dup = self.client.post(url_create, data_nuevo)
        self.assertEqual(resp_dup.status_code, 200)
        self.assertFormError(
            resp_dup.context["form"],
            "nombre",
            "Ya existe un tipo de autorización con este nombre.",
        )

    def test_tipoautorizacion_editar_exitosa(self):
        """
        El Administrador puede actualizar el nombre y estado de un tipo de autorización.
        """
        from django.urls import reverse

        self.client.login(username="director_catalogos", password="password123")
        url_update = reverse(
            "personal:tipoautorizacion_update",
            kwargs={"pk": self.tipo_aut.pk},
        )

        data_update = {
            "nombre": "DECRETO PROVINCIAL",
            "activo": False,
        }
        resp = self.client.post(url_update, data_update)
        self.assertEqual(resp.status_code, 302)

        self.tipo_aut.refresh_from_db()
        self.assertEqual(self.tipo_aut.nombre, "DECRETO PROVINCIAL")
        self.assertFalse(self.tipo_aut.activo)

    def test_paginacion_obligatoria_en_catalogos(self):
        """
        Valida que las tres vistas de listado de catálogos tengan paginate_by = 25.
        """
        from apps.personal.views import (
            CargoCatalogoListView,
            CarreraListView,
            TipoAutorizacionListView,
        )

        self.assertEqual(CarreraListView.paginate_by, 25)
        self.assertEqual(CargoCatalogoListView.paginate_by, 25)
        self.assertEqual(TipoAutorizacionListView.paginate_by, 25)
