"""
Vistas para la aplicación Personal (Docentes y Cargos).
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25)
y Ticket 6: Pantalla 1 — CRUD Personal y endpoint de baja lógica con seguridad.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.views.generic.edit import FormView
from apps.core.audit import AuditoriaFormMixin, audit_save
from apps.personal.forms import (
    CargoCatalogoForm,
    CarreraForm,
    DocenteBedeliaForm,
    DocenteForm,
    ImportarCSVForm,
    TipoAutorizacionForm,
)
from apps.personal.importer import importar_legajos_csv
from apps.personal.models import (
    CargoCatalogo,
    CargoDocente,
    Carrera,
    Docente,
    TipoAutorizacion,
)


class DocenteListView(LoginRequiredMixin, ListView):
    """
    Vista de listado de personal docente.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = Docente
    template_name = "personal/docente_list.html"
    context_object_name = "docentes"
    paginate_by = 25
    ordering = ["apellido", "nombre"]


class DocenteCreateView(
    LoginRequiredMixin, UserPassesTestMixin, AuditoriaFormMixin, CreateView
):
    """
    Vista para el alta de un nuevo legajo docente (Ticket 6).
    Accesible para Administradores y Bedelía Operadora.
    """

    model = Docente
    template_name = "personal/docente_form.html"
    success_url = reverse_lazy("personal:docente_list")
    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["Admin_Institucional", "Bedelia_Operadoras"]
            ).exists()
            or user.has_perm("personal.add_docente")
        )

    def es_bedelia_operadora(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.groups.filter(name="Bedelia_Operadoras").exists()
            and not (
                user.is_superuser
                or user.groups.filter(name="Admin_Institucional").exists()
            )
        )

    def get_form_class(self):
        if self.es_bedelia_operadora():
            return DocenteBedeliaForm
        return DocenteForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.es_bedelia_operadora() and "activo" in form.fields:
            del form.fields["activo"]
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Registrar Nuevo Personal Docente"
        context["accion"] = "Registrar Docente"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Docente {self.object.apellido}, {self.object.nombre} "
            "registrado con éxito.",
        )
        return response


class DocenteUpdateView(
    LoginRequiredMixin, UserPassesTestMixin, AuditoriaFormMixin, UpdateView
):
    """
    Vista de edición para actualizar datos filiatorios y legajo (Ticket 6).
    Si el usuario pertenece al grupo Bedelia_Operadoras, el campo 'activo'
    se oculta del formulario y se bloquea para evitar modificaciones no autorizadas.
    """

    model = Docente
    template_name = "personal/docente_form.html"
    success_url = reverse_lazy("personal:docente_list")
    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["Admin_Institucional", "Bedelia_Operadoras"]
            ).exists()
            or user.has_perm("personal.change_docente")
        )

    def es_bedelia_operadora(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.groups.filter(name="Bedelia_Operadoras").exists()
            and not (
                user.is_superuser
                or user.groups.filter(name="Admin_Institucional").exists()
            )
        )

    def get_form_class(self):
        if self.es_bedelia_operadora():
            return DocenteBedeliaForm
        return DocenteForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.es_bedelia_operadora() and "activo" in form.fields:
            del form.fields["activo"]
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = (
            f"Editar Personal: {self.object.apellido}, {self.object.nombre}"
        )
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Docente {self.object.apellido}, {self.object.nombre} "
            "actualizado con éxito.",
        )
        return response


class DocenteBajaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Endpoint de baja lógica para Docentes (Ticket 6).
    Ruta protegida: POST /personal/<pk>/baja/.
    Permisos estrictos: Solo superusuarios o miembros de Admin_Institucional.
    Si accede Bedelia_Operadoras o Consulta_Directiva, retorna HTTP 403 Forbidden.
    Acción: Cambia el estado del Docente a activo = False y persiste.
    """

    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Admin_Institucional").exists()
        )

    def get(self, request, pk, *args, **kwargs):
        docente = get_object_or_404(Docente, pk=pk)
        return render(
            request,
            "personal/docente_confirm_baja.html",
            {
                "docente": docente,
                "titulo": f"Confirmar Baja: {docente.apellido}, {docente.nombre}",
            },
        )

    def post(self, request, pk, *args, **kwargs):
        docente = get_object_or_404(Docente, pk=pk)
        docente.activo = False
        audit_save(docente, user=request.user, created=False)
        messages.success(
            request,
            f"El docente {docente.apellido}, {docente.nombre} fue dado "
            "de baja exitosamente.",
        )
        return redirect("personal:docente_list")


class CargoDocenteListView(LoginRequiredMixin, ListView):
    """
    Vista de listado de cargos y designaciones docentes.
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = CargoDocente
    template_name = "personal/cargodocente_list.html"
    context_object_name = "cargos"
    paginate_by = 25
    ordering = ["docente__apellido", "docente__nombre"]


