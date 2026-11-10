# Matriz de Trazabilidad de Requerimientos y Reglas de Negocio

### Proyecto Zunin - IESETyFP (Bedelía y Asistencia Docente)

Esta matriz documenta la vinculación bidireccional entre los **Requerimientos Funcionales (RF)**, las **Reglas de Negocio (RN)**, los **Tickets del Backlog Maestro**, los **componentes de código fuente** y las **pruebas automatizadas** que garantizan su cumplimiento institucional.

---

## 1. Tabla de Requerimientos Funcionales (RF)

| ID | Requerimiento Funcional | Ticket Asociado | Archivos de Implementación | Suite de Tests de Validación |
| :--- | :--- | :---: | :--- | :--- |
| **RF-01** | **Gestión de Personal Docente**: Alta, edición, filtrado y baja lógica (soft delete) con preservación histórica. | Ticket 6 / 12.1 | `apps/personal/models.py`<br>`apps/personal/views.py`<br>`apps/personal/forms.py` | `apps/personal/tests/test_personal.py` |
| **RF-02** | **Catálogos de Carreras y Espacios Curriculares**: Administración de tecnicaturas, comisiones, turnos y materias. | Ticket 12.4 | `apps/personal/models.py`<br>`apps/personal/views.py` | `apps/personal/tests/test_espacio_curricular.py` |
| **RF-03** | **Designación de Cargos Docentes**: Vinculación de docentes con espacios curriculares y distribución semanal de horas. | Ticket 6 / 12.2 | `apps/personal/models.py`<br>`apps/personal/views.py`<br>`apps/personal/forms.py` | `apps/personal/tests/test_personal.py` |
| **RF-04** | **ABM de Feriados y Días No Laborables**: Carga de feriados y asuetos con auditoría de usuario creador. | Ticket 4 | `apps/asistencia/models.py`<br>`apps/asistencia/views.py`<br>`apps/asistencia/forms.py` | `apps/asistencia/tests.py` |
| **RF-05** | **Parte Diario de Asistencia**: Matriz interactiva de carga por fecha con marcas estándar (P, I, LIC, LT). | Ticket 5 / 12.6 | `apps/asistencia/views.py`<br>`apps/asistencia/templates/asistencia/carga_masiva.html` | `apps/asistencia/tests.py`<br>`apps/asistencia/tests_ticket_12_6.py` |
| **RF-06** | **Carga Masiva de Asistencia**: Procesamiento atómico en lote de novedades con omisión de días no laborables. | Ticket 5 / 12.6 | `apps/asistencia/views.py`<br>`apps/asistencia/services.py` | `apps/asistencia/tests_ticket_12_6.py` |
| **RF-07** | **Consulta y Filtros de Asistencia**: Buscador predictivo por docente, carrera, fecha y estado de asistencia. | Ticket 12.6 | `apps/asistencia/views.py`<br>`apps/asistencia/templates/asistencia/asistencia_list.html` | `apps/asistencia/tests_ticket_12_6.py` |
| **RF-08** | **Catálogo de Licencias Estatutarias**: Consulta de régimen legal (código, artículo, forma de pago, cuadro mensual). | Ticket 8 | `apps/licencias/models.py`<br>`apps/licencias/views.py`<br>`apps/licencias/forms.py` | `apps/licencias/tests/test_ticket_8_catalogo.py` |
| **RF-09** | **Justificación Diferida de Inasistencias**: Transición de inasistencias ('I') a 'LIC' mediante formulario en papel. | Ticket 7 / RN-03 | `apps/licencias/views.py`<br>`apps/licencias/forms.py`<br>`apps/licencias/services.py` | `apps/licencias/tests/test_justificacion_diferida.py` |
| **RF-10** | **API de Autocompletado Predictivo**: Endpoint JSON para autocompletar código a partir de artículo estatutario. | Ticket 10 | `apps/licencias/api_urls.py`<br>`apps/licencias/views.py` | `apps/licencias/tests/test_api_autocompletado.py` |
| **RF-11** | **Planillas Mensuales (IL-01 / IL-02)**: Consolidación mensual automática de novedades desglosadas por materia y horas. | Ticket 9 / 10.8 | `apps/licencias/services.py`<br>`apps/licencias/views.py`<br>`apps/licencias/models.py` | `apps/licencias/tests/test_ticket_9_planillas.py`<br>`apps/licencias/tests/test_ticket_10_8_navegacion_planillas.py` |
| **RF-12** | **Conmutación de Resoluciones Ministeriales**: Registro de número oficial externo (M.E.C.C.y T.) alternativo a Disposición. | Ticket 10.3 | `apps/licencias/views.py`<br>`apps/licencias/forms.py`<br>`apps/licencias/templates/licencias/planilla_list.html` | `apps/licencias/tests/test_ticket_10_3_resoluciones.py` |
| **RF-13** | **Exportación Oficial a CSV**: Descarga tabular de planillas mensuales con los 9 encabezados requeridos. | Ticket 9 / 10.3 | `apps/licencias/views.py` (`ExportarPlanillaCSVView`) | `apps/licencias/tests/test_ticket_9_planillas.py`<br>`apps/licencias/tests/test_ticket_10_3_resoluciones.py` |
| **RF-14** | **Dashboard y Panel de Alertas**: Monitoreo en tiempo real de inasistencias acumuladas y licencias por vencer. | Ticket 12 | `apps/core/views.py`<br>`apps/core/services.py`<br>`apps/core/templates/core/dashboard.html` | `apps/core/tests/test_ticket_12_panel_alertas.py` |
| **RF-15** | **Control de Acceso RBAC Estricto**: Restricción de operaciones por rol (Admin_Institucional, Bedelia_Operadoras, Consulta). | Ticket 11 / 10.6 | `apps/core/mixins.py`<br>`apps/core/templatetags/auth_tags.py`<br>`templates/403.html` | `apps/core/tests/test_ticket_11_permisos_estrictos.py`<br>`apps/licencias/tests/test_ticket_10_6_permisos.py` |
| **RF-16** | **Auditoría Transaccional Automática**: Registro automático de autor y timestamp en creación y actualización. | Transversal | `apps/core/models.py` (`AuditoriaModel`)<br>`apps/core/audit.py` (`audit_save`) | `apps/core/tests/test_audit.py` |
| **RF-17** | **Sincronización Automática de Licencias con Asistencia Diaria**: Reflejo automático de marcas (LIC, LT) al aprobar y reversión ante anulación. | Ticket 18.1 | `apps/licencias/models.py`<br>`apps/licencias/services.py`<br>`apps/licencias/views.py` | `apps/licencias/tests/test_ticket_18_1_sincronizacion_asistencia.py` |

