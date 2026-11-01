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
from apps.asistencia.forms import DiaNoLaborableForm
from apps.asistencia.models import DiaNoLaborable, RegistroAsistencia
from apps.asistencia.services import justificar_lote_asistencias
from apps.core.audit import AuditoriaFormMixin
from apps.licencias.models import TipoLicencia
from apps.personal.models import CargoDocente, Docente


class RegistroAsistenciaListView(LoginRequiredMixin, ListView):
    """
    Listado paginado de registros de asistencia.
    Configuración obligatoria de paginate_by = 25 (Ticket 3.8).
    """

    model = RegistroAsistencia
    template_name = "asistencia/asistencia_list.html"
    context_object_name = "asistencias"
    paginate_by = 25
    ordering = ["-fecha", "docente__apellido"]


class AsistenciaDiariaView(LoginRequiredMixin, View):
    """
    Pantalla 3: Asistencia Diaria y Carga de Novedades (RF-10, Ticket 5 y 3.8).
    Permite registrar y actualizar la asistencia diaria docente mediante audit_save(),
    gestionando la advertencia visual de feriados sin bloquear la carga operativa.
    """

    def get_fecha(self, request):
        fecha_str = request.GET.get("fecha") or request.POST.get("fecha")
        if fecha_str:
            parsed = parse_date(str(fecha_str).strip())
            if parsed:
                return parsed
        return timezone.localdate()

    def get_docentes_activos_vigentes(self, fecha):
        """
        Filtra docentes que estén activos y vigentes para la fecha especificada.
        Un docente inactivo (activo=False) nunca aparece en la grilla.
        Si el docente tiene cargos asignados, debe tener al menos un cargo
        cuya designación se encuentre vigente a la fecha de referencia.
        """
        docentes_qs = (
            Docente.objects.filter(activo=True)
            .prefetch_related("cargos__materia", "cargos__cargo_catalogo")
            .order_by("apellido", "nombre")
        )

        vigentes = []
        for doc in docentes_qs:
            cargos = list(doc.cargos.all())
            if not cargos:
                vigentes.append(doc)
            elif any(c.es_designacion_vigente(fecha) for c in cargos):
                vigentes.append(doc)

        return vigentes

    def get(self, request):
        fecha = self.get_fecha(request)
        feriado = DiaNoLaborable.objects.filter(fecha=fecha).first()
        docentes = self.get_docentes_activos_vigentes(fecha)

        registros_map = {
            r.docente_id: r
            for r in RegistroAsistencia.objects.filter(
                fecha=fecha, docente__in=docentes
            ).select_related("tipo_licencia", "cargo")
        }

        for doc in docentes:
            doc.registro_actual = registros_map.get(doc.id)

        tipos_licencia = TipoLicencia.objects.filter(activo=True).order_by(
            "codigo"
        )

        context = {
            "titulo": "Asistencia Diaria",
            "fecha": fecha,
            "feriado": feriado,
            "es_feriado": feriado is not None,
            "docentes": docentes,
            "tipos_licencia": tipos_licencia,
        }
        return render(request, "asistencia/carga_masiva.html", context)

    def post(self, request):
        fecha = self.get_fecha(request)
        feriado = DiaNoLaborable.objects.filter(fecha=fecha).first()
        es_feriado = feriado is not None

        # 1. Extracción polimórfica de ítems a procesar
        lote_items = request.POST.getlist("items", [])
        registros_data = []

        if lote_items:
            for item in lote_items:
                if isinstance(item, str):
                    try:
                        parsed = json.loads(item)
                        if isinstance(parsed, dict):
                            registros_data.append(parsed)
                    except Exception:
                        pass
                elif isinstance(item, dict):
                    registros_data.append(item)
                elif isinstance(item, RegistroAsistencia):
                    registros_data.append(item)

        if not registros_data:
            docente_ids = request.POST.getlist("docente_ids")
            if not docente_ids:
                for k in request.POST.keys():
                    if k.startswith("estado_"):
                        d_id = k.split("estado_")[1]
                        if d_id.isdigit():
                            docente_ids.append(d_id)

            if not docente_ids and (
                "docente" in request.POST or "docente_id" in request.POST
            ):
                d_id = request.POST.get("docente") or request.POST.get(
                    "docente_id"
                )
                if d_id:
                    docente_ids.append(str(d_id))

            for d_id in docente_ids:
                registros_data.append(
                    {
                        "docente_id": int(d_id),
                        "fecha": fecha,
                        "estado": request.POST.get(f"estado_{d_id}")
                        or request.POST.get("estado", "PRESENTE"),
                        "marca_diaria": request.POST.get(f"marca_diaria_{d_id}")
                        or request.POST.get("marca_diaria"),
                        "tipo_licencia_id": request.POST.get(
                            f"tipo_licencia_{d_id}"
                        )
                        or request.POST.get("tipo_licencia"),
                        "cargo_id": request.POST.get(f"cargo_{d_id}")
                        or request.POST.get("cargo"),
                        "observaciones": request.POST.get(
                            f"observaciones_{d_id}"
                        )
                        or request.POST.get("observaciones", ""),
                        "justifica": request.POST.get(f"justifica_{d_id}"),
                    }
                )

        if not registros_data:
            messages.warning(
                request, "No se recibieron registros para la carga diaria."
            )
            return redirect("asistencia:asistencia_list")

        # Ticket 10.5: Extraer IDs para precarga masiva en memoria con in_bulk
        doc_ids = set()
        lic_ids = set()
        cargo_ids = set()
        fechas = set()

        for item in registros_data:
            if isinstance(item, RegistroAsistencia):
                doc_ids.add(item.docente_id)
                fechas.add(item.fecha)
                if item.tipo_licencia_id:
                    lic_ids.add(item.tipo_licencia_id)
                if item.cargo_id:
                    cargo_ids.add(item.cargo_id)
                continue

            doc_val = item.get("docente_id") or item.get("docente")
            if isinstance(doc_val, Docente):
                doc_ids.add(doc_val.pk)
            elif doc_val is not None:
                try:
                    doc_ids.add(int(doc_val))
                except (ValueError, TypeError):
                    pass

            lic_val = item.get("tipo_licencia_id") or item.get("tipo_licencia")
            if isinstance(lic_val, TipoLicencia):
                lic_ids.add(lic_val.pk)
            elif lic_val is not None:
                try:
                    lic_ids.add(int(lic_val))
                except (ValueError, TypeError):
                    pass

            cargo_val = item.get("cargo_id") or item.get("cargo")
            if isinstance(cargo_val, CargoDocente):
                cargo_ids.add(cargo_val.pk)
            elif cargo_val is not None:
                try:
                    cargo_ids.add(int(cargo_val))
                except (ValueError, TypeError):
                    pass

            item_fecha = item.get("fecha") or fecha
            if isinstance(item_fecha, str):
                item_fecha = parse_date(item_fecha) or fecha
            fechas.add(item_fecha)

        try:
            with transaction.atomic():
                # Precarga en memoria con in_bulk y diccionarios (Ticket 10.5)
                docentes_map = Docente.objects.in_bulk(doc_ids)
                licencias_map = (
                    TipoLicencia.objects.in_bulk(lic_ids) if lic_ids else {}
                )
                cargos_map = (
                    CargoDocente.objects.in_bulk(cargo_ids) if cargo_ids else {}
                )
                registros_existentes_map = {
                    (r.docente_id, r.fecha): r
                    for r in RegistroAsistencia.objects.filter(
                        docente_id__in=doc_ids, fecha__in=fechas
                    )
                }

                nuevos = []
                existentes = []
                guardados = []
                audit_user = (
                    request.user
                    if (
                        request.user is not None
                        and getattr(request.user, "is_authenticated", True)
                    )
                    else None
                )
                ahora = timezone.now()

                audit_user_id = audit_user.pk if audit_user else None
                for item in registros_data:
                    if isinstance(item, RegistroAsistencia):
                        instancia = item
                        created = instancia.pk is None
                        if created:
                            if not instancia.creado_por_id:
                                instancia.creado_por_id = audit_user_id
                            instancia.modificado_por_id = audit_user_id
                            instancia.actualizado_en = ahora
                            instancia.clean()
                            nuevos.append(instancia)
                        else:
                            instancia.modificado_por_id = audit_user_id
                            instancia.actualizado_en = ahora
                            instancia.clean()
                            existentes.append(instancia)
                        guardados.append(instancia)
                        continue

                    # Obtener docente desde memoria
                    doc_val = item.get("docente_id") or item.get("docente")
                    if isinstance(doc_val, Docente):
                        docente_obj = doc_val
                    else:
                        try:
                            docente_obj = docentes_map.get(int(doc_val))
                        except (ValueError, TypeError):
                            docente_obj = None

                    if not docente_obj:
                        continue

                    item_fecha = item.get("fecha") or fecha
                    if isinstance(item_fecha, str):
                        item_fecha = parse_date(item_fecha) or fecha

                    # Buscar o instanciar desde el mapa en memoria
                    reg = registros_existentes_map.get(
                        (docente_obj.id, item_fecha)
                    )
                    created = reg is None
                    if created:
                        reg = RegistroAsistencia(
                            docente=docente_obj, fecha=item_fecha
                        )

                    estado = item.get("estado", "PRESENTE")
                    reg.estado = estado

                    # Marca diaria coherente por defecto
                    marca = item.get("marca_diaria")
                    if not marca:
                        if estado == "PRESENTE":
                            marca = "PR"
                        elif estado == "AUSENTE":
                            marca = "I"
                        elif estado == "LICENCIA":
                            marca = "LIC"
                        else:
                            marca = "P"
                    reg.marca_diaria = marca

                    # Licencia desde mapa en memoria
                    lic_val = item.get("tipo_licencia_id") or item.get(
                        "tipo_licencia"
                    )
                    if lic_val and estado == "LICENCIA":
                        if isinstance(lic_val, TipoLicencia):
                            reg.tipo_licencia = lic_val
                        else:
                            try:
                                reg.tipo_licencia = licencias_map.get(
                                    int(lic_val)
                                )
                            except (ValueError, TypeError):
                                reg.tipo_licencia = None
                    else:
                        reg.tipo_licencia = None

                    # Cargo desde mapa en memoria
                    cargo_val = item.get("cargo_id") or item.get("cargo")
                    if cargo_val:
                        if isinstance(cargo_val, CargoDocente):
                            reg.cargo = cargo_val
                        else:
                            try:
                                reg.cargo = cargos_map.get(int(cargo_val))
                            except (ValueError, TypeError):
                                reg.cargo = None
                    else:
                        reg.cargo = None

                    if "observaciones" in item:
                        reg.observaciones = item["observaciones"] or ""

                    justifica_val = item.get("justifica")
                    if justifica_val is not None and str(
                        justifica_val
                    ).lower() in [
                        "false",
                        "0",
                        "no",
                    ]:
                        reg.justifica = False
                    elif estado == "AUSENTE":
                        reg.justifica = False
                    elif estado in ["PRESENTE", "JUSTIFICADO"]:
                        reg.justifica = True

                    # Auditoría y validación en memoria
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

                    guardados.append(reg)

                # Persistencia optimizada en lote
                if nuevos:
                    RegistroAsistencia.objects.bulk_create(nuevos)
                if existentes:
                    RegistroAsistencia.objects.bulk_update(
                        existentes,
                        fields=[
                            "estado",
                            "marca_diaria",
                            "tipo_licencia",
                            "cargo",
                            "observaciones",
                            "justifica",
                            "modificado_por",
                            "actualizado_en",
                        ],
                    )

            # Notificación según si es feriado o jornada habitual
            if es_feriado:
                messages.warning(
                    request,
                    f"Asistencia del feriado ({feriado.descripcion}) "
                    "registrada correctamente. El motor mensual omitirá esta "
                    "fecha en la liquidación de horas.",
                )
            else:
                messages.success(
                    request,
                    f"Asistencia diaria del {fecha.strftime('%d/%m/%Y')} "
                    "guardada con éxito.",
                )

            return redirect(
                f"{request.path}?fecha={fecha.strftime('%Y-%m-%d')}"
            )

        except (ValidationError, IntegrityError, Exception) as exc:
            messages.error(
                request,
                f"Error al procesar la asistencia diaria: {exc}. "
                "Se revirtieron todas las operaciones y no se guardó ningún registro.",
            )
            context = {
                "titulo": "Asistencia Diaria",
                "fecha": fecha,
                "feriado": feriado,
                "es_feriado": es_feriado,
                "error": True,
            }
            return render(
                request, "asistencia/carga_masiva.html", context, status=400
            )


