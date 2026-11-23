"""
Formularios para el módulo de Personal y Designaciones Docentes.
Maneja datos filiatorios del cuerpo docente y la asignación de cargos/horas cátedra.
"""

from datetime import date
from django import forms
from apps.core.forms import TailwindForm, TailwindModelForm
from apps.personal.models import (
    TURNO_CHOICES,
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    EspacioCurricular,
    PlanEstudio,
    TipoAutorizacion,
)


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
            "email",
            "celular",
            "contacto",
            "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "dni": forms.TextInput(attrs={"placeholder": "Ej: 28456123"}),
            "apellido": forms.TextInput(attrs={"placeholder": "Apellido del docente"}),
            "nombre": forms.TextInput(attrs={"placeholder": "Nombres del docente"}),
            "email": forms.EmailInput(
                attrs={"placeholder": "ejemplo@iesetyfp.edu.ar"}
            ),
            "celular": forms.TextInput(
                attrs={"placeholder": "Ej: 3624-123456"}
            ),
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
                "La fecha de nacimiento no puede ser posterior a la " "fecha actual."
            )
        return fecha


class DocenteBedeliaForm(DocenteForm):
    """
    Formulario para Bedelia_Operadoras donde el campo 'activo'
    está excluido y bloqueado para impedir modificaciones (Ticket 6).
    """

    class Meta(DocenteForm.Meta):
        fields = [f for f in DocenteForm.Meta.fields if f != "activo"]

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk:
            # Bloquea y preserva el estado original del campo activo
            self.instance.refresh_from_db(fields=["activo"])
        return cleaned_data


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

    espacio_curricular = forms.ModelChoiceField(
        queryset=EspacioCurricular.objects.all(),
        required=False,
        label="Espacio Curricular / Materia",
    )
    disposicion = forms.CharField(
        max_length=100,
        required=False,
        label="Disposición / Resolución",
        widget=forms.TextInput(
            attrs={"placeholder": "Ej: Disp. 145/26 o Res. 102/20"}
        ),
    )
    horas_semanales = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        label="Horas Semanales",
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 4"}),
    )
    turno = forms.ChoiceField(
        choices=[("", "-- Seleccionar Turno --")] + list(TURNO_CHOICES),
        required=False,
        label="Turno",
    )

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
            "codigo_cargo": forms.TextInput(attrs={"placeholder": "Ej: CARGO-BED-01"}),
            "numero_autorizacion": forms.TextInput(attrs={"placeholder": "Ej: 145/26"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materia"].required = False
        self.fields["tipo_cargo"].required = False
        self.fields["tipo_cargo"].initial = "HORAS_CATEDRA"
        self.fields["cargo_catalogo"].required = False
        self.fields["carrera_ref"].required = False
        self.fields["tipo_autorizacion"].required = False
        self.fields["docente_reemplazado"].required = False
        self.fields["espacio_curricular"].queryset = (
            EspacioCurricular.objects.select_related("carrera").order_by("nombre")
        )

        # Si ya existe instancia, inicializar campos de conveniencia
        if self.instance and self.instance.pk:
            if self.instance.materia:
                self.fields["espacio_curricular"].initial = self.instance.materia
                if (
                    hasattr(self.instance.materia, "turno")
                    and self.instance.materia.turno
                ):
                    self.fields["turno"].initial = self.instance.materia.turno
            if hasattr(self.instance, "disposicion") and self.instance.disposicion:
                self.fields["disposicion"].initial = self.instance.disposicion
            if hasattr(self.instance, "total_horas_semanales"):
                self.fields["horas_semanales"].initial = (
                    self.instance.total_horas_semanales
                )
            if hasattr(self.instance, "turno") and self.instance.turno:
                self.fields["turno"].initial = self.instance.turno

        # Las horas de cada día son opcionales y por defecto 0
        for dia in self.DIAS_CAMPOS:
            self.fields[dia].required = False
            if not (self.instance and self.instance.pk):
                self.fields[dia].initial = 0

        # Opciones limpias de situación de revista: palabra completa y abreviatura oficial
        self.fields["situacion_revista"].choices = [
            ("TIT", "Titular (TIT)"),
            ("INT", "Interino (INT)"),
            ("SUP", "Suplente (SUP)"),
            ("TITULAR", "Titular"),
            ("INTERINO", "Interino"),
            ("SUPLENTE", "Suplente"),
        ]
        self.fields["situacion_revista"].widget.choices = [
            ("TIT", "Titular (TIT)"),
            ("INT", "Interino (INT)"),
            ("SUP", "Suplente (SUP)"),
        ]
        if not (self.instance and self.instance.pk):
            self.fields["situacion_revista"].initial = "INT"
        elif self.instance.situacion_revista in ("INTERINO", "INT"):
            self.fields["situacion_revista"].initial = "INT"
        elif self.instance.situacion_revista in ("TITULAR", "TIT"):
            self.fields["situacion_revista"].initial = "TIT"
        elif self.instance.situacion_revista in ("SUPLENTE", "SUP"):
            self.fields["situacion_revista"].initial = "SUP"

        # Asegurar que activo tenga initial=True en nuevas designaciones
        if "activo" in self.fields and not (self.instance and self.instance.pk):
            self.fields["activo"].initial = True

    def clean(self):
        cleaned_data = super().clean()
        for dia in self.DIAS_CAMPOS:
            if cleaned_data.get(dia) is None:
                cleaned_data[dia] = 0

        # Asegurar que un nuevo cargo sea activo por defecto
        if not self.instance.pk:
            if "activo" not in self.data:
                cleaned_data["activo"] = True
            else:
                val = self.data.get("activo")
                cleaned_data["activo"] = val in ("on", "true", "True", "1", True)

        if not cleaned_data.get("tipo_cargo"):
            cleaned_data["tipo_cargo"] = "HORAS_CATEDRA"

        # Sincronizar espacio_curricular con materia
        espacio = cleaned_data.get("espacio_curricular")
        if espacio and not cleaned_data.get("materia"):
            cleaned_data["materia"] = espacio
        elif cleaned_data.get("materia") and not espacio:
            cleaned_data["espacio_curricular"] = cleaned_data["materia"]

        # Sincronizar disposicion con resolucion / numero_autorizacion
        disp = cleaned_data.get("disposicion")
        if disp:
            if not cleaned_data.get("resolucion"):
                cleaned_data["resolucion"] = disp
            if not cleaned_data.get("numero_autorizacion"):
                cleaned_data["numero_autorizacion"] = disp
        elif cleaned_data.get("resolucion"):
            cleaned_data["disposicion"] = cleaned_data["resolucion"]

        # Sincronizar horas_semanales con horas_lunes si los días están en 0
        hs = cleaned_data.get("horas_semanales")
        total_dias = sum(cleaned_data.get(d, 0) for d in self.DIAS_CAMPOS)
        if hs and hs > 0 and total_dias == 0:
            cleaned_data["horas_lunes"] = hs

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

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk and (
            "activo" not in self.data or self.data.get("activo")
        ):
            instance.activo = True
        if self.cleaned_data.get("espacio_curricular"):
            instance.materia = self.cleaned_data["espacio_curricular"]
        if self.cleaned_data.get("disposicion"):
            instance.resolucion = self.cleaned_data["disposicion"]
            instance.numero_autorizacion = self.cleaned_data["disposicion"]
        if self.cleaned_data.get("turno"):
            instance.turno = self.cleaned_data["turno"]
        hs = self.cleaned_data.get("horas_semanales")
        if hs and hs > 0 and instance.total_horas_semanales == 0:
            instance.horas_lunes = hs
        if instance.fecha_alta and (
            not instance.desde_texto or instance.desde_texto == "SIN INICIO"
        ):
            instance.desde_texto = instance.fecha_alta.strftime("%d/%m/%Y")
        if not instance.fecha_alta:
            from django.utils import timezone
            instance.fecha_alta = timezone.localdate()
            if not instance.desde_texto or instance.desde_texto == "SIN INICIO":
                instance.desde_texto = instance.fecha_alta.strftime("%d/%m/%Y")
        if commit:
            instance.save()
        return instance


class ImportarCSVForm(TailwindForm):
    """
    Formulario para la carga masiva e importación de Docentes y Cargos vía CSV.
    """

    archivo = forms.FileField(
        label="Archivo CSV de Personal y Cargos",
        help_text=(
            "Seleccione un archivo con formato .csv (delimitador ';' o coma, "
            "codificación UTF-8)."
        ),
        widget=forms.FileInput(
            attrs={
                "accept": ".csv,text/csv",
                "class": (
                    "block w-full text-sm text-slate-500 file:mr-4 file:py-2.5 "
                    "file:px-4 file:rounded-lg file:border-0 file:text-sm "
                    "file:font-semibold file:bg-institucional-50 "
                    "file:text-institucional-700 hover:file:bg-institucional-100 "
                    "cursor-pointer border border-slate-300 rounded-lg p-2 "
                    "focus:outline-none"
                ),
            }
        ),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if not archivo:
            raise forms.ValidationError("Debe seleccionar un archivo para importar.")
        if not archivo.name.lower().endswith(".csv"):
            raise forms.ValidationError(
                "El archivo seleccionado debe tener extensión .csv."
            )
        return archivo


class CarreraForm(TailwindModelForm):
    """
    Formulario para el alta y edición de Carreras (Ticket 10.1).
    Requiere obligatoriamente definir el Plan de Estudio Inicial al crear una carrera.
    """

    plan_inicial_nombre = forms.CharField(
        required=True,
        label="Plan de Estudio Inicial",
        help_text=(
            "Ej: Plan 2026. Toda carrera debe contar con su plan de estudio."
        ),
        widget=forms.TextInput(attrs={"placeholder": "Ej: Plan 2026"}),
    )
    plan_inicial_resolucion = forms.CharField(
        required=True,
        label="Resolución Ministerial",
        help_text="Ej: Res. MECCyT N° 1245/26. Norma legal ministerial aprobatoria.",
        widget=forms.TextInput(
            attrs={"placeholder": "Ej: Res. MECCyT N° 1245/26"}
        ),
    )
    plan_inicial_anio = forms.IntegerField(
        required=True,
        label="Año de Implementación",
        help_text="Año calendario en que entra en vigencia el plan (Ej: 2026).",
        widget=forms.NumberInput(
            attrs={"placeholder": "Ej: 2026", "min": 1990, "max": 2100}
        ),
    )

    class Meta:
        model = Carrera
        fields = ["codigo", "nombre", "activo"]
        widgets = {
            "codigo": forms.TextInput(attrs={"placeholder": "Ej: TEC-DS"}),
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ej: Tecnicatura Superior en Desarrollo de Software"
                    )
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields.pop("plan_inicial_nombre", None)
            self.fields.pop("plan_inicial_resolucion", None)
            self.fields.pop("plan_inicial_anio", None)

    def save(self, commit=True):
        carrera = super().save(commit=commit)
        plan_nombre = self.cleaned_data.get("plan_inicial_nombre", "").strip()
        if plan_nombre and commit and carrera.pk:
            from apps.personal.models import PlanEstudio

            resolucion = self.cleaned_data.get(
                "plan_inicial_resolucion", ""
            ).strip()
            anio = self.cleaned_data.get("plan_inicial_anio")
            PlanEstudio.objects.get_or_create(
                carrera=carrera,
                nombre=plan_nombre,
                defaults={
                    "resolucion": resolucion,
                    "anio_implementacion": anio,
                    "activo": True,
                },
            )
        return carrera

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").strip().upper()
        if not codigo:
            raise forms.ValidationError("El código es obligatorio.")
        qs = Carrera.objects.filter(codigo__iexact=codigo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe una carrera registrada con este código."
            )
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        if not nombre:
            raise forms.ValidationError("El nombre de la carrera es obligatorio.")
        return nombre


class CargoCatalogoForm(TailwindModelForm):
    """
    Formulario para el alta y edición del catálogo de cargos (Ticket 10.1).
    """

    class Meta:
        model = CargoCatalogo
        fields = ["codigo", "descripcion", "activo"]
        widgets = {
            "codigo": forms.TextInput(attrs={"placeholder": "Ej: MEP"}),
            "descripcion": forms.TextInput(
                attrs={"placeholder": ("Ej: Maestro de Enseñanza Práctica")}
            ),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").strip().upper()
        if not codigo:
            raise forms.ValidationError("El código de cargo es obligatorio.")
        qs = CargoCatalogo.objects.filter(codigo__iexact=codigo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe un cargo registrado con este código."
            )
        return codigo

    def clean_descripcion(self):
        descripcion = self.cleaned_data.get("descripcion", "").strip()
        if not descripcion:
            raise forms.ValidationError("La descripción es obligatoria.")
        return descripcion


class TipoAutorizacionForm(TailwindModelForm):
    """
    Formulario para el catálogo de tipos de autorización (Ticket 10.1).
    """

    class Meta:
        model = TipoAutorizacion
        fields = ["nombre", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: RESOLUCIÓN"}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip().upper()
        if not nombre:
            raise forms.ValidationError(
                "El nombre del tipo de autorización es obligatorio."
            )
        qs = TipoAutorizacion.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe un tipo de autorización con este nombre."
            )
        return nombre


class PlanEstudioForm(TailwindModelForm):
    """
    Formulario para el catálogo de Planes de Estudio institucionales (Ticket 19.1).
    """

    class Meta:
        model = PlanEstudio
        fields = [
            "carrera",
            "nombre",
            "resolucion",
            "anio_implementacion",
            "activo",
            "descripcion",
        ]
        widgets = {
            "nombre": forms.TextInput(
                attrs={"placeholder": "Ej: Plan 2022 o Res. 542/19"}
            ),
            "resolucion": forms.TextInput(
                attrs={"placeholder": "Ej: Res. 542/19 - MECCyT"}
            ),
            "anio_implementacion": forms.NumberInput(
                attrs={"placeholder": "Ej: 2022", "min": 1990, "max": 2100}
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Observaciones sobre el plan, incumbencias o transición"
                    ),
                }
            ),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        if not nombre:
            raise forms.ValidationError(
                "El nombre o código del plan de estudio es obligatorio."
            )
        return nombre

    def clean(self):
        cleaned_data = super().clean()
        carrera = cleaned_data.get("carrera")
        nombre = cleaned_data.get("nombre")
        if carrera and nombre:
            qs = PlanEstudio.objects.filter(
                carrera=carrera, nombre__iexact=nombre
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "nombre",
                    (
                        f"Ya existe un plan con el nombre '{nombre}' "
                        f"para la carrera '{carrera.nombre}'."
                    ),
                )
        return cleaned_data


class EspacioCurricularForm(TailwindModelForm):
    """
    Formulario para el catálogo de espacios curriculares / materias.
    Soporta la asociación formal a Carrera y Plan de Estudio (Ticket 19.1).
    """

    plan_estudio_ref = forms.ModelChoiceField(
        queryset=PlanEstudio.objects.none(),
        required=True,
        empty_label="-- Seleccionar Plan de Estudio --",
        label="Plan de Estudio",
        help_text=(
            "Plan curricular ministerial al que pertenece la asignatura (requerido)"
        ),
    )
    anio = forms.TypedChoiceField(
        choices=[
            ("", "-- Seleccionar Año de Cursada --"),
            (1, "1° Año"),
            (2, "2° Año"),
            (3, "3° Año"),
            (4, "4° Año"),
            (5, "5° Año"),
        ],
        coerce=int,
        required=True,
        label="Año de Cursada",
        help_text="Año correspondiente dentro de la carrera (1° a 5°)",
    )

    class Meta:
        model = EspacioCurricular
        fields = [
            "codigo",
            "nombre",
            "carrera",
            "plan_estudio_ref",
            "anio",
            "comision",
            "turno",
            "regimen",
            "aula",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"placeholder": "Ej: DS-101"}),
            "nombre": forms.TextInput(
                attrs={"placeholder": "Ej: Programación I"}
            ),
            "comision": forms.TextInput(attrs={"placeholder": "Ej: 1° A"}),
            "aula": forms.TextInput(
                attrs={"placeholder": "Ej: Laboratorio 1"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comision"].required = False
        self.fields["comision"].initial = "UNICA"
        self.fields["regimen"].initial = "ANUAL"
        self.fields["turno"].initial = "MANANA"
        self.fields["aula"].required = False

        carrera_id = None
        if "carrera" in self.data:
            try:
                carrera_id = int(self.data.get("carrera"))
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.carrera_id:
            carrera_id = self.instance.carrera_id
        elif self.initial.get("carrera"):
            initial_carrera = self.initial.get("carrera")
            carrera_id = getattr(initial_carrera, "pk", initial_carrera)

        if carrera_id:
            self.fields["plan_estudio_ref"].queryset = PlanEstudio.objects.filter(
                carrera_id=carrera_id, activo=True
            ).order_by("-anio_implementacion", "nombre")
        else:
            self.fields["plan_estudio_ref"].queryset = PlanEstudio.objects.filter(
                activo=True
            ).order_by("carrera__codigo", "nombre")

        # Si se está editando una materia existente, fijar y bloquear Carrera y Plan
        if self.instance and self.instance.pk:
            self.fields["carrera"].disabled = True
            self.fields["carrera"].help_text = (
                "Carrera a la que pertenece la asignatura (asignación fija)."
            )
            self.fields["plan_estudio_ref"].disabled = True
            self.fields["plan_estudio_ref"].help_text = (
                "Plan curricular ministerial al que pertenece la asignatura (fijo)."
            )
        elif self.initial.get("plan_estudio_ref") and self.initial.get("carrera"):
            self.fields["carrera"].disabled = True
            self.fields["carrera"].help_text = (
                "Carrera preseleccionada desde el plan (fijo)."
            )
            self.fields["plan_estudio_ref"].disabled = True
            self.fields["plan_estudio_ref"].help_text = (
                "Plan curricular ministerial preseleccionado (fijo)."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.plan_estudio_ref:
            instance.plan_estudio = instance.plan_estudio_ref.nombre
        elif not instance.plan_estudio:
            instance.plan_estudio = ""
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        carrera = cleaned_data.get("carrera")
        plan_ref = cleaned_data.get("plan_estudio_ref")
        if plan_ref and carrera:
            if plan_ref.carrera_id != carrera.id:
                self.add_error(
                    "plan_estudio_ref",
                    (
                        f"El plan de estudio '{plan_ref.nombre}' no pertenece "
                        f"a la carrera '{carrera.nombre}'."
                    ),
                )
        return cleaned_data

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").strip().upper()
        if not codigo:
            raise forms.ValidationError(
                "El código del espacio curricular es obligatorio."
            )
        qs = EspacioCurricular.objects.filter(codigo__iexact=codigo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe un espacio curricular registrado con este código."
            )
        return codigo

    def clean_comision(self):
        comision = self.cleaned_data.get("comision", "").strip()
        return comision or "UNICA"

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        if not nombre:
            raise forms.ValidationError(
                "El nombre de la materia es obligatorio."
            )
        return nombre
