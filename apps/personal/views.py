"""
Vistas para la aplicación Personal (Docentes y Cargos).
Implementa Ticket 3.8: Paginación obligatoria (paginate_by = 25)
y Ticket 6: Pantalla 1 — CRUD Personal y endpoint de baja lógica con seguridad.
"""

import datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.edit import FormView
from apps.core.audit import AuditoriaFormMixin, audit_save
from apps.personal.forms import (
    DocenteBedeliaForm,
    DocenteForm,
    ImportarCSVForm,
)
from apps.personal.importer import importar_legajos_csv
from apps.personal.models import CargoDocente, Docente


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


class CargoDocenteBajaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Endpoint de baja lógica / cese de designación puntual (Ticket 10.2).
    Ruta protegida: POST /personal/cargos/<pk>/baja/.
    Permisos estrictos: Exclusivo para Superusuarios y miembros de Admin_Institucional.
    Si accede Bedelia_Operadoras o Consulta_Directiva, retorna HTTP 403 Forbidden.
    Acción: Actualiza fecha_baja = date.today() y activo = False únicamente en ese
    CargoDocente, manteniendo inalterado el legajo del Docente vinculado.
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
        cargo = get_object_or_404(
            CargoDocente.objects.select_related(
                "docente", "materia", "cargo_catalogo"
            ),
            pk=pk,
        )
        return render(
            request,
            "personal/cargodocente_confirm_baja.html",
            {
                "cargo": cargo,
                "titulo": f"Confirmar Cese de Cargo: {cargo}",
            },
        )

    def post(self, request, pk, *args, **kwargs):
        cargo = get_object_or_404(
            CargoDocente.objects.select_related(
                "docente", "materia", "cargo_catalogo"
            ),
            pk=pk,
        )
        cargo.fecha_baja = datetime.date.today()
        cargo.activo = False
        audit_save(cargo, user=request.user, created=False)
        messages.success(
            request,
            f"El cese de la designación '{cargo}' fue procesado exitosamente. "
            f"El legajo de {cargo.docente.nombre_completo} permanece activo.",
        )
        next_url = (
            request.POST.get("next")
            or reverse_lazy("personal:cargodocente_list")
        )
        return redirect(next_url)


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
