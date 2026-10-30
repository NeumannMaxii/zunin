"""
Formularios para el módulo de Licencias y Justificación Diferida de Inasistencias.
Implementa el buscador de licencias estatutarias y el flujo de justificación en papel (RF-09, RF-11).
"""

from django import forms
from django.db.models import Q
from apps.asistencia.models import RegistroAsistencia
from apps.core.forms import TailwindForm
from apps.licencias.models import TipoLicencia


class TipoLicenciaSearchForm(TailwindForm):
    """
    Formulario de búsqueda y filtrado de tipos de licencias estatutarias (RF-15).
    """

    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={"placeholder": "Buscar por código, artículo o descripción..."}
        ),
    )
    categoria = forms.ChoiceField(
        required=False,
        label="Categoría",
        choices=[("", "Todas las categorías")] + TipoLicencia.CATEGORIA_CHOICES,
    )
    forma_pago = forms.ChoiceField(
        required=False,
        label="Forma de Pago",
        choices=[("", "Todas las formas de pago")] + TipoLicencia.FORMA_PAGO_CHOICES,
    )
    cuadro_mensual = forms.ChoiceField(
        required=False,
        label="Cuadro Mensual",
        choices=[("", "Todos los cuadros")] + TipoLicencia.CUADRO_CHOICES,
    )
    activo = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos"), ("1", "Solo activos"), ("0", "Inactivos")],
    )

    def filtrar(self, queryset=None):
        """Aplica los criterios de búsqueda al queryset suministrado o a TipoLicencia.objects.all()."""
        if queryset is None:
            queryset = TipoLicencia.objects.all()

        if not self.is_valid():
            return queryset

        q_val = self.cleaned_data.get("q", "").strip()
        categoria = self.cleaned_data.get("categoria")
        forma_pago = self.cleaned_data.get("forma_pago")
        cuadro_mensual = self.cleaned_data.get("cuadro_mensual")
        activo = self.cleaned_data.get("activo")

        if q_val:
            queryset = queryset.filter(
                Q(codigo__icontains=q_val)
                | Q(articulo__icontains=q_val)
                | Q(descripcion__icontains=q_val)
            )

        if categoria:
            queryset = queryset.filter(categoria=categoria)

        if forma_pago:
            queryset = queryset.filter(forma_pago=forma_pago)

        if cuadro_mensual:
            queryset = queryset.filter(cuadro_mensual=cuadro_mensual)

        if activo == "1":
            queryset = queryset.filter(activo=True)
        elif activo == "0":
            queryset = queryset.filter(activo=False)

        return queryset


class JustificacionDiferidaForm(TailwindForm):
    """
    Formulario operativo para la recepción y carga de formularios oficiales en papel (RF-09, RF-11).
    Permite transicionar un registro de inasistencia ('I') a 'LIC', 'P' o 'LT'.
    """

    NUEVA_MARCA_CHOICES = [
        ("LIC", "Licencia médica o especial (LIC)"),
        ("P", "Permiso reglamentario (P)"),
        ("LT", "Largo tratamiento (LT)"),
    ]

    registro = forms.ModelChoiceField(
        queryset=RegistroAsistencia.objects.all(),
        label="Registro de Asistencia / Inasistencia",
        help_text="Seleccione el registro de inasistencia pendiente de justificación.",
    )
    nueva_marca = forms.ChoiceField(
        choices=NUEVA_MARCA_CHOICES,
        label="Nueva Marca Oficial",
        help_text="Marca final tras verificar el formulario oficial.",
    )
    tipo_licencia = forms.ModelChoiceField(
        queryset=TipoLicencia.objects.filter(activo=True),
        required=False,
        label="Tipo de Licencia Estatutaria",
        help_text="Requerido si se justifica con Licencia médica o especial.",
    )
    numero_disposicion = forms.CharField(
        max_length=50,
        required=False,
        label="Número de Disposición / Instrumento",
        widget=forms.TextInput(attrs={"placeholder": "Ej: Disp. Interna 042/2026"}),
    )
    observaciones = forms.CharField(
        required=False,
        label="Observaciones de Justificación",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Detalle de presentación de certificado médico o formulario oficial...",
            }
        ),
    )

    def __init__(self, *args, registro=None, **kwargs):
        super().__init__(*args, **kwargs)
        if registro is not None:
            self.fields["registro"].initial = registro
            self.fields["registro"].queryset = RegistroAsistencia.objects.filter(pk=registro.pk)

    def clean(self):
        cleaned_data = super().clean()
        registro = cleaned_data.get("registro")
        nueva_marca = cleaned_data.get("nueva_marca")
        tipo_licencia = cleaned_data.get("tipo_licencia")

        if registro:
            if registro.marca_diaria not in ["I", "INA"] and registro.estado != "AUSENTE":
                self.add_error(
                    "registro",
                    "Solo se pueden justificar registros en estado de inasistencia ('I').",
                )

        if nueva_marca in ["LIC", "LT"] and not tipo_licencia:
            self.add_error(
                "tipo_licencia",
                "Debe especificar un Tipo de Licencia para justificar con Licencia (LIC/LT).",
            )

        return cleaned_data

    def save(self, usuario=None):
        """Aplica la justificación delegando a la lógica del modelo subyacente y guarda los metadatos."""
        if not self.is_valid():
            raise ValueError("No se puede guardar un formulario con errores.")

        registro = self.cleaned_data["registro"]
        nueva_marca = self.cleaned_data["nueva_marca"]
        tipo_licencia = self.cleaned_data.get("tipo_licencia")
        numero_disposicion = self.cleaned_data.get("numero_disposicion")
        observaciones = self.cleaned_data.get("observaciones")

        # Delegar transición de estado
        registro.justificar_con_formulario(
            nueva_marca=nueva_marca,
            tipo_licencia=tipo_licencia,
            usuario=usuario,
        )

        if numero_disposicion:
            registro.numero_disposicion = numero_disposicion

        if observaciones:
            if registro.observaciones:
                registro.observaciones = f"{registro.observaciones} | {observaciones}"
            else:
                registro.observaciones = observaciones

        registro.save()
        return registro
