"""
Formularios para el módulo de Asistencia (Días No Laborables y Registro de Novedades).
Aplica diseño Tailwind CSS y validaciones con delegación a las reglas de modelo.
"""

from django import forms
from django.core.exceptions import ValidationError
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.core.forms import TailwindModelForm
from apps.personal.models import CargoDocente


class DiaNoLaborableForm(TailwindModelForm):
    """
    Formulario operativo para registrar feriados, asuetos y días no laborables.
    """

    class Meta:
        model = DiaNoLaborable
        fields = ["fecha", "tipo", "descripcion"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.TextInput(
                attrs={"placeholder": "Ej: Feriado Nacional - Día de la Memoria"}
            ),
        }

    def clean_descripcion(self):
        descripcion = self.cleaned_data.get("descripcion", "").strip()
        if not descripcion:
            raise forms.ValidationError("La descripción del día no laborable no puede estar vacía.")
        return descripcion

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha:
            qs = DiaNoLaborable.objects.filter(fecha=fecha)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Ya existe un día no laborable registrado para esta fecha."
                )
        return fecha


class RegistroAsistenciaForm(TailwindModelForm):
    """
    Formulario para la carga diaria de novedades de asistencia docente en Bedelía.
    Valida coherencia entre estado, marcas diarias (RF-08) y tipos de licencia (RN-06).
    """

    class Meta:
        model = RegistroAsistencia
        fields = [
            "docente",
            "cargo",
            "fecha",
            "fecha_hasta",
            "estado",
            "marca_diaria",
            "oficina",
            "anio_planilla",
            "justifica",
            "tipo_licencia",
            "numero_disposicion",
            "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "fecha_hasta": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Observaciones, motivo o justificación de la novedad...",
                }
            ),
            "numero_disposicion": forms.TextInput(
                attrs={"placeholder": "Ej: Disp. 024/2026"}
            ),
            "oficina": forms.TextInput(attrs={"placeholder": "1452"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].required = False
        self.fields["fecha_hasta"].required = False
        self.fields["tipo_licencia"].required = False
        self.fields["numero_disposicion"].required = False

        # Filtrar cargos disponibles según el docente seleccionado si está presente
        docente_id = None
        if "docente" in self.data:
            try:
                docente_id = int(self.data.get("docente"))
            except (ValueError, TypeError):
                pass
        elif self.instance and getattr(self.instance, "docente_id", None):
            docente_id = self.instance.docente_id

        if docente_id:
            self.fields["cargo"].queryset = CargoDocente.objects.filter(
                docente_id=docente_id, activo=True
            )

    def clean(self):
        cleaned_data = super().clean()
        fecha = cleaned_data.get("fecha")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        estado = cleaned_data.get("estado")
        marca_diaria = cleaned_data.get("marca_diaria")
        tipo_licencia = cleaned_data.get("tipo_licencia")
        docente = cleaned_data.get("docente")

        # Reglas de Licencia vs Presente
        if estado == "LICENCIA" and not tipo_licencia:
            self.add_error(
                "tipo_licencia",
                "Debe especificar el Tipo de Licencia cuando el estado es LICENCIA.",
            )

        if estado == "PRESENTE" and tipo_licencia:
            self.add_error(
                "tipo_licencia",
                "No debe asignar un Tipo de Licencia si el estado es PRESENTE.",
            )

        # Validación cronológica de fechas
        if fecha and fecha_hasta:
            if fecha_hasta < fecha:
                self.add_error(
                    "fecha_hasta",
                    "La fecha de finalización no puede ser anterior a la fecha inicial.",
                )
            elif fecha_hasta != fecha:
                es_inasistencia = (
                    estado == "AUSENTE"
                    or marca_diaria in ["I", "INA"]
                    or (
                        tipo_licencia
                        and getattr(tipo_licencia, "categoria", None) == "INASISTENCIA"
                    )
                )
                if es_inasistencia:
                    self.add_error(
                        "fecha_hasta",
                        "RN-06: Las inasistencias solamente pueden ser por un día.",
                    )

        # Validación de unicidad docente + fecha
        if docente and fecha:
            qs = RegistroAsistencia.objects.filter(docente=docente, fecha=fecha)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "fecha",
                    f"Ya existe un registro de asistencia para el docente {docente} en la fecha {fecha}.",
                )

        return cleaned_data
