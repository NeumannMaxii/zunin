"""
Formularios para el módulo de Licencias y Justificación Diferida.
Implementa el buscador de licencias y el flujo en papel (RF-09, RF-11, RF-15, Ticket 8).
"""

import unicodedata
from django import forms
from django.db.models import Q
from apps.asistencia.models import RegistroAsistencia
from apps.core.forms import TailwindForm
from apps.licencias.models import LicenciaOtorgada, TipoLicencia
from apps.personal.models import CargoDocente, Docente


def _variantes_token_busqueda(token):
    """
    Genera el token y variantes con/sin tildes para búsqueda predictiva (Ticket 8).
    """
    if not token:
        return []
    nfkd = unicodedata.normalize("NFKD", token)
    sin_tilde = "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
    tildes_map = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
    variantes = {token.lower(), sin_tilde}

    for i, char in enumerate(sin_tilde):
        if char in tildes_map:
            variantes.add(sin_tilde[:i] + tildes_map[char] + sin_tilde[i + 1 :])

    if "cion" in sin_tilde:
        variantes.add(sin_tilde.replace("cion", "ción"))
    if "amen" in sin_tilde:
        variantes.add(sin_tilde.replace("amen", "ámen"))
    if "menes" in sin_tilde:
        variantes.add(sin_tilde.replace("menes", "ámenes"))

    return list(variantes)


class TipoLicenciaSearchForm(TailwindForm):
    """
    Formulario de búsqueda y filtrado de licencias estatutarias (RF-15, Ticket 8).
    Soporta filtros GET por cuadro (?cuadro=IL-01 o ?cuadro=IL-02) y búsqueda (?q=).
    """

    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={"placeholder": "Buscar por código, artículo o descripción..."}
        ),
    )
    cuadro = forms.CharField(
        required=False,
        label="Cuadro",
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
    regimen = forms.ChoiceField(
        required=False,
        label="Régimen / Situación de Revista",
        choices=[("", "Todos los regímenes")] + TipoLicencia.REGIMEN_CHOICES,
    )
    activo = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos"), ("1", "Solo activos"), ("0", "Inactivos")],
    )

    def filtrar(self, queryset=None):
        """Aplica los criterios de búsqueda al queryset suministrado."""
        if queryset is None:
            queryset = TipoLicencia.objects.all()

        if not self.is_valid():
            return queryset

        q_val = self.cleaned_data.get("q", "").strip()
        cuadro_raw = self.cleaned_data.get("cuadro", "")
        cuadro_val = cuadro_raw.strip().upper() if cuadro_raw else ""
        cuadro_mensual = self.cleaned_data.get("cuadro_mensual")
        categoria = self.cleaned_data.get("categoria")
        forma_pago = self.cleaned_data.get("forma_pago")
        activo = self.cleaned_data.get("activo")
        regimen = self.cleaned_data.get("regimen")

        if q_val:
            tokens = q_val.split()
            for token in tokens:
                q_token = Q()
                for variante in _variantes_token_busqueda(token):
                    q_token |= (
                        Q(codigo__icontains=variante)
                        | Q(articulo__icontains=variante)
                        | Q(descripcion__icontains=variante)
                    )
                queryset = queryset.filter(q_token)

        # Filtro por cuadro (Ticket 8: ?cuadro=IL-01 o ?cuadro=IL-02)
        cuadro_filtro = cuadro_val or cuadro_mensual
        if cuadro_filtro:
            if cuadro_filtro in ["IL-01", "DL-01"]:
                queryset = queryset.filter(cuadro_mensual__in=["IL-01", "DL-01"])
            elif cuadro_filtro in ["IL-02", "DL-02"]:
                queryset = queryset.filter(cuadro_mensual__in=["IL-02", "DL-02"])
            else:
                queryset = queryset.filter(cuadro_mensual=cuadro_filtro)

        if categoria:
            queryset = queryset.filter(categoria=categoria)

        if forma_pago:
            queryset = queryset.filter(forma_pago=forma_pago)

        if activo == "1":
            queryset = queryset.filter(activo=True)
        elif activo == "0":
            queryset = queryset.filter(activo=False)

        if regimen:
            from apps.licencias.validaciones import (
                filtrar_tipos_licencia_por_regimen,
            )

            queryset = filtrar_tipos_licencia_por_regimen(
                queryset=queryset, situacion_revista=regimen
            )

        return queryset


