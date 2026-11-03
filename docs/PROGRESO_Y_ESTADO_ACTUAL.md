# Estado Actual y Registro de Progreso del Proyecto
## Sistema de Gestión Institucional IESETyFP (Zunin)

**Última actualización:** 02 de Noviembre de 2026, 23:25 hs  
**Rama activa:** `main` (Sincronizada con `origin/main` en commit `8b9ac42`)  
**Estado del entorno:** Limpio, 0 migraciones pendientes, 0 advertencias de linters, 260/260 tests pasando.

---

## 📌 Guía Rápida para el Agente al Retomar la Sesión

Si la sesión se reinicia o se pierde el contexto, lee este documento completo antes de iniciar cualquier tarea:
1. **Ruta del Proyecto:** `/home/javier/3ro/Desarrollo Web - Cristian Miranda/ZuninAPP/zunin`
2. **Entorno Virtual de Python:** `./venv/bin/python` y `./venv/bin/pip` (¡NO usar `/usr/bin/python` del sistema porque faltan librerías como django-environ!).
3. **Comandos de Verificación Inmediata:**
   ```bash
   ./venv/bin/python manage.py check
   ./venv/bin/python manage.py makemigrations --check --dry-run
   ./venv/bin/flake8 .
   ./venv/bin/black --check .
   ./venv/bin/python manage.py test
   ```
4. **Flujo de Trabajo para Nuevos Tickets:**
   - Asegurarse de estar en `main` y con pull actualizado: `git checkout main && git pull origin main`.
   - Crear rama de feature: `git checkout -b feature/ticket-XX-...`.
   - Implementar código, migraciones si aplica y suite de pruebas unitarias.
   - Ejecutar linter (`./venv/bin/flake8 .` y `./venv/bin/black --check .`).
   - Ejecutar pruebas (`./venv/bin/python manage.py test`).
   - Commit con Conventional Commits: `feat(...)`, `fix(...)`, `chore(...)`.
   - Push al remoto: `git push -u origin feature/ticket-XX-...`.
   - Generar el enlace del PR y el comentario descriptivo en Markdown para el usuario.

---

## 📋 Historial Detallado de Tickets Implementados y Merged en `main`

### 1. Ticket 11: Permisos Estrictos en Vistas (HTTP 403)
- **Objetivo:** Asegurar que los accesos denegados retornen 403 estricto con `raise_exception=True` en lugar de redirigir al login.
- **Implementación:** `PermisosEstrictosMixin`, plantillas `403.html`, validaciones en vistas de Asistencia, Personal y Licencias.
- **Pruebas:** `apps/core/tests/test_ticket_11_permisos_estrictos.py`.

### 2. Ticket 12: Consultas y Panel de Alertas Preventivas (RF-18)
- **Objetivo:** Panel de alertas preventivas en el Dashboard calculando `(Faltas 'I' / Límite Legal) * 100` (límite base de 15 días).
- **Implementación:** Consulta optimizada en `apps/core/services.py` con `annotate(Count(filter=Q(marca='I')))` y `ExpressionWrapper`. Umbrales visuales: >70% Precaución (Naranja), >100% Crítico (Rojo).
- **Pruebas:** `apps/core/tests/test_ticket_12_panel_alertas.py` (valida caso de 11 faltas -> 73%).

### 3. Ticket 12.5: Verificación de Dependencias y Decisiones de Arquitectura (ADR)
- **Objetivo:** Auditoría pre-cierre y documentación formal de decisiones arquitectónicas.
- **Implementación:**
  - Dependencia explícita `freezegun>=1.4.0` en `requirements.txt`.
  - Documento técnico en [docs/DECISIONES_ARQUITECTURA.md](docs/DECISIONES_ARQUITECTURA.md) cubriendo:
    a) Tailwind CSS vía CDN para prototipado institucional sin NodeJS.
    b) Mapeo legacy de tablas (`db_table = "gestion_asistencia_..."`) para preservar datos históricos.
    c) Estrategia de auditoría híbrida polimórfica (`AuditoriaModel`, `AuditoriaFormMixin`, `audit_save`).
  - Formateo global y cumplimiento estricto con `flake8` y `black`.

