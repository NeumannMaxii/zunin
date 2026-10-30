"""
Utilidades y clases base de Formularios con Tailwind CSS para Proyecto Zunin.
Centraliza estilos visuales, clases de error y personalización de widgets.
"""

from django import forms
from django.forms.utils import ErrorList


class TailwindErrorList(ErrorList):
    """
    Renderizador de listas de errores con tipografía y colores de alerta legibles en Tailwind.
    """

    def __init__(self, initlist=None, error_class=None, **kwargs):
        error_class = (
            error_class
            or "text-xs text-rose-600 mt-1 font-medium list-disc list-inside space-y-0.5"
        )
        super().__init__(initlist, error_class=error_class, **kwargs)


class TailwindFormMixin:
    """
    Mixin para inyectar automáticamente clases de Tailwind CSS en widgets de formularios.
    Soporta text inputs, selects, textareas, checkboxes y selectores de fecha nativos (type="date").
    """

    BASE_INPUT_CLASSES = (
        "block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 "
        "placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-institucional-600 "
        "focus:border-institucional-600 transition-colors"
    )
    BASE_SELECT_CLASSES = (
        "block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 "
        "text-sm focus:outline-none focus:ring-2 focus:ring-institucional-600 "
        "focus:border-institucional-600 transition-colors"
    )
    BASE_TEXTAREA_CLASSES = (
        "block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 "
        "placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-institucional-600 "
        "focus:border-institucional-600 transition-colors"
    )
    BASE_CHECKBOX_CLASSES = (
        "h-4 w-4 rounded border-slate-300 text-institucional-600 "
        "focus:ring-institucional-600 transition-colors cursor-pointer"
    )
    ERROR_WIDGET_CLASSES = (
        "border-rose-500 text-rose-900 focus:ring-rose-500 focus:border-rose-500"
    )

    error_css_class = "has-error"
    required_css_class = "is-required"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("error_class", TailwindErrorList)
        super().__init__(*args, **kwargs)
        self.apply_tailwind_widgets()

    def apply_tailwind_widgets(self):
        """Aplica dinámicamente las clases CSS de Tailwind según el tipo de widget."""
        for field_name, field in self.fields.items():
            widget = field.widget

            # Asegurar tipo date para DateInput
            if isinstance(widget, forms.DateInput):
                if "type" not in widget.attrs:
                    widget.attrs["type"] = "date"

            current_class = widget.attrs.get("class", "")

            if isinstance(widget, forms.CheckboxInput):
                target_base = self.BASE_CHECKBOX_CLASSES
            elif isinstance(widget, forms.Textarea):
                target_base = self.BASE_TEXTAREA_CLASSES
                if widget.attrs.get("rows") in (None, "10", 10):
                    widget.attrs["rows"] = 3
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                target_base = self.BASE_SELECT_CLASSES
            else:
                target_base = self.BASE_INPUT_CLASSES

            if not current_class:
                widget.attrs["class"] = target_base
            elif target_base not in current_class:
                widget.attrs["class"] = f"{current_class} {target_base}".strip()

    def full_clean(self):
        """Sobrescribe full_clean para resaltar visualmente con borde rojo los campos con error."""
        super().full_clean()
        if self._errors:
            for field_name in self._errors:
                if field_name in self.fields:
                    widget = self.fields[field_name].widget
                    classes = widget.attrs.get("class", "")
                    if self.ERROR_WIDGET_CLASSES not in classes:
                        widget.attrs["class"] = f"{classes} {self.ERROR_WIDGET_CLASSES}".strip()


class TailwindModelForm(TailwindFormMixin, forms.ModelForm):
    """Clase base de conveniencia para ModelForms estilizados con Tailwind CSS."""
    pass


class TailwindForm(TailwindFormMixin, forms.Form):
    """Clase base de conveniencia para Forms regulares estilizados con Tailwind CSS."""
    pass
