# Registro de Decisiones de Arquitectura (ADR)
## Sistema de Gestión de Asistencia y Personal Docente — IESETyFP (Zunin)

**Fecha:** Noviembre 2026  
**Estado:** Aprobado / Implementado  
**Versión del Proyecto:** Pre-Cierre / Release Candidate  

---

## 1. Contexto y Propósito

El presente documento formaliza las decisiones de arquitectura de software y diseño de base de datos adoptadas durante el desarrollo del sistema de gestión institucional del IESETyFP. El objetivo es salvaguardar la coherencia técnica, la trazabilidad de las decisiones tomadas y facilitar el mantenimiento evolutivo a futuros mantenedores e inspectores de calidad técnica.

---

## 2. Decisión A: Prototipado Ágil e Interfaz Institucional mediante Tailwind CSS CDN (Sin Node.js)

### 2.1 Contexto y Problemática
El sistema requería una interfaz moderna, responsiva, accesible y visualmente alineada con la identidad corporativa del IESETyFP (colores institucionales, tipografía Inter, optimización para dispositivos móviles y soporte PWA). Al mismo tiempo, la infraestructura de desarrollo y el entorno de despliegue institucional requerían minimizar la complejidad operativa, evitando la instalación de Node.js, `npm`, herramientas de compilación pesadas (Webpack, Vite, PostCSS) o pipelines CI/CD que ralentizaran las iteraciones y el mantenimiento.

### 2.2 Decisión Adoptada
Se adoptó la distribución **Tailwind CSS vía CDN** integrada directamente en la plantilla base (`templates/base.html`), configurada dinámicamente mediante `tailwind.config` en el navegador del cliente.

### 2.3 Justificación y Ventajas Técnicas
1. **Cero Dependencia de Node.js en Servidor y Local:** La ejecución del proyecto solo requiere Python y el entorno virtual (`venv`), eliminando conflictos de versiones de Node, dependencias huérfanas en `node_modules` y pasos de compilación previa.
2. **Prototipado y Validación Rápida:** Cualquier ajuste visual o componente nuevo se diseña y renderiza de inmediato en los templates de Django usando utilidades estándar de Tailwind.
3. **Paleta Institucional Centralizada:** Se configuró un tema institucional unificado (`institucional` con escalas 50–950, acentos ámbar y tipografía sans-serif con Google Fonts Inter), garantizando consistencia visual en todas las vistas (Dashboard, Asistencia, Licencias, Personal y Vistas de Error 403/404/500).
4. **Camino de Migración Claro:** Dado que todo el marcado HTML utiliza clases utilitarias estándar de Tailwind CSS, en una etapa futura de producción masiva con tráfico intensivo es trivial instalar `@tailwindcss/cli` y compilar un bundle CSS estático minificado mediante PurgeCSS/JIT sin necesidad de modificar el código HTML de las plantillas.

---

## 3. Decisión B: Mapeo Legacy de Tablas (`db_table = "gestion_asistencia_..."`) para Preservar Datos Históricos

### 3.1 Contexto y Problemática
El proyecto evolucionó modularizando el código en distintas aplicaciones de Django (`apps.personal`, `apps.asistencia`, `apps.licencias`, `apps.core`). Sin embargo, existían bases de datos preexistentes en producción y dumps SQL históricos generados bajo una aplicación monolítica previa denominada `gestion_asistencia`. Si Django aplicaba su convención por defecto para el nombrado de tablas (`<app_label>_<model_name>`), se hubieran creado tablas como `personal_docente` o `licencias_renglonplanillamensual`, provocando pérdida de datos históricos, inconsistencias de llaves foráneas y la necesidad de ejecutar scripts de migración ETL destructivos de alto riesgo.

### 3.2 Decisión Adoptada
Se forzó explícitamente el nombre físico de las tablas en la clase interna `Meta` de cada modelo mediante el atributo `db_table = "gestion_asistencia_<nombre>"`.

### 3.3 Mapeo de Tablas Principales
| Aplicación Django | Modelo Django | Nombre Físico en BD (`db_table`) | Propósito / Datos Históricos |
| :--- | :--- | :--- | :--- |
| `apps.personal` | `Docente` | `gestion_asistencia_docente` | Legajos, DNI, nombres y estado activo del personal docente |
| `apps.personal` | `Carrera` | `gestion_asistencia_carrera` | Carreras y tecnicaturas dictadas |
| `apps.personal` | `EspacioCurricular` | `gestion_asistencia_espaciocurricular` | Materias y asignaturas de los planes de estudio |
| `apps.personal` | `CargoDocente` | `gestion_asistencia_cargodocente` | Asignación de cargos/horas cátedra a docentes |
| `apps.personal` | `CargoCatalogo` | `gestion_asistencia_cargocatalogo` | Catálogo de tipos de cargos institucionales |
| `apps.personal` | `TipoAutorizacion` | `gestion_asistencia_tipoautorizacion` | Tipos de resoluciones y autorizaciones ministeriales |
| `apps.asistencia` | `RegistroAsistencia` | `gestion_asistencia_registroasistencia` | Marcas diarias de asistencia, inasistencias y justificaciones |
| `apps.asistencia` | `DiaNoLaborable` | `gestion_asistencia_dianolaborable` | Feriados, asuetos y jornadas institucionales |
| `apps.licencias` | `TipoLicencia` | `gestion_asistencia_tipolicencia` | Catálogo de artículos y códigos estatutarios de licencias |
| `apps.licencias` | `RenglonPlanillaMensual` | `gestion_asistencia_renglonplanillamensual` | Registro y liquidación mensual de inasistencias/licencias |

