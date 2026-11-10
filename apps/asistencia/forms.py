"""
Formularios para el módulo de Asistencia (Días No Laborables, Registro de Novedades
y Consulta Avanzada Multicriterio).
Aplica diseño Tailwind CSS y validaciones con delegación a las reglas de modelo.
"""

from django import forms
from django.db.models import Q
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import filtrar_asistencias_multicriterio
from apps.core.forms import TailwindForm, TailwindModelForm
from apps.licencias.models import TipoLicencia
from apps.licencias.services import determinar_marca_licencia
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
            raise forms.ValidationError(
                "La descripción del día no laborable no puede estar vacía."
            )
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
                    "placeholder": (
                        "Observaciones, motivo o justificación de la novedad..."
                    ),
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
        docente = cleaned_data.get("docente")
        if docente and not cleaned_data.get("cargo"):
            from apps.personal.models import CargoDocente
            first_cargo = (
                docente.cargos.filter(activo=True).first()
                or docente.cargos.first()
            )
            if not first_cargo:
                first_cargo = CargoDocente.objects.create(
                    docente=docente, situacion_revista="TIT", activo=True
                )
            cleaned_data["cargo"] = first_cargo
            if hasattr(self, "_errors") and "cargo" in self._errors:
                del self._errors["cargo"]
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
                    "La fecha de finalización no puede ser anterior a "
                    "la fecha inicial.",
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

        # Validación de unicidad docente + cargo + fecha
        cargo = cleaned_data.get("cargo")
        if docente and fecha and cargo:
            qs = RegistroAsistencia.objects.filter(
                docente=docente, cargo=cargo, fecha=fecha
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "fecha",
                    f"Ya existe un registro de asistencia para el docente "
                    f"{docente} en la fecha {fecha}.",
                )

        return cleaned_data


