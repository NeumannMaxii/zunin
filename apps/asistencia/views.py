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
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)
from apps.asistencia.forms import (
    ConsultaAsistenciaForm,
    DiaNoLaborableForm,
    RegistroAsistenciaUpdateForm,
)
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import (
    justificar_lote_asistencias,
    rectificar_planillas_por_fechas,
)
from apps.core.audit import AuditoriaFormMixin, audit_save
from apps.core.mixins import PermisosEstrictosMixin
from apps.licencias.models import RenglonPlanillaMensual, TipoLicencia
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
            .select_related(
                "docente",
                "cargo__materia",
                "cargo__cargo_catalogo",
                "tipo_licencia",
            )
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


class RegistroAsistenciaUpdateView(BackendPermisoMixin, UpdateView):
    """
    Edición individual de un RegistroAsistencia (Presente <-> Ausente <->
    Licencia <-> Justificado) para corregir errores de carga sobre un único
    cargo y fecha, rectificando planillas mensuales preexistentes (RN-03).
    """

    raise_exception = True
    model = RegistroAsistencia
    form_class = RegistroAsistenciaUpdateForm
    template_name = "asistencia/registroasistencia_form.html"
    context_object_name = "registro"

    def test_func(self):
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

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "docente",
                "cargo__materia",
                "cargo__cargo_catalogo",
                "tipo_licencia",
            )
        )

    def _get_next_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return reverse("asistencia:asistencia_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar Registro de Asistencia"
        context["accion"] = "Guardar Cambios"
        context["next_url"] = self._get_next_url()
        context["planilla_existente"] = (
            RenglonPlanillaMensual.objects.filter(
                mes=self.object.fecha.month,
                anio=self.object.fecha.year,
            ).exists()
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            obj = form.save(commit=False)
            self.object = audit_save(obj, user=self.request.user, created=False)
            rectificados = rectificar_planillas_por_fechas(
                [self.object.fecha],
                usuario=self.request.user,
            )

        msg = (
            f"Registro de {self.object.docente} del "
            f"{self.object.fecha.strftime('%d/%m/%Y')} actualizado a "
            f"{self.object.get_estado_display()} ({self.object.marca_diaria})."
        )
        if rectificados:
            periodos_txt = ", ".join(f"{m:02d}/{a}" for m, a in rectificados)
            msg += (
                f" Planilla mensual {periodos_txt} rectificada "
                "automáticamente (RN-03)."
            )
        messages.success(self.request, msg)
        return redirect(self._get_next_url())


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
        rectificados = []
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
                    elif estado in ["PRESENTE", "LICENCIA", "JUSTIFICADO"]:
                        reg.justifica = True

                    if (
                        not created
                        and estado == "PRESENTE"
                        and reg.numero_disposicion
                    ):
                        reg.numero_disposicion = ""

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
                            "numero_disposicion",
                            "observaciones",
                            "justifica",
                            "modificado_por",
                            "actualizado_en",
                        ],
                    )
                if nuevos or existentes:
                    rectificados = rectificar_planillas_por_fechas(
                        [fecha],
                        usuario=audit_user,
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
            if rectificados:
                periodos_txt = ", ".join(f"{m:02d}/{a}" for m, a in rectificados)
                messages.info(
                    request,
                    f"Planilla mensual {periodos_txt} rectificada automáticamente "
                    "para reflejar los cambios (RN-03).",
                )
            return redirect("asistencia:asistencia_list")

        except (ValidationError, IntegrityError) as exc:
            messages.error(
                request,
                f"Error al registrar la asistencia diaria: {exc}. "
                "Se revirtieron los cambios atómicamente.",
            )
            return redirect(
                f"{reverse('asistencia:asistencia_diaria')}"
                f"?fecha={fecha.isoformat()}"
            )


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

    def _get_inasistencias_pendientes(self):
        return (
            RegistroAsistencia.objects.filter(
                Q(marca_diaria__in=["I", "INA"])
                | Q(estado="AUSENTE", justifica=False)
            )
            .select_related(
                "docente",
                "cargo__materia",
                "cargo__cargo_catalogo",
                "tipo_licencia",
            )
            .order_by("-fecha", "docente__apellido")
        )

    def _get_tipos_licencia(self):
        return TipoLicencia.objects.filter(activo=True).order_by("codigo")

    def _build_context(
        self,
        *,
        selected_ids=None,
        selected_nueva_marca="P",
        selected_tipo_licencia="",
        error=False,
    ):
        inasistencias_pendientes = self._get_inasistencias_pendientes()
        return {
            "titulo": "Justificaciones por Lote",
            "inasistencias": inasistencias_pendientes,
            "tipos_licencia": self._get_tipos_licencia(),
            "total_pendientes": inasistencias_pendientes.count(),
            "selected_ids": selected_ids or [],
            "selected_nueva_marca": selected_nueva_marca,
            "selected_tipo_licencia": selected_tipo_licencia,
            "error": error,
        }

    def get(self, request):
        return render(
            request,
            "asistencia/justificaciones_lote.html",
            self._build_context(),
        )

    def post(self, request):
        lote_items = request.POST.getlist("items", [])
        if not lote_items:
            messages.warning(request, "No se recibieron registros para justificar.")
            return redirect("asistencia:justificaciones_lote")

        nueva_marca = (request.POST.get("nueva_marca") or "P").strip().upper()
        tipo_licencia_id = (request.POST.get("tipo_licencia") or "").strip()
        tipo_licencia = None
        if tipo_licencia_id:
            if tipo_licencia_id.isdigit():
                tipo_licencia = TipoLicencia.objects.filter(
                    pk=int(tipo_licencia_id)
                ).first()
            if tipo_licencia is None:
                tipo_licencia = tipo_licencia_id

        items_lote = []
        selected_ids = []
        for it in lote_items:
            if isinstance(it, str) and it.strip().isdigit():
                item_id = int(it.strip())
                selected_ids.append(str(item_id))
                items_lote.append({
                    "asistencia": item_id,
                    "nueva_marca": nueva_marca,
                    "tipo_licencia": tipo_licencia,
                })
            elif isinstance(it, str):
                try:
                    parsed = json.loads(it)
                    if isinstance(parsed, dict):
                        parsed.setdefault("nueva_marca", nueva_marca)
                        if not parsed.get("tipo_licencia") and tipo_licencia:
                            parsed["tipo_licencia"] = tipo_licencia
                        parsed_id = (
                            parsed.get("asistencia")
                            or parsed.get("registro")
                            or parsed.get("id")
                        )
                        if parsed_id is not None:
                            selected_ids.append(str(parsed_id))
                    items_lote.append(parsed)
                except Exception:
                    items_lote.append(it)
            else:
                items_lote.append(it)

        try:
            justificados = justificar_lote_asistencias(
                items_lote, usuario=request.user, request=request
            )
            messages.success(
                request,
                f"Lote de justificaciones procesado exitosamente "
                f"({len(justificados)} registro/s actualizado/s).",
            )
            return redirect("asistencia:asistencia_list")
        except (ValidationError, IntegrityError, Exception):
            return render(
                request,
                "asistencia/justificaciones_lote.html",
                self._build_context(
                    selected_ids=selected_ids,
                    selected_nueva_marca=nueva_marca,
                    selected_tipo_licencia=tipo_licencia_id,
                    error=True,
                ),
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
