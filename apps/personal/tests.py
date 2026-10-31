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
from apps.personal.models import CargoDocente, Docente, EspacioCurricular


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