### 3.4 Justificación y Beneficios
1. **Preservación Total de Datos Históricos:** Permite montar el sistema sobre bases de datos existentes sin renombrar tablas físicas ni destruir relaciones foráneas preexistentes.
2. **Reversibilidad y Compatibilidad:** Permite convivir con herramientas de reporte o consultas SQL directas ya existentes que dependían de los nombres de tabla tradicionales.
3. **Migraciones Limpias:** Las migraciones de Django reconocen las tablas existentes sin generar operaciones destructivas `DropTable` o `RenameTable`.

---

## 4. Decisión C: Estrategia de Auditoría Híbrida Polimórfica sin Destrucción de Esquemas

### 4.1 Contexto y Problemática
El sistema requería auditoría institucional estricta (saber qué usuario creó o modificó cada registro y en qué instante). No obstante, el esquema de base de datos es híbrido:
- Modelos nuevos o rediseñados que pueden incorporar campos formales de auditoría (`creado_por`, `modificado_por`, `creado_en`, `actualizado_en`).
- Modelos legacy preexistentes donde agregar campos no nulos o llaves foráneas obligatorias hubiera requerido alterar tablas masivas en caliente o reescribir consultas históricas.
- Distintos flujos de guardado (vistas basadas en clases CBV, llamadas en servicios internos, importadores batch de CSV, tareas administrativas).

### 4.2 Decisión Adoptada
Se implementó un patrón de **auditoría híbrida y polimórfica defensiva** compuesto por tres piezas desacopladas:

1. **`AuditoriaModel` (`apps.core.models.AuditoriaModel`):**
   - Clase base abstracta de Django (`abstract = True`).
   - Define los campos:
     - `creado_por = ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True)`
     - `modificado_por = ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True)`
     - `creado_en = DateTimeField(auto_now_add=True)`
     - `actualizado_en = DateTimeField(auto_now=True)`
   - Provee propiedades de retrocompatibilidad (`creado_el`, `modificado_el`).
   - Utilizado en modelos críticos como `RegistroAsistencia` y `RenglonPlanillaMensual`.

2. **Función de Persistencia Defensiva `audit_save(obj, user, created=False)` (`apps.core.audit`):**
   - Aplica introspección de atributos con `hasattr(obj, ...)` en tiempo de ejecución.
   - Si el objeto posee `creado_por` y se trata de una creación (`created=True`), inyecta el usuario autenticado.
   - Si posee `modificado_por`, inyecta el usuario autenticado.
   - Si posee marcas de tiempo (`actualizado_en` o `fecha_modificacion`), actualiza con `timezone.now()`.
   - Si el objeto no posee alguno de estos campos (modelos legacy), la función no falla ni arroja excepciones, sino que ejecuta la validación (`full_clean()`) y `save()` de forma segura.
   - Permite auditar indistintamente tanto modelos derivados de `AuditoriaModel` como modelos legacy heterogéneos.

3. **Mixin de Intercepción para Vistas `AuditoriaFormMixin` (`apps.core.audit`):**
   - Intercepta `form_valid(self, form)` en vistas basadas en clases (`CreateView`, `UpdateView`).
   - Extrae el usuario de `self.request.user`, determina si es creación a partir de la presencia de clave primaria, invoca `audit_save(obj, user, created)` y maneja relaciones `save_m2m()` de manera uniforme.

### 4.3 Beneficios Obtenidos
- **Tolerancia a Fallos:** Nunca falla con `AttributeError` ante modelos heterogéneos o scripts desatendidos donde `user` puede ser `None` o anónimo.
- **Sin Migraciones Destructivas:** Permite auditar gradualmente cualquier entidad sin exigir la alteración de esquemas legacy que no puedan ser migrados de inmediato.
- **Trazabilidad Verificada:** Cubierta al 100% por tests automatizados en `apps/core/tests/test_audit.py`.

---

## 5. Auditoría de Estado y Configuración del Proyecto (Ticket 12.5)

Para garantizar la estabilidad pre-cierre y asegurar que cualquier desarrollador pueda clonar y ejecutar el repositorio desde cero, se llevaron a cabo las siguientes validaciones técnicas:

1. **Gestión de Dependencias (`requirements.txt`):**
   - Se añadió explícitamente `freezegun>=1.4.0` para asegurar la reproducibilidad de pruebas que dependen de congelamiento temporal.
   - Todas las dependencias (`Django`, `django-environ`, `PyMySQL`, `cryptography`, `openpyxl`, `pandas`, `flake8`, `black`, `freezegun`) se encuentran sincronizadas y fijadas con operadores de compatibilidad.

2. **Verificación de Migraciones:**
   - Ejecución de `python manage.py makemigrations --check --dry-run` con resultado: **0 cambios pendientes / No changes detected**.

3. **Calidad de Código y Estilo:**
   - Ejecución de `flake8 .` con configuración `.flake8` (max-line-length = 88): **0 advertencias de estilo**.
   - Ejecución de `black --check .`: **0 diferencias de formato (100 archivos validados)**.

4. **Chequeo del Framework:**
   - Ejecución de `python manage.py check`: **0 problemas reportados**.
