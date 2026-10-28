"""
Pruebas automatizadas para el helper de auditoría polimórfico (Ticket 0.5).
Verifica audit_save y AuditoriaFormMixin en modelos con y sin campos de auditoría.
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from apps.asistencia.models import RegistroAsistencia
from apps.core.audit import AuditoriaFormMixin, audit_save
from apps.personal.models import CargoDocente, Docente


class AuditSavePolymorphicTests(TestCase):
    """
    Pruebas defensivas para audit_save en Docente, RegistroAsistencia
    y CargoDocente.
    """

    def setUp(self):
        User = get_user_model()
        self.user1 = User.objects.create_user(
            username="auditor1",
            password="password123",
        )
        self.user2 = User.objects.create_user(
            username="auditor2",
            password="password123",
        )

    def test_audit_save_docente_sin_attribute_error(self):
        """
        Verifica que procesar Docente mediante audit_save no lance
        AttributeError y asigne los campos de auditoría correctamente.
        """
        docente = Docente(
            dni="20999888",
            apellido="López",
            nombre="Carlos",
            sexo="M",
        )

        try:
            audit_save(docente, self.user1, created=True)
        except AttributeError as e:
            self.fail(f"audit_save levantó AttributeError en Docente: {e}")

        self.assertIsNotNone(docente.pk)
        self.assertEqual(docente.creado_por, self.user1)
        self.assertEqual(docente.modificado_por, self.user1)
        self.assertIsNotNone(docente.fecha_modificacion)

        # Actualización con created=False
        try:
            audit_save(docente, self.user2, created=False)
        except AttributeError as e:
            self.fail(f"audit_save levantó AttributeError al actualizar: {e}")

        docente.refresh_from_db()
        self.assertEqual(docente.creado_por, self.user1)
        self.assertEqual(docente.modificado_por, self.user2)

    def test_audit_save_registro_asistencia_sin_attribute_error(self):
        """
        Verifica que procesar RegistroAsistencia (AuditoriaModel) mediante
        audit_save no lance AttributeError y actualice creado_por y actualizado_en.
        """
        docente = Docente.objects.create(
            dni="30888777",
            apellido="Ruiz",
            nombre="Ana",
            sexo="F",
            creado_por=self.user1,
        )

        asistencia = RegistroAsistencia(
            docente=docente,
            fecha=datetime.date(2026, 10, 28),
            estado="PRESENTE",
        )

        try:
            audit_save(asistencia, self.user1, created=True)
        except AttributeError as e:
            self.fail(
                f"audit_save levantó AttributeError en RegistroAsistencia: {e}"
            )

        self.assertIsNotNone(asistencia.pk)
        self.assertEqual(asistencia.creado_por, self.user1)
        self.assertEqual(asistencia.modificado_por, self.user1)
        self.assertIsNotNone(asistencia.actualizado_en)

    def test_audit_save_cargo_docente_sin_attribute_error(self):
        """
        Verifica que procesar CargoDocente (modelo sin actualizado_en ni
        fecha_modificacion) no lance AttributeError por ausencia de campos.
        """
        docente = Docente.objects.create(
            dni="40777666",
            apellido="García",
            nombre="Lucas",
            sexo="M",
            creado_por=self.user1,
        )

        cargo = CargoDocente(
            docente=docente,
            materia=None,
            tipo_cargo="CARGO_ADM",
            situacion_revista="TITULAR",
            horas_lunes=5,
        )

        # Confirmamos la asimetría del modelo: no posee actualizado_en
        self.assertFalse(hasattr(cargo, "actualizado_en"))

        try:
            audit_save(cargo, self.user1, created=True)
        except AttributeError as e:
            self.fail(
                f"audit_save levantó AttributeError en CargoDocente: {e}"
            )

        self.assertIsNotNone(cargo.pk)
        self.assertEqual(cargo.creado_por, self.user1)
        self.assertEqual(cargo.modificado_por, self.user1)
        self.assertEqual(cargo.situacion_revista, "TIT")

    def test_audit_save_no_sobreescribe_creado_por_existente(self):
        """
        Verifica que si obj.creado_por_id ya existe, audit_save con created=True
        respete el creador original.
        """
        docente = Docente(
            dni="50666555",
            apellido="Fernández",
            nombre="Lucía",
            sexo="F",
            creado_por=self.user1,
        )
        docente.save()

        # Invocamos audit_save con created=True pero con user2
        audit_save(docente, self.user2, created=True)
        docente.refresh_from_db()

        self.assertEqual(docente.creado_por, self.user1)
        self.assertEqual(docente.modificado_por, self.user2)


class AuditoriaFormMixinTests(TestCase):
    """
    Pruebas para AuditoriaFormMixin en vistas de formularios basadas en clases.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="form_user",
            password="password123",
        )
        self.factory = RequestFactory()

    def test_form_valid_inyecta_auditoria(self):
        """
        Verifica que AuditoriaFormMixin intercepte form_valid e inyecte
        el usuario autenticado mediante audit_save.
        """
        class DummyForm:
            def __init__(self, instance):
                self.instance = instance

            def save(self, commit=True):
                return self.instance

        class DummyView(AuditoriaFormMixin):
            def __init__(self, request):
                self.request = request
                self.object = None

            def get_success_url(self):
                return "/exito/"

        request = self.factory.post("/dummy/")
        request.user = self.user

        docente = Docente(
            dni="60555444",
            apellido="Romero",
            nombre="Sofía",
            sexo="F",
        )
        form = DummyForm(instance=docente)
        view = DummyView(request=request)

        response = view.form_valid(form)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/exito/")
        self.assertIsNotNone(view.object.pk)
        self.assertEqual(view.object.creado_por, self.user)
        self.assertEqual(view.object.modificado_por, self.user)
