"""
Formularios para el módulo de Personal y Designaciones Docentes.
Maneja datos filiatorios del cuerpo docente y la asignación de cargos/horas cátedra.
"""

from datetime import date
from django import forms
from apps.core.forms import TailwindModelForm
from apps.personal.models import CargoDocente, Docente


class DocenteForm(TailwindModelForm):
    """
    Formulario para el alta y edición del legajo y datos de contacto de docentes.
    """

    class Meta:
        model = Docente
        fields = [
            "dni",
            "tipo_documento",
            "apellido",
            "nombre",
            "sexo",
            "fecha_nacimiento",
            "estado_civil",
            "nacionalidad",
            "cuil_dgi",
            "inscripcion_dgr",
            "domicilio_calle",
            "barrio",
            "localidad",
            "codigo_postal",
            "provincia",
            "contacto",
            "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "dni": forms.TextInput(attrs={"placeholder": "Ej: 28456123"}),
            "apellido": forms.TextInput(attrs={"placeholder": "Apellido del docente"}),
            "nombre": forms.TextInput(attrs={"placeholder": "Nombres del docente"}),
            "contacto": forms.TextInput(
                attrs={"placeholder": "Teléfono o correo electrónico"}
            ),
            "domicilio_calle": forms.TextInput(
                attrs={"placeholder": "Calle, número y piso"}
            ),
        }

    def clean_dni(self):
        dni = str(self.cleaned_data.get("dni", "")).strip()
        if not dni:
            raise forms.ValidationError("El DNI es un campo obligatorio.")
        if not dni.replace(".", "").isdigit():
            raise forms.ValidationError(
                "El DNI debe contener únicamente dígitos numéricos."
            )

        dni_clean = dni.replace(".", "")
        qs = Docente.objects.filter(dni=dni_clean)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe un docente registrado con este número de DNI."
            )
        return dni_clean

    def clean_apellido(self):
        apellido = self.cleaned_data.get("apellido", "").strip()
        if not apellido:
            raise forms.ValidationError("El apellido es obligatorio.")
        return apellido.upper()

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        if not nombre:
            raise forms.ValidationError("El nombre es obligatorio.")
        return nombre.title()

    def clean_cuil_dgi(self):
        cuil = self.cleaned_data.get("cuil_dgi", "")
        if cuil:
            cuil = str(cuil).strip()
        return cuil

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get("fecha_nacimiento")
        if fecha and fecha > date.today():
            raise forms.ValidationError(
                "La fecha de nacimiento no puede ser posterior a la "
                "fecha actual."
            )
        return fecha


class CargoDocenteForm(TailwindModelForm):
    """
    Formulario para la designación de cargos y distribución de horas semanales.
    Garantiza el cumplimiento del Formulario DP-01 para suplencias (RF-04).
    """

    DIAS_CAMPOS = [
        "horas_lunes",
        "horas_martes",
        "horas_miercoles",
        "horas_jueves",
        "horas_viernes",
    ]

    class Meta:
        model = CargoDocente
        fields = [
            "docente",
            "tipo_cargo",
            "codigo_cargo",
            "codigo_motivo",
            "carrera_ref",
            "cargo_catalogo",
            "tipo_autorizacion",
            "materia",
            "situacion_revista",
            "docente_reemplazado",
            "numero_autorizacion",
            "anio_autorizacion",
            "organismo_emisor",
            "horas_lunes",
            "horas_martes",
            "horas_miercoles",
            "horas_jueves",
            "horas_viernes",
            "desde_texto",
            "hasta_texto",
            "resolucion",
            "fecha_alta",
            "fecha_baja",
            "activo",
            "observaciones",
        ]
        widgets = {
            "fecha_alta": forms.DateInput(attrs={"type": "date"}),
            "fecha_baja": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Observaciones o detalles de designación...",
                }
            ),
            "codigo_cargo": forms.TextInput(
                attrs={"placeholder": "Ej: CARGO-BED-01"}
            ),
            "numero_autorizacion": forms.TextInput(
                attrs={"placeholder": "Ej: 145/26"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materia"].required = False
        self.fields["cargo_catalogo"].required = False
        self.fields["carrera_ref"].required = False
        self.fields["tipo_autorizacion"].required = False
        self.fields["docente_reemplazado"].required = False

        # Las horas de cada día son opcionales y por defecto 0
        for dia in self.DIAS_CAMPOS:
            self.fields[dia].required = False
            self.fields[dia].initial = 0

    def clean(self):
        cleaned_data = super().clean()
        for dia in self.DIAS_CAMPOS:
            if cleaned_data.get(dia) is None:
                cleaned_data[dia] = 0
        situacion = cleaned_data.get("situacion_revista")
        docente_reemplazado = cleaned_data.get("docente_reemplazado")
        fecha_alta = cleaned_data.get("fecha_alta")
        fecha_baja = cleaned_data.get("fecha_baja")

        # RF-04: Exigencia de docente reemplazado para cargos suplentes
        if situacion in ["SUPLENTE", "SUP"] and not docente_reemplazado:
            self.add_error(
                "docente_reemplazado",
                "Debe especificar el docente reemplazado para una suplencia "
                "según Formulario DP-01.",
            )

        # Validación cronológica de altas y bajas
        if fecha_alta and fecha_baja and fecha_baja < fecha_alta:
            self.add_error(
                "fecha_baja",
                "La fecha de baja no puede ser anterior a la fecha de alta "
                "de la designación.",
            )

        # Validación de horas cátedra no negativas
        dias_horas = [
            ("horas_lunes", "Lunes"),
            ("horas_martes", "Martes"),
            ("horas_miercoles", "Miércoles"),
            ("horas_jueves", "Jueves"),
            ("horas_viernes", "Viernes"),
        ]
        for field_name, label in dias_horas:
            horas = cleaned_data.get(field_name)
            if horas is not None and horas < 0:
                self.add_error(
                    field_name,
                    f"Las horas cátedra del {label} no pueden ser negativas.",
                )

        return cleaned_data