class RegistroAsistenciaUpdateForm(TailwindModelForm):
    """
    Formulario operativo para rectificar un registro individual de asistencia
    sin afectar otros cargos ni otras fechas, manteniendo coherencia entre
    estado, marca diaria, tipo de licencia y justificación.
    """

    class Meta:
        model = RegistroAsistencia
        fields = [
            "estado",
            "marca_diaria",
            "tipo_licencia",
            "numero_disposicion",
            "observaciones",
        ]
        widgets = {
            "observaciones": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Motivo de rectificación, certificado o detalle..."
                    ),
                }
            ),
            "numero_disposicion": forms.TextInput(
                attrs={"placeholder": "Ej: Disp. 024/2026 o Res. 1450/2026"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca_diaria"].required = False
        self.fields["tipo_licencia"].required = False
        self.fields["numero_disposicion"].required = False
        self.fields["observaciones"].required = False

        choices_map = dict(RegistroAsistencia.MARCA_DIARIA_CHOICES)
        orden_marcas = ["PR", "I", "LIC", "LT", "P", "LIC.", "INA", "PERM"]
        self.fields["marca_diaria"].choices = [
            (cod, choices_map[cod]) for cod in orden_marcas if cod in choices_map
        ]

        qs_tipos = TipoLicencia.objects.filter(activo=True)
        if self.instance and getattr(self.instance, "tipo_licencia_id", None):
            qs_tipos = TipoLicencia.objects.filter(
                Q(activo=True) | Q(pk=self.instance.tipo_licencia_id)
            )
        self.fields["tipo_licencia"].queryset = qs_tipos.order_by(
            "cuadro_mensual", "codigo"
        )
        self.fields["tipo_licencia"].empty_label = "-- Sin licencia --"

    def clean(self):
        cleaned_data = super().clean()
        estado = cleaned_data.get("estado")
        marca = cleaned_data.get("marca_diaria")
        tipo_licencia = cleaned_data.get("tipo_licencia")

        prev_disp = (
            (self.instance.numero_disposicion or "").strip()
            if self.instance and self.instance.pk
            else ""
        )
        new_disp = (cleaned_data.get("numero_disposicion") or "").strip()

        if estado == "PRESENTE":
            cleaned_data["marca_diaria"] = "PR"
            cleaned_data["tipo_licencia"] = None
            if (
                self.instance
                and self.instance.estado != "PRESENTE"
                and new_disp == prev_disp
            ):
                cleaned_data["numero_disposicion"] = ""
        elif estado == "AUSENTE":
            if marca not in ("I", "INA"):
                cleaned_data["marca_diaria"] = "I"
            cleaned_data["tipo_licencia"] = None
            if (
                self.instance
                and self.instance.estado == "LICENCIA"
                and new_disp == prev_disp
            ):
                cleaned_data["numero_disposicion"] = ""
        elif estado == "LICENCIA":
            if marca not in ("LIC", "LIC.", "LT"):
                cleaned_data["marca_diaria"] = determinar_marca_licencia(
                    tipo_licencia
                )
        elif estado == "JUSTIFICADO":
            if marca not in ("P", "PERM"):
                cleaned_data["marca_diaria"] = "P"

        return cleaned_data

    def _post_clean(self):
        estado = self.cleaned_data.get("estado")
        if estado:
            self.instance.justifica = estado != "AUSENTE"
            if (
                estado == "AUSENTE"
                and self.instance.fecha_hasta
                and self.instance.fecha_hasta != self.instance.fecha
            ):
                self.instance.fecha_hasta = None
        super()._post_clean()


class ConsultaAsistenciaForm(TailwindForm):
    """
    Formulario de consulta avanzada multicriterio para auditar registros
    de asistencia cruzando diferentes variables (Ticket 12.6).
    Filtros combinables:
    - fecha_desde, fecha_hasta: Rango de fechas inclusivo.
    - dni_o_apellido, dni, apellido: DNI o apellido del docente.
    - estado, marca, marca_diaria: Estado o marca diaria de asistencia.
    - materia, materia_id: Espacio curricular / Asignatura del cargo.
    """

    fecha_desde = forms.DateField(
        required=False,
        label="Fecha Desde",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label="Fecha Hasta",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    dni_o_apellido = forms.CharField(
        required=False,
        label="DNI o Apellido",
        widget=forms.TextInput(attrs={"placeholder": "Buscar por DNI o Apellido..."}),
    )
    dni = forms.CharField(
        required=False,
        label="DNI",
        widget=forms.TextInput(attrs={"placeholder": "DNI..."}),
    )
    apellido = forms.CharField(
        required=False,
        label="Apellido",
        widget=forms.TextInput(attrs={"placeholder": "Apellido..."}),
    )
    estado = forms.ChoiceField(
        choices=[("", "Todos los estados")] + list(RegistroAsistencia.ESTADO_CHOICES),
        required=False,
        label="Estado",
    )
    marca = forms.ChoiceField(
        choices=[("", "Todas las marcas")]
        + list(RegistroAsistencia.MARCA_DIARIA_CHOICES),
        required=False,
        label="Marca Diaria",
    )
    marca_diaria = forms.CharField(required=False)
    estado_marca = forms.CharField(required=False)
    materia = forms.CharField(
        required=False,
        label="Materia / Espacio Curricular",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Nombre o código de materia...",
                "list": "materias-list",
            }
        ),
    )
    materia_id = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            self.add_error(
                "fecha_hasta",
                "La fecha de finalización no puede ser anterior a la inicial.",
            )
        return cleaned_data

    def filtrar(self, queryset=None):
        """
        Aplica los filtros sobre el queryset provisto o sobre todos los registros.
        """
        if queryset is None:
            queryset = RegistroAsistencia.objects.all()

        if not self.is_valid():
            return queryset

        materia_val = (
            self.data.get("materia")
            if hasattr(self.data.get("materia"), "pk")
            else self.cleaned_data.get("materia")
        )

        return filtrar_asistencias_multicriterio(
            queryset=queryset,
            fecha_desde=self.cleaned_data.get("fecha_desde"),
            fecha_hasta=self.cleaned_data.get("fecha_hasta"),
            dni_o_apellido=(
                self.cleaned_data.get("dni_o_apellido")
                or self.data.get("docente")
                or self.data.get("q")
            ),
            dni=self.cleaned_data.get("dni"),
            apellido=self.cleaned_data.get("apellido"),
            estado=self.cleaned_data.get("estado"),
            marca=self.cleaned_data.get("marca"),
            marca_diaria=(
                self.cleaned_data.get("marca_diaria") or self.data.get("marca_diaria")
            ),
            estado_marca=(
                self.cleaned_data.get("estado_marca")
                or self.data.get("estado_marca")
                or self.data.get("estado_o_marca")
            ),
            materia=materia_val,
            materia_id=(
                self.cleaned_data.get("materia_id") or self.data.get("materia_id")
            ),
        )


# Aliases semánticos y de compatibilidad
AsistenciaConsultaForm = ConsultaAsistenciaForm
ConsultaAvanzadaAsistenciaForm = ConsultaAsistenciaForm
BusquedaAsistenciaForm = ConsultaAsistenciaForm
FiltroAsistenciaForm = ConsultaAsistenciaForm