class ImportarCSVView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """
    Vista para importar docentes y cargos desde un archivo CSV.
    Acceso restringido exclusivamente a Superusuarios o usuarios
    del grupo Admin_Institucional (HTTP 403 Forbidden para otros roles).
    """

    template_name = "personal/importar_csv.html"
    form_class = ImportarCSVForm
    success_url = reverse_lazy("personal:docente_list")
    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Admin_Institucional").exists()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Importar Docentes y Cargos desde CSV"
        return context

    def form_valid(self, form):
        archivo = form.cleaned_data["archivo"]
        try:
            resumen = importar_legajos_csv(
                archivo,
                usuario=self.request.user,
                encoding="utf-8-sig",
            )
            doc_c = resumen.get("docentes_creados", 0)
            doc_a = resumen.get("docentes_actualizados", 0)
            carg_c = resumen.get("cargos_creados", 0)
            carg_a = resumen.get("cargos_actualizados", 0)
            errores = resumen.get("errores", [])

            msg = (
                f"Importación CSV procesada con éxito: "
                f"{doc_c} docente(s) creado(s), {doc_a} actualizado(s); "
                f"{carg_c} cargo(s) creado(s), {carg_a} actualizado(s)."
            )
            messages.success(self.request, msg)

            if errores:
                for err in errores[:5]:
                    messages.warning(self.request, err)

            return super().form_valid(form)
        except Exception as exc:
            messages.error(
                self.request, f"Error durante la importación: {exc}"
            )
            return self.form_invalid(form)


# ==============================================================================
# Mixin de Autorización Exclusiva para Administrador Institucional (Ticket 10.1)
# ==============================================================================


class SoloAdminInstitucionalMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin para restringir el acceso exclusivamente a Superusuarios y
    miembros del grupo Admin_Institucional (Ticket 10.1).
    Los usuarios no autenticados son redirigidos a la pantalla de login (302).
    Los usuarios autenticados sin el rol adecuado reciben HTTP 403 Forbidden.
    """

    raise_exception = False

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Admin_Institucional").exists()
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied(self.get_permission_denied_message())


class CatalogosHubView(SoloAdminInstitucionalMixin, TemplateView):
    """
    Panel central de gestión de catálogos institucionales base (Ticket 10.1).
    Permite acceder a los catálogos de Carrera, CargoCatalogo y TipoAutorizacion.
    """

    template_name = "personal/catalogos/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogos Institucionales"
        context["total_carreras"] = Carrera.objects.count()
        context["carreras_activas"] = Carrera.objects.filter(
            activo=True
        ).count()
        context["total_cargos"] = CargoCatalogo.objects.count()
        context["cargos_activos"] = CargoCatalogo.objects.filter(
            activo=True
        ).count()
        context["total_autorizaciones"] = TipoAutorizacion.objects.count()
        context["autorizaciones_activas"] = TipoAutorizacion.objects.filter(
            activo=True
        ).count()
        return context


# ==============================================================================
# Catálogo de Carreras (Ticket 10.1)
# ==============================================================================


class CarreraListView(SoloAdminInstitucionalMixin, ListView):
    """
    Vista de listado para el catálogo de Carreras formativas (Ticket 10.1).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = Carrera
    template_name = "personal/catalogos/carrera_list.html"
    context_object_name = "carreras"
    paginate_by = 25
    ordering = ["codigo"]

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(codigo__icontains=q) | Q(nombre__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogo de Carreras"
        context["q"] = self.request.GET.get("q", "").strip()
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["carreras"].count()
        )
        return context


class CarreraCreateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, CreateView
):
    """
    Vista para dar de alta una nueva Carrera formativa (Ticket 10.1).
    """

    model = Carrera
    form_class = CarreraForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:carrera_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nueva Carrera"
        context["catalogo_nombre"] = "Carrera"
        context["list_url"] = reverse_lazy("personal:carrera_list")
        context["accion"] = "Registrar Carrera"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Carrera '{self.object.codigo} - {self.object.nombre}' "
            "registrada con éxito.",
        )
        return response


class CarreraUpdateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, UpdateView
):
    """
    Vista para actualizar una Carrera formativa existente (Ticket 10.1).
    """

    model = Carrera
    form_class = CarreraForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:carrera_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Editar Carrera: {self.object.codigo}"
        context["catalogo_nombre"] = "Carrera"
        context["list_url"] = reverse_lazy("personal:carrera_list")
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Carrera '{self.object.codigo} - {self.object.nombre}' "
            "actualizada con éxito.",
        )
        return response


# ==============================================================================
# Catálogo de Cargos (Ticket 10.1)
# ==============================================================================


class CargoCatalogoListView(SoloAdminInstitucionalMixin, ListView):
    """
    Vista de listado para el catálogo de Cargos institucionales (Ticket 10.1).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = CargoCatalogo
    template_name = "personal/catalogos/cargocatalogo_list.html"
    context_object_name = "cargos_catalogo"
    paginate_by = 25
    ordering = ["codigo"]

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(codigo__icontains=q) | Q(descripcion__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogo de Cargos"
        context["q"] = self.request.GET.get("q", "").strip()
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["cargos_catalogo"].count()
        )
        return context


class CargoCatalogoCreateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, CreateView
):
    """
    Vista para dar de alta un nuevo Cargo de Catálogo (Ticket 10.1).
    """

    model = CargoCatalogo
    form_class = CargoCatalogoForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:cargocatalogo_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nuevo Cargo de Catálogo"
        context["catalogo_nombre"] = "Cargo de Catálogo"
        context["list_url"] = reverse_lazy("personal:cargocatalogo_list")
        context["accion"] = "Registrar Cargo"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Cargo de catálogo '{self.object.codigo} - "
            f"{self.object.descripcion}' registrado con éxito.",
        )
        return response


class CargoCatalogoUpdateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, UpdateView
):
    """
    Vista para actualizar un Cargo de Catálogo existente (Ticket 10.1).
    """

    model = CargoCatalogo
    form_class = CargoCatalogoForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:cargocatalogo_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = (
            f"Editar Cargo de Catálogo: {self.object.codigo}"
        )
        context["catalogo_nombre"] = "Cargo de Catálogo"
        context["list_url"] = reverse_lazy("personal:cargocatalogo_list")
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Cargo de catálogo '{self.object.codigo} - "
            f"{self.object.descripcion}' actualizado con éxito.",
        )
        return response


# ==============================================================================
# Catálogo de Tipos de Autorización (Ticket 10.1)
# ==============================================================================


class TipoAutorizacionListView(SoloAdminInstitucionalMixin, ListView):
    """
    Vista de listado para Tipos de Autorización (Ticket 10.1).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = TipoAutorizacion
    template_name = "personal/catalogos/tipoautorizacion_list.html"
    context_object_name = "tipos_autorizacion"
    paginate_by = 25
    ordering = ["nombre"]

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(nombre__icontains=q)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogo de Tipos de Autorización"
        context["q"] = self.request.GET.get("q", "").strip()
        context["total_encontrados"] = (
            context["paginator"].count
            if "paginator" in context
            else context["tipos_autorizacion"].count()
        )
        return context


class TipoAutorizacionCreateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, CreateView
):
    """
    Vista para dar de alta un nuevo Tipo de Autorización (Ticket 10.1).
    """

    model = TipoAutorizacion
    form_class = TipoAutorizacionForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:tipoautorizacion_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nuevo Tipo de Autorización"
        context["catalogo_nombre"] = "Tipo de Autorización"
        context["list_url"] = reverse_lazy(
            "personal:tipoautorizacion_list"
        )
        context["accion"] = "Registrar Tipo de Autorización"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Tipo de autorización '{self.object.nombre}' "
            "registrado con éxito.",
        )
        return response


class TipoAutorizacionUpdateView(
    SoloAdminInstitucionalMixin, AuditoriaFormMixin, UpdateView
):
    """
    Vista para actualizar un Tipo de Autorización existente (Ticket 10.1).
    """

    model = TipoAutorizacion
    form_class = TipoAutorizacionForm
    template_name = "personal/catalogos/catalogo_form.html"
    success_url = reverse_lazy("personal:tipoautorizacion_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = (
            f"Editar Tipo de Autorización: {self.object.nombre}"
        )
        context["catalogo_nombre"] = "Tipo de Autorización"
        context["list_url"] = reverse_lazy(
            "personal:tipoautorizacion_list"
        )
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Tipo de autorización '{self.object.nombre}' "
            "actualizado con éxito.",
        )
        return response