class JustificacionDiferidaForm(TailwindForm):
    """
    Formulario operativo para carga de formularios en papel (RF-09, RF-11, Ticket 7).
    Permite transicionar un registro de inasistencia ('I') a 'LIC', 'P' o 'LT',
    o procesar un rango de fechas omitiendo fines de semana y feriados (RN-03).
    """

    NUEVA_MARCA_CHOICES = [
        ("LIC", "Licencia médica o especial (LIC)"),
        ("P", "Permiso reglamentario (P)"),
        ("LT", "Largo tratamiento (LT)"),
    ]

    docente = forms.ModelChoiceField(
        queryset=Docente.objects.filter(activo=True),
        required=False,
        label="Docente",
        help_text="Seleccione el docente al que corresponde la justificación.",
    )
    fecha_desde = forms.DateField(
        required=False,
        label="Fecha Desde",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Fecha de inicio del período a justificar.",
    )
    fecha_hasta = forms.DateField(
        required=False,
        label="Fecha Hasta",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Fecha de finalización del período a justificar.",
    )
    cargo = forms.ModelChoiceField(
        queryset=CargoDocente.objects.filter(activo=True),
        required=False,
        label="Cargo / Materia (Opcional)",
        help_text="Especifique si la justificación aplica a un cargo particular.",
    )
    registro = forms.ModelChoiceField(
        queryset=RegistroAsistencia.objects.all(),
        required=False,
        label="Registro de Asistencia / Inasistencia",
        help_text="Seleccione el registro puntual (para justificación individual).",
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
    TIPO_INSTRUMENTO_CHOICES = [
        ("DISPOSICION", "Disposición Interna IESETyFP"),
        ("RESOLUCION", "Resolución Ministerial M.E.C.C.y T."),
    ]

    tipo_instrumento = forms.ChoiceField(
        choices=TIPO_INSTRUMENTO_CHOICES,
        required=False,
        initial="DISPOSICION",
        label="Tipo de Instrumento Legal",
    )
    numero_disposicion = forms.CharField(
        max_length=50,
        required=False,
        label="Número de Disposición / Instrumento",
        widget=forms.TextInput(attrs={"placeholder": "Ej: Disp. Interna 042/2026"}),
    )
    numero_resolucion = forms.CharField(
        max_length=50,
        required=False,
        label="Número de Resolución Ministerial Externa",
        widget=forms.TextInput(
            attrs={"placeholder": "Ej: Res. 1450/2026 M.E.C.C.y T."}
        ),
    )
    observaciones = forms.CharField(
        required=False,
        label="Observaciones de Justificación",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Detalle de presentación de certificado médico o "
                    "formulario oficial..."
                ),
            }
        ),
    )

    def __init__(self, *args, registro=None, cargo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if registro is not None:
            self.fields["registro"].initial = registro
            self.fields["registro"].queryset = RegistroAsistencia.objects.filter(
                pk=registro.pk
            )
        cargo_target = cargo or (
            registro.cargo if registro and hasattr(registro, "cargo") else None
        )
        if cargo_target:
            from apps.licencias.validaciones import (
                filtrar_tipos_licencia_por_regimen,
            )

            self.fields["tipo_licencia"].queryset = (
                filtrar_tipos_licencia_por_regimen(cargo=cargo_target)
            )

    def clean(self):
        cleaned_data = super().clean()
        registro = cleaned_data.get("registro")
        docente = cleaned_data.get("docente")
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        nueva_marca = cleaned_data.get("nueva_marca")
        tipo_licencia = cleaned_data.get("tipo_licencia")

        if not registro and not (docente and fecha_desde and fecha_hasta):
            if not registro and not docente:
                self.add_error(
                    "docente",
                    "Debe seleccionar un docente o un registro puntual.",
                )
            if not registro and not fecha_desde:
                self.add_error(
                    "fecha_desde",
                    "Debe especificar la fecha de inicio del período.",
                )
            if not registro and not fecha_hasta:
                self.add_error(
                    "fecha_hasta",
                    "Debe especificar la fecha de fin del período.",
                )

        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            self.add_error(
                "fecha_hasta",
                "La fecha de fin no puede ser anterior a la fecha de inicio.",
            )

        if registro:
            no_ausente = (
                registro.marca_diaria not in ["I", "INA"]
                and registro.estado != "AUSENTE"
            )
            if no_ausente:
                self.add_error(
                    "registro",
                    "Solo se pueden justificar registros en estado de "
                    "inasistencia ('I').",
                )

        if nueva_marca in ["LIC", "LT"] and not tipo_licencia:
            self.add_error(
                "tipo_licencia",
                "Debe especificar un Tipo de Licencia para justificar "
                "con Licencia (LIC/LT).",
            )

        # Validación de Régimen de Revista (Ticket 17.1)
        cargo_target = cleaned_data.get("cargo")
        if not cargo_target and registro and hasattr(registro, "cargo"):
            cargo_target = registro.cargo

        if cargo_target and tipo_licencia:
            from apps.licencias.validaciones import validar_regimen_revista

            try:
                validar_regimen_revista(
                    tipo_licencia=tipo_licencia, cargo=cargo_target
                )
            except forms.ValidationError as exc:
                self.add_error("tipo_licencia", exc)

        if tipo_licencia:
            from apps.licencias.validaciones import validar_antiguedad_minima

            try:
                validar_antiguedad_minima(
                    tipo_licencia=tipo_licencia,
                    docente=docente,
                    cargo=cargo_target,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                )
            except forms.ValidationError as exc:
                self.add_error("tipo_licencia", exc)

        if cargo_target and fecha_desde and fecha_hasta:
            from apps.licencias.validaciones import validar_solapamiento_licencias

            try:
                validar_solapamiento_licencias(
                    cargo=cargo_target,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                    docente=docente,
                )
            except forms.ValidationError as exc:
                self.add_error("fecha_desde", exc)

        return cleaned_data

    def save(self, usuario=None):
        """
        Aplica la justificación delegando a la lógica individual del modelo
        o al servicio de rango con omisión de feriados y regla RN-03.
        """
        if not self.is_valid():
            raise ValueError("No se puede guardar un formulario con errores.")

        registro = self.cleaned_data.get("registro")
        nueva_marca = self.cleaned_data["nueva_marca"]
        tipo_licencia = self.cleaned_data.get("tipo_licencia")
        tipo_instrumento = self.cleaned_data.get("tipo_instrumento") or "DISPOSICION"
        numero_resolucion = self.cleaned_data.get("numero_resolucion")
        numero_disposicion = self.cleaned_data.get("numero_disposicion")
        observaciones = self.cleaned_data.get("observaciones")

        if tipo_instrumento == "RESOLUCION" and numero_resolucion:
            num_final = numero_resolucion
        else:
            num_final = numero_disposicion or numero_resolucion

        if registro:
            registro.justificar_con_formulario(
                nueva_marca=nueva_marca,
                tipo_licencia=tipo_licencia,
                usuario=usuario,
            )
            if num_final:
                registro.numero_disposicion = num_final
            if observaciones:
                if registro.observaciones:
                    registro.observaciones = (
                        f"{registro.observaciones} | {observaciones}"
                    )
                else:
                    registro.observaciones = observaciones
            registro.save()
            return registro
        else:
            docente = self.cleaned_data["docente"]
            fecha_desde = self.cleaned_data["fecha_desde"]
            fecha_hasta = self.cleaned_data["fecha_hasta"]
            cargo = self.cleaned_data.get("cargo")

            from .services import procesar_justificacion_rango

            return procesar_justificacion_rango(
                docente=docente,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                nueva_marca=nueva_marca,
                tipo_licencia=tipo_licencia,
                numero_disposicion=num_final,
                observaciones=observaciones,
                cargo=cargo,
                usuario=usuario,
                tipo_instrumento=tipo_instrumento,
            )


JustificacionDiferidaRangoForm = JustificacionDiferidaForm


class LicenciaOtorgadaForm(TailwindForm, forms.ModelForm):
    """
    Formulario oficial para registro y solicitud de licencias docentes (Ticket 16.1).
    Ticket 17.1: Filtra el catálogo de tipos de licencia según el régimen
    del cargo (TIT, INT, SUP) y bloquea en backend ante tipos incompatibles.
    """

    class Meta:
        model = LicenciaOtorgada
        fields = [
            "docente",
            "cargo",
            "tipo_licencia",
            "fecha_desde",
            "fecha_hasta_prevista",
            "estado",
            "porcentaje_goce",
            "instrumento_legal",
            "observaciones",
        ]
        widgets = {
            "fecha_desde": forms.DateInput(attrs={"type": "date"}),
            "fecha_hasta_prevista": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(
        self,
        *args,
        cargo=None,
        situacion_revista=None,
        docente=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        target_cargo = cargo or (
            self.instance.cargo if self.instance.pk else None
        )
        target_docente = docente or (
            self.instance.docente if self.instance.pk else None
        )
        target_revista = situacion_revista
        if not target_revista and target_cargo:
            target_revista = getattr(target_cargo, "situacion_revista", None)

        if target_revista:
            from apps.licencias.validaciones import (
                filtrar_tipos_licencia_por_regimen,
            )

            self.fields["tipo_licencia"].queryset = (
                filtrar_tipos_licencia_por_regimen(
                    situacion_revista=target_revista
                )
            )

        if target_docente:
            self.fields["cargo"].queryset = CargoDocente.objects.filter(
                docente=target_docente, activo=True
            )

    def clean(self):
        cleaned_data = super().clean()
        cargo = cleaned_data.get("cargo")
        tipo_licencia = cleaned_data.get("tipo_licencia")
        docente = cleaned_data.get("docente")

        if cargo and tipo_licencia:
            from apps.licencias.validaciones import validar_regimen_revista

            try:
                validar_regimen_revista(
                    tipo_licencia=tipo_licencia, cargo=cargo
                )
            except forms.ValidationError as exc:
                self.add_error("tipo_licencia", exc)

        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta_prevista")

        if tipo_licencia:
            from apps.licencias.validaciones import validar_antiguedad_minima

            try:
                validar_antiguedad_minima(
                    tipo_licencia=tipo_licencia,
                    docente=docente,
                    cargo=cargo,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                )
            except forms.ValidationError as exc:
                self.add_error("tipo_licencia", exc)

        if cargo and fecha_desde and fecha_hasta:
            from apps.licencias.validaciones import validar_solapamiento_licencias

            try:
                validar_solapamiento_licencias(
                    cargo=cargo,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                    instancia_actual=self.instance,
                    docente=docente,
                )
            except forms.ValidationError as exc:
                self.add_error("fecha_desde", exc)

        if docente and cargo and cargo.docente != docente:
            self.add_error(
                "cargo",
                f"El cargo '{cargo}' no pertenece al docente {docente}.",
            )

        return cleaned_data
