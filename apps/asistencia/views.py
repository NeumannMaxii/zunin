"""
Vistas para la aplicación Asistencia.
Listados paginados, ABM de Feriados (Ticket 4), carga diaria / masiva (Ticket 5)
y justificaciones por lote (Ticket 7).
"""

import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)
from apps.asistencia.forms import ConsultaAsistenciaForm, DiaNoLaborableForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import justificar_lote_asistencias
from apps.core.audit import AuditoriaFormMixin
from apps.core.mixins import PermisosEstrictosMixin
from apps.licencias.models import TipoLicencia
from apps.personal.models import CargoDocente, Docente


class BackendPermisoMixin(PermisosEstrictosMixin):
    """
    Mixin base para blindaje de permisos backend (Ticket 10.6 y Ticket 11).
    Redirige usuarios anónimos al login (302) y rechaza con 403 Forbidden estricto
    a usuarios autenticados que no posean el rol o privilegios requeridos.
    """


class RegistroAsistenciaListView(LoginRequiredMixin, ListView):
    """
    Listado paginado y consulta avanzada multicriterio de registros de asistencia.
    Configuración obligatoria de paginate_by = 25 (Ticket 3.8 y Ticket 12.6).
    """

    model = RegistroAsistencia
    template_name = "asistencia/asistencia_list.html"
    context_object_name = "asistencias"
    paginate_by = 25
    ordering = ["-fecha", "docente__apellido"]

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("docente", "cargo__materia", "tipo_licencia")
        )
        self.form = ConsultaAsistenciaForm(self.request.GET or None)
        if self.form.is_valid():
            queryset = self.form.filtrar(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = getattr(self, "form", None)
        if form is None:
            form = ConsultaAsistenciaForm(self.request.GET or None)
        context["form"] = form
        from apps.personal.models import EspacioCurricular

        context["materias"] = EspacioCurricular.objects.all().order_by("nombre")
        return context


class ConsultaAsistenciaView(RegistroAsistenciaListView):
    """
    Vista de consulta avanzada multicriterio para auditar registros de asistencia
    (Ticket 12.6).
    Hereda de RegistroAsistenciaListView manteniendo filtros combinables y paginación.
    """

    pass


class AsistenciaDiariaView(BackendPermisoMixin, View):
    """
    Pantalla 3: Asistencia Diaria y Carga de Novedades (RF-10, Ticket 5).
    Permite registrar y actualizar la asistencia diaria por Materia/Cargo
    mediante audit_save(), gestionando la advertencia visual de feriados
    sin bloquear la carga operativa.
    Blindaje de permisos backend (Ticket 10.6): Restringe peticiones POST a roles
    operativos (Admin_Institucional o Bedelia_Operadoras).
    """

    raise_exception = True

    def test_func(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["Admin_Institucional", "Bedelia_Operadoras"]
            ).exists()
            or user.has_perm("asistencia.add_registroasistencia")
        )

    def get_fecha(self, request):
        fecha_str = request.GET.get("fecha") or request.POST.get("fecha")
        if fecha_str:
            parsed = parse_date(str(fecha_str).strip())
            if parsed:
                return parsed
        return timezone.localdate()

    def get(self, request):
        fecha = self.get_fecha(request)
        feriado = DiaNoLaborable.objects.filter(fecha=fecha).first()

        # Consultar los cargos vigentes del día ordenados por docente y materia
        cargos_vigentes = (
            CargoDocente.objects.vigentes(fecha=fecha)
            .select_related("docente", "espacio_curricular__carrera")
            .order_by("docente__apellido", "espacio_curricular__nombre")
        )

        # Construir el diccionario de registros existentes indexando por cargo_id
        registros_map = {
            r.cargo_id: r
            for r in RegistroAsistencia.objects.filter(
                fecha=fecha, cargo__in=cargos_vigentes
            ).select_related("tipo_licencia", "cargo", "docente")
        }

        # Armar la lista grilla: cada elemento contiene
        # {'cargo': cargo, 'docente': cargo.docente, 'registro': reg}
        grilla = []
        for cargo in cargos_vigentes:
            reg = registros_map.get(cargo.id)
            grilla.append({
                "cargo": cargo,
                "docente": cargo.docente,
                "registro": reg,
            })

        # Asegurar que docentes activos sin cargo tengan un cargo base
        # (retrocompatibilidad)
        docentes_sin_cargo = list(
            Docente.objects.activos().filter(cargos__isnull=True)
        )
        if docentes_sin_cargo:
            CargoDocente.objects.bulk_create([
                CargoDocente(docente=d, situacion_revista="TIT", activo=True)
                for d in docentes_sin_cargo
            ])
            cargos_vigentes = (
                CargoDocente.objects.vigentes(fecha=fecha)
                .select_related("docente", "espacio_curricular__carrera")
                .order_by("docente__apellido", "espacio_curricular__nombre")
            )
            grilla = []
            for cargo in cargos_vigentes:
                reg = registros_map.get(cargo.id)
                grilla.append({
                    "cargo": cargo,
                    "docente": cargo.docente,
                    "registro": reg,
                })

        tipos_licencia = TipoLicencia.objects.filter(activo=True).order_by("codigo")
        docentes = Docente.objects.activos()

        # Agrupar cargos por docente único para evitar duplicaciones en la interfaz
        docentes_map = {}
        for cargo in cargos_vigentes:
            d_id = cargo.docente_id
            if d_id not in docentes_map:
                docentes_map[d_id] = {
                    "docente": cargo.docente,
                    "cargos": [],
                }
            reg = registros_map.get(cargo.id)
            docentes_map[d_id]["cargos"].append({
                "cargo": cargo,
                "registro": reg,
            })

        docentes_grilla = list(docentes_map.values())

        context = {
            "titulo": "Asistencia Diaria",
            "fecha": fecha,
            "feriado": feriado,
            "es_feriado": feriado is not None,
            "grilla": grilla,
            "docentes_grilla": docentes_grilla,
            "total_docentes": len(docentes_grilla),
            "cargos": cargos_vigentes,
            "docentes": docentes,
            "tipos_licencia": tipos_licencia,
        }
        return render(request, "asistencia/carga_masiva.html", context)

    def post(self, request):
        fecha = self.get_fecha(request)
        feriado = DiaNoLaborable.objects.filter(fecha=fecha).first()
        es_feriado = feriado is not None

        # 1. Identificar si se enviaron docente_ids explícitos o IDs de estado_
        docente_ids_post = [
            int(i) for i in request.POST.getlist("docente_ids") if str(i).isdigit()
        ]
        raw_ids = [
            int(key.split("_")[1])
            for key in request.POST.keys()
            if key.startswith("estado_") and key.split("_")[1].isdigit()
        ]

        if not raw_ids and not docente_ids_post:
            lote_items = request.POST.getlist("items", [])
            for item in lote_items:
                if isinstance(item, str):
                    try:
                        parsed = json.loads(item)
                        if isinstance(parsed, dict):
                            cid = parsed.get("cargo_id") or parsed.get("docente_id")
                            if cid:
                                raw_ids.append(int(cid))
                    except Exception:
                        pass
                elif isinstance(item, dict):
                    cid = item.get("cargo_id") or item.get("docente_id")
                    if cid:
                        raw_ids.append(int(cid))

        if not raw_ids and not docente_ids_post:
            messages.warning(
                request, "No se recibieron registros para la carga diaria."
            )
            return redirect("asistencia:asistencia_list")

        cargos_a_procesar = []
        if docente_ids_post:
            doc_cargos = (
                CargoDocente.objects.filter(
                    docente_id__in=docente_ids_post, activo=True
                ).select_related("docente")
            )
            doc_cargo_dict = {}
            for c in doc_cargos:
                if c.docente_id not in doc_cargo_dict:
                    doc_cargo_dict[c.docente_id] = c
            missing_d_ids = [
                d_id for d_id in docente_ids_post if d_id not in doc_cargo_dict
            ]
            if missing_d_ids:
                missing_docentes = Docente.objects.filter(
                    id__in=missing_d_ids
                ).in_bulk()
                new_cargos = [
                    CargoDocente(
                        docente=missing_docentes[d_id],
                        situacion_revista="TIT",
                        activo=True,
                    )
                    for d_id in missing_d_ids
                    if d_id in missing_docentes
                ]
                if new_cargos:
                    CargoDocente.objects.bulk_create(new_cargos)
                    for c in CargoDocente.objects.filter(
                        docente_id__in=missing_d_ids, activo=True
                    ).select_related("docente"):
                        if c.docente_id not in doc_cargo_dict:
                            doc_cargo_dict[c.docente_id] = c
            for d_id in docente_ids_post:
                if d_id in doc_cargo_dict:
                    cargos_a_procesar.append(doc_cargo_dict[d_id])
        else:
            cargos_by_id = (
                CargoDocente.objects.filter(id__in=raw_ids)
                .select_related("docente")
                .in_bulk()
            )
            cargos_a_procesar = list(cargos_by_id.values())
            missing_ids = set(raw_ids) - set(cargos_by_id.keys())
            if missing_ids:
                doc_cargos = (
                    CargoDocente.objects.filter(docente_id__in=missing_ids, activo=True)
                    .select_related("docente")
                )
                doc_cargo_dict = {}
                for c in doc_cargos:
                    if c.docente_id not in doc_cargo_dict:
                        doc_cargo_dict[c.docente_id] = c
                for d_id in missing_ids:
                    if d_id in doc_cargo_dict:
                        cargos_a_procesar.append(doc_cargo_dict[d_id])
                    else:
                        d_obj = Docente.objects.filter(id=d_id).first()
                        if d_obj:
                            nc = CargoDocente.objects.create(
                                docente=d_obj, situacion_revista="TIT", activo=True
                            )
                            cargos_a_procesar.append(nc)

        if not cargos_a_procesar:
            messages.warning(
                request, "No se encontraron cargos válidos para procesar."
            )
            return redirect("asistencia:asistencia_list")

        cargo_ids_set = {c.id for c in cargos_a_procesar}

        # Diccionario de registros existentes indexando por cargo_id
        registros_existentes_map = {
            r.cargo_id: r
            for r in RegistroAsistencia.objects.filter(
                cargo_id__in=cargo_ids_set, fecha=fecha
            )
        }

        # Precargar tipos de licencia
        lic_ids = set()
        for cargo in cargos_a_procesar:
            lic_val = (
                request.POST.get(f"licencia_{cargo.id}")
                or request.POST.get(f"licencia_{cargo.docente_id}")
                or request.POST.get(f"tipo_licencia_{cargo.id}")
                or request.POST.get(f"tipo_licencia_{cargo.docente_id}")
            )
            if lic_val:
                try:
                    lic_ids.add(int(lic_val))
                except (ValueError, TypeError):
                    pass
        licencias_map = TipoLicencia.objects.in_bulk(lic_ids) if lic_ids else {}

        nuevos = []
        existentes = []
        audit_user = (
            request.user
            if (
                request.user is not None
                and getattr(request.user, "is_authenticated", True)
            )
            else None
        )
        audit_user_id = audit_user.pk if audit_user else None
        ahora = timezone.now()

        try:
            with transaction.atomic():
                for cargo in cargos_a_procesar:
                    estado = (
                        request.POST.get(f"estado_{cargo.id}")
                        or request.POST.get(f"estado_{cargo.docente_id}")
                        or request.POST.get("estado", "PRESENTE")
                    )
                    lic_val = (
                        request.POST.get(f"licencia_{cargo.id}")
                        or request.POST.get(f"licencia_{cargo.docente_id}")
                        or request.POST.get(f"tipo_licencia_{cargo.id}")
                        or request.POST.get(f"tipo_licencia_{cargo.docente_id}")
                    )
                    marca = (
                        request.POST.get(f"marca_diaria_{cargo.id}")
                        or request.POST.get(f"marca_diaria_{cargo.docente_id}")
                    )
                    observaciones = (
                        request.POST.get(f"observaciones_{cargo.id}")
                        or request.POST.get(f"observaciones_{cargo.docente_id}")
                        or ""
                    )
                    justifica_val = (
                        request.POST.get(f"justifica_{cargo.id}")
                        or request.POST.get(f"justifica_{cargo.docente_id}")
                    )

                    if not marca:
                        if estado == "PRESENTE":
                            marca = "PR"
                        elif estado == "AUSENTE":
                            marca = "I"
                        elif estado == "LICENCIA":
                            marca = "LIC"
                        else:
                            marca = "P"

                    reg = registros_existentes_map.get(cargo.id)
                    created = reg is None
                    if created:
                        reg = RegistroAsistencia(
                            docente=cargo.docente, cargo=cargo, fecha=fecha
                        )

                    reg.docente = cargo.docente
                    reg.cargo = cargo
                    reg.fecha = fecha
                    reg.estado = estado
                    reg.marca_diaria = marca

                    if lic_val and estado == "LICENCIA":
                        try:
                            reg.tipo_licencia = licencias_map.get(int(lic_val))
                        except (ValueError, TypeError):
                            reg.tipo_licencia = None
                    else:
                        reg.tipo_licencia = None

                    reg.observaciones = observaciones

                    if (
                        justifica_val is not None
                        and str(justifica_val).lower() in ["false", "0", "no"]
                    ):
                        reg.justifica = False
                    elif estado == "AUSENTE":
                        reg.justifica = False
                    elif estado in ["PRESENTE", "JUSTIFICADO"]:
                        reg.justifica = True

                    if created:
                        if not reg.creado_por_id:
                            reg.creado_por_id = audit_user_id
                        reg.modificado_por_id = audit_user_id
                        reg.actualizado_en = ahora
                        reg.clean()
                        nuevos.append(reg)
                    else:
                        reg.modificado_por_id = audit_user_id
                        reg.actualizado_en = ahora
                        reg.clean()
                        existentes.append(reg)

                if nuevos:
                    RegistroAsistencia.objects.bulk_create(nuevos)
                if existentes:
                    RegistroAsistencia.objects.bulk_update(
                        existentes,
                        fields=[
                            "docente",
                            "cargo",
                            "estado",
                            "marca_diaria",
                            "tipo_licencia",
                            "observaciones",
                            "justifica",
                            "modificado_por",
                            "actualizado_en",
                        ],
                    )

            if es_feriado:
                messages.warning(
                    request,
                    f"Asistencia del feriado ({feriado.descripcion}) "
                    "registrada correctamente por cargo. El motor mensual omitirá esta "
                    "fecha en la liquidación de horas.",
                )
            else:
                messages.success(
                    request,
                    f"Asistencia diaria de {len(cargos_a_procesar)} cargo(s) "
                    f"del día {fecha.strftime('%d/%m/%Y')} registrada exitosamente.",
                )
            return redirect("asistencia:asistencia_list")

        except (ValidationError, IntegrityError) as exc:
            messages.error(
                request,
                f"Error al registrar la asistencia diaria: {exc}. "
                "Se revirtieron los cambios atómicamente.",
            )
            return redirect("asistencia:asistencia_diaria")


