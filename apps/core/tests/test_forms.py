"""
Pruebas para las utilidades de Formularios y el Mixin de Tailwind CSS (apps.core.forms).
"""

from django import forms
from django.test import SimpleTestCase
from apps.core.forms import TailwindForm


class DummyForm(TailwindForm):
    nombre = forms.CharField()
    fecha = forms.DateField(widget=forms.DateInput())
    opcion = forms.ChoiceField(choices=[("1", "Uno"), ("2", "Dos")])
    descripcion = forms.CharField(widget=forms.Textarea())
    activo = forms.BooleanField(required=False, widget=forms.CheckboxInput())


class TailwindFormsCoreTests(SimpleTestCase):
    def test_widgets_reciben_clases_tailwind(self):
        """Los widgets se inicializan con sus correspondientes clases Tailwind."""
        form = DummyForm()

        # Input texto
        self.assertIn(
            "border-slate-300", form.fields["nombre"].widget.attrs["class"]
        )
        self.assertIn(
            "focus:ring-institucional-600",
            form.fields["nombre"].widget.attrs["class"],
        )

        # Date input recibe type="date"
        self.assertEqual(form.fields["fecha"].widget.attrs.get("type"), "date")

        # Select
        self.assertIn(
            "border-slate-300", form.fields["opcion"].widget.attrs["class"]
        )

        # Textarea
        self.assertIn("rows", form.fields["descripcion"].widget.attrs)
        self.assertEqual(form.fields["descripcion"].widget.attrs["rows"], 3)

        # Checkbox
        self.assertIn(
            "cursor-pointer", form.fields["activo"].widget.attrs["class"]
        )

    def test_campos_con_error_reciben_clases_visuales_de_alerta(self):
        """Los campos con error incorporan clases de alerta roja."""
        form = DummyForm(data={})
        self.assertFalse(form.is_valid())

        # Nombre falló por ser requerido
        nombre_widget_class = form.fields["nombre"].widget.attrs["class"]
        self.assertIn("border-rose-500", nombre_widget_class)
        self.assertIn("text-rose-900", nombre_widget_class)

    def test_tailwind_error_list_renderiza_clases_legibles(self):
        """La lista de errores emite estilos de Tailwind legibles para el usuario."""
        form = DummyForm(data={})
        self.assertFalse(form.is_valid())

        errors_html = str(form.errors["nombre"])
        self.assertIn("text-rose-600", errors_html)
        self.assertIn("text-xs", errors_html)
