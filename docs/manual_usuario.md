# Manual de Usuario Integral - Sistema Zunin
**Sistema de Gestión de Asistencia, Personal Docente y Licencias**  
*Instituto de Educación Superior de Educación Técnica y Formación Profesional (IESETyFP)*  
**Versión del Sistema:** 2.0 (Sprint 3) &bull; **Fecha:** Noviembre 2026

---

## Índice General

1. [Introducción y Arquitectura Funcional](#1-introducción-y-arquitectura-funcional)
   - 1.1. Propósito del Sistema
   - 1.2. Perfiles y Roles de Usuario
   - 1.3. Acceso y Navegación General
2. [Módulo de Personal y Designaciones](#2-módulo-de-personal-y-designaciones)
   - 2.1. Gestión del Padrón Docente
   - 2.2. Asignación Obligatoria de Cargos Docentes
   - 2.3. Configuración de Turnos y Carga Horaria
   - 2.4. Suplencias y Régimen DP-01
   - 2.5. Cese Puntual de Cargos vs. Baja de Legajo
3. [Módulo de Asistencia Diaria y Novedades](#3-módulo-de-asistencia-diaria-y-novedades)
   - 3.1. Modelo Multi-Turno por Cargo (Regla Bedelía / SIE)
   - 3.2. Carga Diaria Masiva
   - 3.3. Marcas de Asistencia y Estados Operativos
   - 3.4. Gestión de Feriados y Días No Laborables
   - 3.5. Consulta Avanzada Multicriterio
4. [Módulo de Licencias y Planillas Mensuales](#4-módulo-de-licencias-y-planillas-mensuales)
   - 4.1. Justificación Diferida de Inasistencias
   - 4.2. Planillas Mensuales Consolidadas (Cuadros IL-01 e IL-02)
   - 4.3. Conmutación de Instrumentos Legales
   - 4.4. Cambio Directo de Artículo de Licencia
   - 4.5. Exportación a CSV Optimizada para Microsoft Excel
5. [Módulo de Catálogos Institucionales](#5-módulo-de-catálogos-institucionales)
   - 5.1. Hub Central de Catálogos
   - 5.2. Espacios Curriculares (Materias y Talleres)
   - 5.3. Carreras Formativas y Tipos de Autorización
   - 5.4. Catálogo Normativo de Licencias Estatutarias
6. [Resolución de Problemas y Preguntas Frecuentes](#6-resolución-de-problemas-y-preguntas-frecuentes)

---

## 1. Introducción y Arquitectura Funcional

### 1.1. Propósito del Sistema
El **Sistema Zunin** es una plataforma web desarrollada para informatizar y agilizar la operativa diaria de la Bedelía y la Secretaría Académica del IESETyFP. Sus pilares fundamentales son:
- Control de presentismo docente con **granularidad por materia y turno**.
- Seguimiento normativo de licencias y ausentismo según el Estatuto Docente.
- Generación automatizada de los **Cuadros IL-01 (Salud)** e **IL-02 (Otras causales)** para liquidación ministerial.
- Administración del claustro docente, designaciones y catálogo académico formativo.

### 1.2. Perfiles y Roles de Usuario
El sistema implementa un esquema de **Control de Acceso Basado en Roles (RBAC)** con tres niveles de privilegio:

| Rol de Usuario | Grupo Django | Permisos y Alcance Operativo |
| :--- | :--- | :--- |
| **Administrador Institucional** | `Admin_Institucional` | Acceso irrestricto. Creación, modificación y baja lógica de docentes y designaciones; administración de usuarios y grupos; gestión total de catálogos y eliminación de feriados. |
| **Operador de Bedelía** | `Bedelia_Operadoras` | Carga operativa diaria de asistencia multi-turno; alta y modificación de feriados; procesamiento de justificaciones diferidas; reasignación de artículos y conmutación de instrumentos legales en planillas mensuales. |
| **Supervisión / Directivo** | `Consulta_Directiva` | Acceso en modo **sólo lectura**. Visualización del dashboard, consulta avanzada de asistencias, visualización de cuadros consolidados y exportación de reportes a CSV. Sin permisos de modificación ni baja. |

### 1.3. Acceso y Navegación General
1. **Inicio de Sesión:** Ingrese su usuario y contraseña institucional en `/login/`.
2. **Barra de Navegación Principal:**
   - **Dashboard:** Métricas en tiempo real y accesos rápidos del día.
   - **Personal:** Listado de docentes, gestión de legajos y cargos.
   - **Asistencia:** Carga diaria masiva, consulta histórica y calendario de feriados.
   - **Planillas (IL):** Cuadros mensuales, justificación diferida y exportaciones.
   - **Catálogos:** Menú central para carreras, materias y normativas.

---

## 2. Módulo de Personal y Designaciones

### 2.1. Gestión del Padrón Docente
El padrón docente centraliza los legajos activos e inactivos de la institución.
- **Acceso:** Menú `Personal` &rarr; `Docentes` (`/personal/docentes/`).
- **Búsqueda Dinámica:** Permite filtrar por apellido, nombre o número de DNI.
- **Alta de Docente:** Haga clic en el botón `+ Nuevo Docente`. Complete apellido, nombre, DNI, CUIL, género, fecha de nacimiento y vías de contacto (teléfono y correo).
- **Fusión Visual Docente/DNI:** En la tabla general, el DNI se presenta debajo del nombre completo, facilitando la lectura compacta en cualquier pantalla.

### 2.2. Asignación Obligatoria de Cargos Docentes
> **Regla de Negocio Crítica:** Todo docente debe poseer al menos una designación de cargo o materia activa para registrar su asistencia y computar sus haberes.

Para registrar una nueva designación:
1. Desde el listado de personal, ubique al docente y pulse el botón `+ Cargo`.
2. El sistema abrirá el formulario con el docente ya vinculado.
3. Seleccione el **Espacio Curricular** correspondiente (o el Cargo de Catálogo institucional si es función administrativa).
4. Indique la **Situación de Revista** (Titular, Interino o Suplente).
5. Seleccione el **Turno de Cursado** (Mañana, Tarde o Noche).
6. Ingrese el número de **Disposición o Resolución** ministerial habilitante.

### 2.3. Configuración de Turnos y Carga Horaria
- **Carga Horaria Semanal:** Especifique el total de horas cátedra que insume la materia.
- **Desglose Diario Opcional:** Puede desglosar la carga cátedra por día hábil (Lunes a Viernes). El sistema valida que las horas coincidan con los horarios de cursado.

### 2.4. Suplencias y Régimen DP-01
Cuando la situación de revista sea **Suplente**:
- Es obligatorio completar el campo **Docente Reemplazado**.
- Esto garantiza la trazabilidad con los formularios ministeriales DP-01, asociando de forma inequívoca al suplente con el titular de la cátedra durante el período de licencia.

### 2.5. Cese Puntual de Cargos vs. Baja de Legajo
- **Cesar Cargo:** Si un docente deja de dictar una materia en particular pero continúa en la institución, ingrese a `Cargos` &rarr; `Cesar Cargo`. Se solicitará la fecha de baja del cargo sin afectar los demás cargos ni su legajo.
- **Dar de Baja al Docente:** Si el docente finaliza toda vinculación institucional, se efectúa la baja lógica desde `Docentes` &rarr; `Dar de Baja`. Esta acción cesa en cascada todas sus designaciones activas y preserva el historial de asistencias pasadas.

---

## 3. Módulo de Asistencia Diaria y Novedades

### 3.1. Modelo Multi-Turno por Cargo (Regla Bedelía / SIE)
En instituciones de nivel superior, un docente puede desempeñar actividades en múltiples turnos y materias durante el mismo día hábil. Por ejemplo:
- Turno Mañana (08:00 a 12:00): Cátedra *Matemática I* &rarr; **Presente**.
- Turno Tarde (14:00 a 18:00): Cátedra *Programación Web* &rarr; **Ausente con Justificación**.

El Sistema Zunin implementa la restricción única `(docente, cargo, fecha)`, permitiendo computar de manera 100% independiente el presentismo de cada designación.

### 3.2. Carga Diaria Masiva
- **Ruta:** Menú `Asistencia` &rarr; `Carga Diaria` (`/asistencia/diaria/`).
- **Selector de Fecha:** Seleccione la fecha a procesar (por defecto la fecha de hoy).
- **Grilla Unificada:** Cada fila representa un cargo activo vigente en esa fecha. Se visualiza:
  - Nombre del Docente y DNI.
  - Materia, Turno e Instrumento de designación.
  - Selector de **Estado de Asistencia**.
  - Selector de **Marca Diaria**.
  - Selector de **Tipo de Licencia** (habilitado al seleccionar Licencia).
  - Campo de **Observaciones**.
  - Estado de registro previo (Pendiente o Registrado).
- **Guardado Atómico:** Al presionar `Guardar Asistencias del Día`, el sistema ejecuta una transacción atómica; si existiera alguna incoherencia en un registro, se revierten los cambios para evitar datos inconsistentes.

### 3.3. Marcas de Asistencia y Estados Operativos

| Estado | Marca | Significado Operativo | Imputación en Liquidación |
| :--- | :---: | :--- | :--- |
| **PRESENTE** | `PR` | Docente presente en la cátedra/turno. | Cómputo normal de haberes. |
| **AUSENTE** | `I` | Inasistencia injustificada sin aviso. | Descuento automático de horas cátedra. |
| **LICENCIA** | `LIC` / `LT` | Licencia estatutaria con aviso o certificado. | Deriva al Cuadro IL correspondiente (con/sin goce). |
| **JUSTIFICADO** | `P` | Permiso institucional o justificación reglamentaria. | No genera descuento si está habilitado por normativa. |

### 3.4. Gestión de Feriados y Días No Laborables
- **Acceso:** Menú `Asistencia` &rarr; `Feriados` (`/asistencia/feriados/`).
- **Alerta Visual:** Si el día seleccionado es feriado o asueto, la grilla diaria se resalta automáticamente en color rojo, advirtiendo al operador.
- **Sin Bloqueo Operativo:** El sistema permite registrar actividades especiales en días feriados (ej. jornadas o exámenes extraordinarios); el motor mensual omite automáticamente el cómputo de días no laborables para no generar inasistencias indebidas.
- **Permisos de Eliminación:** Por seguridad institucional, solo el rol `Admin_Institucional` puede eliminar feriados registrados.

### 3.5. Consulta Avanzada Multicriterio
- **Ruta:** `/asistencia/consulta/`
- Permite filtrar simultáneamente por:
  - Rango de fechas (`Desde` y `Hasta`).
  - Docente específico (búsqueda por nombre o DNI).
  - Espacio Curricular / Materia.
  - Estado de asistencia (`PRESENTE`, `AUSENTE`, `LICENCIA`, `JUSTIFICADO`).
  - Tipo de Licencia asignado.
- Paginación estandarizada de **25 registros por página** para máxima velocidad de respuesta.

---

## 4. Módulo de Licencias y Planillas Mensuales

### 4.1. Justificación Diferida de Inasistencias
En la operativa habitual, los docentes presentan certificados médicos o notas de justificación días después de ocurrida la falta.
- **Acceso:** Menú `Planillas` &rarr; `Justificación Diferida` (`/licencias/justificacion-diferida/`).
- **Procedimiento:**
  1. Filtre las inasistencias por rango de fecha o por docente.
  2. Seleccione la inasistencia injustificada previa.
  3. Indique el **Tipo de Licencia** correspondiente (ej. `LIC-340A` Enfermedad Común).
  4. Adjunte las observaciones o número de certificado.
  5. Al confirmar, el sistema actualiza retroactivamente la asistencia, recalcula los días e incorpora la novedad a la planilla mensual correspondiente.

### 4.2. Planillas Mensuales Consolidadas (Cuadros IL-01 e IL-02)
- **Ruta:** Menú `Planillas` &rarr; `Planillas Mensuales` (`/licencias/planillas/`).
- **Clasificación Ministerial de Cuadros:**
  - **Cuadro IL-01 (Salud):** Corto tratamiento médico, largo tratamiento, licencias por maternidad y afecciones de salud.
  - **Cuadro IL-02 (Otras Causales):** Exámenes, duelo familiar, comisiones de servicio, razones particulares, gremiales y políticas.
- **Tabla Compacta de Renglones:**
  - Columna **Cuadro / Período**: Muestra el mes/año y el estado de vigencia (*Vigente* o *Rectificada*).
  - Columna **Instrumento Legal**: Identifica si se trata de Disposición Interna o Resolución Ministerial con su número oficial.
  - Columna **Docente**: Apellido, nombre y DNI.
  - Columna **Período**: Rango `dd/mm/aaaa – dd/mm/aaaa` y total de días solicitados.
  - Columna **Materia / Cargo**: Materia con badge de carga horaria (`X hs`) y turno.
  - Columna **Licencia Estatutaria**: Código de licencia, artículo reglamentario y badge de haberes (*Con Goce* / *Sin Goce*).

### 4.3. Conmutación de Instrumentos Legales
Junto a cada renglón de planilla se encuentra el botón **Conmutar Instrumento**:
1. Despliegue el panel desplegable.
2. Seleccione entre **Disposición Interna** o **Resolución Ministerial**.
3. Ingrese el número oficial externo (ej. `Res. 1450/2026 M.E.C.C.y T.`).
4. Pulse `Guardar`. El cambio se reflejará al instante tanto en pantalla como en las exportaciones oficiales.

### 4.4. Cambio Directo de Artículo de Licencia
Si un certificado médico requiere modificar el encuadre legal de la licencia (por ejemplo, pasar de *Corto Tratamiento* a *Largo Tratamiento*):
1. En la columna de Licencia Estatutaria, seleccione el nuevo artículo en el menú desplegable.
2. Presione el botón `Guardar`.
3. El motor de licencias recalcula automáticamente la imputación presupuestaria y actualiza la condición de goce de haberes.

### 4.5. Exportación a CSV Optimizada para Microsoft Excel
- **Acceso:** Botón `Exportar CSV` en la cabecera de las planillas.
- **Filtrado:** Respeta el filtro de cuadro activo (exporta solo IL-01, solo IL-02 o el consolidado general).
- **Compatibilidad Garantizada con MS Excel:**
  - El sistema inyecta automáticamente el **Byte Order Mark (BOM) UTF-8** (`\ufeff`) en el encabezado binario del archivo descargado.
  - Esto evita que Excel en sistemas Windows altere las palabras con tildes, eñes o caracteres especiales (evitando el error de *mojibake*), permitiendo abrir el archivo directamente con doble clic sin necesidad de asistentes de importación.

---

## 5. Módulo de Catálogos Institucionales

### 5.1. Hub Central de Catálogos
- **Ruta:** `/personal/catalogos/`
- Permite acceder a los cuatro paneles de configuración académica e institucional con métricas de totales en tiempo real:
  1. Espacios Curriculares (Materias y Talleres).
  2. Carreras Formativas.
  3. Cargos Institucionales de Catálogo.
  4. Tipos de Autorización Normativa.

### 5.2. Espacios Curriculares (Materias y Talleres)
- **Ruta:** `/personal/catalogos/espacios/`
- **Operaciones:**
  - **Búsqueda y Filtrado:** Búsqueda rápida por código de materia, denominación o carrera asociada.
  - **Alta de Espacio Curricular:** Formulario con Código de materia, Nombre oficial, Carrera vinculada, Año de cursado (1°, 2°, 3°, etc.), Comisión (`Única`, `A`, `B`, `C`), Turno y Régimen de dictado (`Anual`, `1° Cuatrimestre`, `2° Cuatrimestre`).
  - **Modificación:** Edición de parámetros curriculares y aulas asignadas.

### 5.3. Carreras Formativas y Tipos de Autorización
- Permite parametrizar las carreras activas (ej. *Tecnicatura Superior en Desarrollo de Software*) y los tipos de autorizaciones habilitantes (disposiciones de planta, horas institucionales, etc.).

### 5.4. Catálogo Normativo de Licencias Estatutarias
- **Ruta:** `/licencias/tipos/`
- Detalla los códigos del régimen de licencias docentes:
  - Código y Artículo (ej. `LIC-340A`, Art. 340-A).
  - Cuadro de imputación ministerial (`IL-01` o `IL-02`).
  - Período máximo en días continuos o discontinuos.
  - Condición de haberes: **Con Goce** o **Sin Goce**.

---

## 6. Resolución de Problemas y Preguntas Frecuentes

### ¿Por qué un docente activo no figura en la grilla de asistencia diaria?
> **Causa:** El docente fue dado de alta en el padrón, pero aún no tiene ningún **Cargo Docente** activo asignado para la fecha seleccionada.  
> **Solución:** Diríjase a `Personal` &rarr; `Docentes`, ubique al profesor y pulse `+ Cargo` para vincularle su materia y turno.

### ¿Se puede cambiar el estado de un turno sin modificar el otro?
> **Sí.** La grilla diaria muestra una fila por cada designación activa. Puede seleccionar *Presente* en la fila del Turno Mañana y *Ausente* o *Licencia* en la del Turno Tarde. Al presionar *Guardar*, ambos estados se almacenarán de forma independiente.

### ¿Cómo se corrigen las fechas de una licencia cargada erróneamente?
> **Solución:** Ingrese a `Planillas Mensuales`, ubique el renglón afectado y rectifíquelo, o utilice la función de `Justificación Diferida` para reasignar el período y tipo de licencia correcto. El sistema mantendrá la marca de auditoría del usuario que realizó la corrección.

### Al abrir el archivo CSV descargado, ¿es necesario configurar el delimitador o la codificación en Excel?
> **No.** El archivo CSV emitido por el Sistema Zunin cuenta con codificación **UTF-8 con BOM** nativa. Al hacer doble clic en el archivo descargado, Microsoft Excel lo reconocerá de forma inmediata y mostrará correctamente todos los caracteres del idioma español sin distorsiones.

---
*Manual de Usuario del Sistema Zunin &bull; Desarrollado para el IESETyFP &bull; 2026*