class JustificacionesLoteView(BackendPermisoMixin, View):
    """
    Vista para Justificaciones por Lote de Inasistencias (Ticket 7 y 3.8).
    Blindaje de permisos backend (Ticket 10.6): Restringe peticiones POST a roles
    operativos (Admin_Institucional o Bedelia_Operadoras).
    """

    raise_exception = True

    def test_func(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["Admin_Institucional", "Bedelia_Operadoras"]
            ).exists()
            or user.has_perm("asistencia.change_registroasistencia")
        )

    def get(self, request):
        inasistencias_pendientes = (
            RegistroAsistencia.objects.filter(
                Q(marca_diaria__in=["I", "INA"])
                | Q(estado="AUSENTE", justifica=False)
            )
            .select_related("docente", "cargo__espacio_curricular", "tipo_licencia")
            .order_by("-fecha", "docente__apellido")
        )
        tipos_licencia = TipoLicencia.objects.filter(activo=True).order_by("codigo")
        return render(
            request,
            "asistencia/justificaciones_lote.html",
            {
                "titulo": "Justificaciones por Lote",
                "inasistencias": inasistencias_pendientes,
                "tipos_licencia": tipos_licencia,
                "total_pendientes": inasistencias_pendientes.count(),
            },
        )

    def post(self, request):
        lote_items = request.POST.getlist("items", [])
        if not lote_items:
            messages.warning(request, "No se recibieron registros para justificar.")
            return redirect("asistencia:asistencia_list")

        nueva_marca = request.POST.get("nueva_marca", "P")
        tipo_licencia_id = request.POST.get("tipo_licencia")
        tipo_licencia = (
            TipoLicencia.objects.filter(pk=tipo_licencia_id).first()
            if tipo_licencia_id
            else None
        )

        items_lote = []
        for it in lote_items:
            if isinstance(it, str) and it.isdigit():
                items_lote.append({
                    "asistencia": int(it),
                    "nueva_marca": nueva_marca,
                    "tipo_licencia": tipo_licencia,
                })
            elif isinstance(it, str):
                try:
                    parsed = json.loads(it)
                    items_lote.append(parsed)
                except Exception:
                    items_lote.append(it)
            else:
                items_lote.append(it)

        try:
            justificar_lote_asistencias(
                items_lote, usuario=request.user, request=request
            )
            messages.success(request, "Lote de justificaciones procesado exitosamente.")
            return redirect("asistencia:asistencia_list")
        except (ValidationError, IntegrityError, Exception):
            inasistencias_pendientes = (
                RegistroAsistencia.objects.filter(
                    Q(marca_diaria__in=["I", "INA"])
                    | Q(estado="AUSENTE", justifica=False)
                )
                .select_related("docente", "cargo__espacio_curricular", "tipo_licencia")
                .order_by("-fecha", "docente__apellido")
            )
            tipos_licencia = TipoLicencia.objects.filter(activo=True).order_by("codigo")
            return render(
                request,
                "asistencia/justificaciones_lote.html",
                {
                    "titulo": "Justificaciones por Lote",
                    "inasistencias": inasistencias_pendientes,
                    "tipos_licencia": tipos_licencia,
                    "total_pendientes": inasistencias_pendientes.count(),
                    "error": True,
                },
                status=400,
            )