### 4. Ticket 12.6: Módulo de Consulta Avanzada Multicriterio (Asistencia)
- **Objetivo:** Filtros multicriterio de asistencia (por DNI/apellido, estado, marca diaria, materia/espacio curricular y rango de fechas).
- **Implementación:** `ConsultaAsistenciaForm`, servicio de filtrado en `apps/asistencia/services.py` y template interactivo en `asistencia_list.html`.
- **Pruebas:** `apps/asistencia/tests_ticket_12_6.py`.

### 5. Ticket 12.7: UniqueConstraint de Idempotencia en BD (RenglonPlanillaMensual)
- **Objetivo:** Impedir duplicados en planillas mensuales por inserciones manuales o fallos de concurrencia.
- **Implementación:** `UniqueConstraint` en `RenglonPlanillaMensual.Meta` sobre `(docente, cargo, mes, anio, desde, hasta)` con `condition=models.Q(desactualizada=False)` para compatibilidad con RN-03.
- **Migración:** `licencias.0004_renglonplanillamensual_unique_renglon_docente_cargo_periodo_fechas`.
- **Pruebas:** `apps/licencias/tests/test_ticket_12_7_unique_constraint.py`.

### 6. Ticket 12.8: Trazabilidad Temporal en Modelos
- **Objetivo:** Campos de auditoría temporal `creado_en` y `actualizado_en` en entidades de catálogo.
- **Implementación:** Añadidos a `CargoDocente` y `TipoLicencia`.
- **Migraciones:** `personal.0003_cargodocente_actualizado_en_cargodocente_creado_en` y `licencias.0005_tipolicencia_actualizado_en_tipolicencia_creado_en`.
- **Pruebas:** `apps/licencias/tests/test_ticket_12_8_trazabilidad_temporal.py`.

### 7. Ticket 12.9: Normalización Relacional de EspacioCurricular
- **Objetivo:** Migrar el campo `carrera` de `CharField` a `ForeignKey(Carrera, on_delete=models.PROTECT)`.
- **Implementación:**
  - `EspacioCurricular.carrera` normalizado con soporte defensivo retrocompatible en `__init__`.
  - Migración con `RunPython`: [apps/personal/migrations/0004_espaciocurricular_carrera_fk.py](apps/personal/migrations/0004_espaciocurricular_carrera_fk.py) mapeando strings existentes a IDs de `Carrera`.
  - `EspacioCurricularAdmin.search_fields` actualizado a `carrera__nombre` y `carrera__codigo`.
  - Seeder y factories actualizados.
- **Pruebas:** `apps/personal/tests_ticket_12_9.py`.

---

## 🗄️ Estructura del Grafo de Migraciones Reciente

| App | Migración Actual | Dependencia Previa | Propósito |
| :--- | :--- | :--- | :--- |
| `personal` | `0001_initial` | - | Modelos iniciales |
| `personal` | `0002_cargodocente_...` | `0001_initial` | Campos días fin de semana |
| `personal` | `0003_cargodocente_actualizado_en...` | `0002_...` | Trazabilidad temporal CargoDocente (Ticket 12.8) |
| `personal` | `0004_espaciocurricular_carrera_fk` | `0003_...` | FK normalizada Carrera (Ticket 12.9) |
| `licencias` | `0004_renglonplanillamensual_unique...` | `0003_...` | Restricción de unicidad (Ticket 12.7) |
| `licencias` | `0005_tipolicencia_actualizado_en...` | `0004_...` | Trazabilidad temporal TipoLicencia (Ticket 12.8) |

---

## 🛠️ Tecnologías y Configuración Clave
- **Django:** 5.1.15
- **Base de Datos Local:** SQLite (`db.sqlite3`)
- **Base de Datos Producción:** MySQL (`PyMySQL` + `cryptography`)
- **Linters:** `flake8` (`.flake8`, max-line-length = 88) y `black` (línea máx 88)
- **Testing:** 260 tests automatizados (`Ran 260 tests in ~80-120s, OK`)
- **Estilos UI:** Tailwind CSS CDN configurado en `templates/base.html` con paleta institucional.