---

## 2. Tabla de Reglas de Negocio (RN)

| Regla | Descripción de la Regla de Negocio | Impacto en el Sistema | Archivo de Implementación | Test Automatizado |
| :--- | :--- | :--- | :--- | :--- |
| **RN-01** | **Vigencia Temporal de Designaciones** | Las asistencias y liquidaciones de horas solo aplican si `cargo.es_designacion_vigente(fecha)` es verdadero. | `apps/personal/models.py`<br>`apps/licencias/services.py` | `apps/licencias/tests/test_motor_mensual.py` |
| **RN-02** | **Cómputo Hábil Inteligente** | El cálculo de días hábiles salta automáticamente sábados, domingos y días feriados de `DiaNoLaborable`. | `apps/licencias/services.py`<br>`apps/asistencia/services.py` | `apps/licencias/tests/test_ticket_10_7_dias_habiles_desacoplamiento.py` |
| **RN-03** | **Integridad Histórica de Planillas** | Novedades cargadas sobre meses con planilla ya emitida no eliminan renglones existentes; los marcan como desactualizados y preservan sus números de instrumento. | `apps/licencias/services.py`<br>`apps/licencias/models.py` | `apps/licencias/tests/test_justificacion_diferida.py` |
| **RN-04** | **Correlatividad Anual de Instrumentos (001/YYYY)** | El contador correlativo de disposiciones es anual. Al cambiar de año (Enero), se reinicia a `001/YYYY`. | `apps/licencias/services.py` (`generar_planilla_mes`) | `apps/core/tests/test_ticket_14_e2e_tiempo.py` |
| **RN-05** | **Blindaje RBAC y Restricción de Borrado** | Operadoras de Bedelía pueden crear y editar asistencias y licencias, pero tienen estrictamente prohibida la eliminación de datos. | `apps/core/mixins.py`<br>`apps/licencias/views.py` | `apps/core/tests/test_ticket_11_permisos_estrictos.py` |
| **RN-06** | **Unicidad Diaria de Inasistencia** | Un docente no puede registrar inasistencias en fechas donde no tenga obligación horaria o duplicar cargas el mismo día. | `apps/asistencia/models.py`<br>`apps/licencias/models.py` | `apps/licencias/tests/test_ticket_12_7_unique_constraint.py` |
| **RN-07** | **Baja Lógica Institucional (Soft Delete)** | El personal docente y sus designaciones no se eliminan físicamente (`activo=False`) para resguardar la memoria administrativa. | `apps/personal/models.py`<br>`apps/personal/views.py` | `apps/personal/tests/test_personal.py` |
| **RN-08** | **Auditoría Transaccional Obligatoria** | Todo cambio crítico se ejecuta bajo `transaction.atomic()` registrando al usuario autenticado en sesión. | `apps/core/audit.py`<br>`apps/asistencia/views.py` | `apps/core/tests/test_audit.py` |
| **RN-09** | **Búsqueda Predictiva Insensible a Tildes** | El buscador y autocompletado estatutario normaliza caracteres Unicode (NFKD) para coincidir con y sin tildes. | `apps/licencias/forms.py`<br>`apps/licencias/views.py` | `apps/licencias/tests/test_ticket_8_catalogo.py`<br>`apps/licencias/tests/test_api_autocompletado.py` |
| **RN-10** | **Formateo de Resoluciones Ministeriales** | En planillas y CSV, el instrumento con `RESOLUCION` debe prefijarse como `Resolución <número>` evitando números internos de disposición. | `apps/licencias/views.py` (`ExportarPlanillaCSVView`) | `apps/licencias/tests/test_ticket_10_3_resoluciones.py` |
| **RN-11** | **Consolidación de Adyacencia** | Períodos continuos de inasistencia justificada con la misma licencia se consolidan en un único bloque de planilla mensual. | `apps/licencias/services.py` | `apps/licencias/tests/test_motor_mensual.py` |
| **RN-12** | **Desglose Curricular Exacto de Horas** | El cálculo de horas afectadas evalúa día por día los módulos asignados al cargo según el día de la semana (`horas_lunes`, etc.). | `apps/personal/models.py`<br>`apps/licencias/services.py` | `apps/personal/tests/test_personal.py` |

---

## 3. Cobertura de Verificación Automatizada

- **Total de Pruebas Unitarias e Integración:** 379 tests
- **Tasa de Aprobación:** 100% (todos los tests en verde)
- **Conformidad de Estilo (PEP8):** 0 errores de `flake8`
- **Simulación Temporal E2E:** Validada exitosamente mediante `freezegun` en `apps/core/tests/test_ticket_14_e2e_tiempo.py`.