class DiaNoLaborableListView(LoginRequiredMixin, ListView):
    """
    Listado paginado de feriados, asuetos y días no laborables (Ticket 4).
    Paginación obligatoria de 25 registros por página (Ticket 3.8).
    """

    model = DiaNoLaborable
    template_name = "asistencia/dianolaborable_list.html"
    context_object_name = "feriados"
    paginate_by = 25
    ordering = ["-fecha"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Gestión de Feriados y Días No Laborables"
        return context


class DiaNoLaborableCreateView(BackendPermisoMixin, AuditoriaFormMixin, CreateView):
    """
    Alta de nuevo feriado o día no laborable con auditoría (Ticket 4).
    Blindaje de permisos backend (Ticket 10.6): Exige rol operativo.
    """

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
            or user.has_perm("asistencia.add_dianolaborable")
        )

    model = DiaNoLaborable
    form_class = DiaNoLaborableForm
    template_name = "asistencia/dianolaborable_form.html"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Registrar Nuevo Día No Laborable"
        context["accion"] = "Crear"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Día no laborable registrado con éxito.")
        return super().form_valid(form)


class DiaNoLaborableUpdateView(BackendPermisoMixin, AuditoriaFormMixin, UpdateView):
    """
    Edición de feriado o día no laborable existente con auditoría (Ticket 4).
    Blindaje de permisos backend (Ticket 10.6): Exige rol operativo.
    """

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
            or user.has_perm("asistencia.change_dianolaborable")
        )

    model = DiaNoLaborable
    form_class = DiaNoLaborableForm
    template_name = "asistencia/dianolaborable_form.html"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar Día No Laborable"
        context["accion"] = "Guardar Cambios"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Día no laborable modificado con éxito.")
        return super().form_valid(form)


class DiaNoLaborableDeleteView(BackendPermisoMixin, DeleteView):
    """
    Eliminación de un día no laborable / feriado del calendario (Ticket 4).
    Blindaje de permisos backend (Ticket 10.6): Exclusivo para Admin_Institucional.
    Bedelía y roles de consulta reciben HTTP 403 Forbidden.
    """

    raise_exception = True

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return (
            user.is_superuser or user.groups.filter(name="Admin_Institucional").exists()
        )

    model = DiaNoLaborable
    template_name = "asistencia/dianolaborable_confirm_delete.html"
    context_object_name = "feriado"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Eliminar Día No Laborable"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Día no laborable eliminado correctamente.")
        return super().form_valid(form)