# Alias para retrocompatibilidad total con Ticket 3.8 y rutas existentes
CargaDiariaMasivaView = AsistenciaDiariaView


class JustificacionesLoteView(LoginRequiredMixin, View):
    """
    Vista para Justificaciones por Lote de Inasistencias (Ticket 7 y 3.8).
    """

    def get(self, request):
        return render(
            request,
            "asistencia/justificaciones_lote.html",
            {"titulo": "Justificaciones por Lote"},
        )

    def post(self, request):
        lote_items = request.POST.getlist("items", [])
        if not lote_items:
            messages.warning(
                request, "No se recibieron registros para justificar."
            )
            return redirect("asistencia:asistencia_list")

        try:
            justificar_lote_asistencias(
                lote_items, usuario=request.user, request=request
            )
            messages.success(
                request, "Lote de justificaciones procesado exitosamente."
            )
            return redirect("asistencia:asistencia_list")
        except (ValidationError, IntegrityError, Exception):
            return render(
                request,
                "asistencia/justificaciones_lote.html",
                {"titulo": "Justificaciones por Lote", "error": True},
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


class DiaNoLaborableCreateView(LoginRequiredMixin, AuditoriaFormMixin, CreateView):
    """
    Alta de nuevo feriado o día no laborable con auditoría (Ticket 4).
    """

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
        messages.success(
            self.request, "Día no laborable registrado con éxito."
        )
        return super().form_valid(form)


class DiaNoLaborableUpdateView(LoginRequiredMixin, AuditoriaFormMixin, UpdateView):
    """
    Edición de feriado o día no laborable existente con auditoría (Ticket 4).
    """

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
        messages.success(
            self.request, "Día no laborable modificado con éxito."
        )
        return super().form_valid(form)


class DiaNoLaborableDeleteView(LoginRequiredMixin, DeleteView):
    """
    Eliminación de un día no laborable / feriado del calendario (Ticket 4).
    """

    model = DiaNoLaborable
    template_name = "asistencia/dianolaborable_confirm_delete.html"
    context_object_name = "feriado"
    success_url = reverse_lazy("asistencia:feriado_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Eliminar Día No Laborable"
        return context

    def form_valid(self, form):
        messages.success(
            self.request, "Día no laborable eliminado correctamente."
        )
        return super().form_valid(form)
