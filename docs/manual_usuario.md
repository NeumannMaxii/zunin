# Manual de Usuario Oficial - Sistema Zunin
**Sistema Integral de Gestión de Asistencia, Personal Docente, Licencias y Resguardo**  
*Instituto de Educación Superior de Educación Técnica y Formación Profesional (IESETyFP)*  
**Versión del Sistema:** 2.0 (Sprint 3) &bull; **Fecha de Publicación:** Noviembre 2026

---

## Índice General del Manual

1. [Módulo 1: Inicio y Roles](#módulo-1-inicio-y-roles)
   - 1.1. Acceso al Sistema y Seguridad
   - 1.2. Perfiles y Roles de Usuario (RBAC)
   - 1.3. Navegación e Interfaz Institucional
2. [Módulo 2: Planta Docente y Cargos](#módulo-2-planta-docente-y-cargos)
   - 2.1. Padrón Docente Institucional
   - 2.2. Alta Obligatoria de Cargos y Designaciones
   - 2.3. Asignación de Horarios y Distribución por Día
   - 2.4. Régimen de Suplencias y Trazabilidad DP-01
   - 2.5. Cese Puntual de Cargos vs. Baja de Legajo
3. [Módulo 3: Asistencia y Parte Diario](#módulo-3-asistencia-y-parte-diario)
   - 3.1. Modelo Multi-Turno por Cargo (Regla Bedelía / SIE)
   - 3.2. Operatoria de Toma Diaria y Marcas Institucionales
   - 3.3. Vistas del Parte Diario de Bedelía
   - 3.4. Filtros Operativos y Panel de KPIs
   - 3.5. Justificaciones por Lote y Justificación Diferida
   - 3.6. Consulta Histórica y Auditoría
4. [Módulo 4: Régimen de Licencias y Planillas Mensuales](#módulo-4-régimen-de-licencias-y-planillas-mensuales)
   - 4.1. Tipos de Licencia Estatutarios y Situación de Revista
   - 4.2. Números de Disposición Autoincrementales y Correlativos
   - 4.3. Conmutación de Instrumentos Legales
   - 4.4. Emisión de Cuadros IL-01 e IL-02
   - 4.5. Exportación a Excel/CSV Optimizada con BOM UTF-8
5. [Módulo 5: Feriados y Resguardo de Datos](#módulo-5-feriados-y-resguardo-de-datos)
   - 5.1. Feriados y Días No Laborables
   - 5.2. Resguardo Institucional y Descarga de Backups en ZIP
   - 5.3. Preguntas Frecuentes y Resolución de Incidencias

---

## Módulo 1: Inicio y Roles

### 1.1. Acceso al Sistema y Seguridad
El Sistema Zunin es la plataforma oficial del IESETyFP para el registro de asistencia docente, la tramitación de novedades de personal y la emisión de planillas de licencias con destino ministerial.

1. **Ingreso al Sistema:** Ingrese a la dirección web institucional `/login/`.
2. **Credenciales:** Escriba su nombre de usuario asignado y contraseña personal.
3. **Cierre de Sesión Seguro:** Al finalizar su jornada, haga clic en el botón `Cerrar Sesión` ubicado en el extremo superior derecho. Por estándares de seguridad modernos, la desconexión se procesa mediante una solicitud segura con token CSRF para invalidar la sesión activa.
4. **Cambio de Contraseña:** Todo agente debe modificar periódicamente su clave de acceso desde las opciones de usuario para preservar la confidencialidad de los datos institucionales.

### 1.2. Perfiles y Roles de Usuario (RBAC)
El sistema opera bajo un modelo de Control de Acceso Basado en Roles que asigna permisos específicos a cada integrante de la comunidad educativa:

| Rol Institucional | Perfil / Grupo | Competencias y Alcance Operativo |
| :--- | :--- | :--- |
| **Operador de Bedelía** | `Bedelia_Operadoras` | Carga operativa diaria de asistencia en turnos mañana, tarde y noche; registro de justificaciones diferidas y por lote; visualización de calendarios de feriados y consulta de partes diarios. |
| **Secretaría Académica** | `Admin_Institucional` | Administración del padrón docente; alta obligatoria de cargos y horarios; conmutación de instrumentos legales; control y rectificación de planillas mensuales IL-01 / IL-02; catálogos de materias y carreras. |
| **Dirección / Supervisión** | `Consulta_Directiva` | Modo de sólo lectura directivo. Seguimiento del semáforo de ausentismo docente en el Dashboard; consulta avanzada multicriterio; visualización y descarga de planillas oficiales sin permisos de modificación. |
| **Administrador del Sistema** | Superusuario | Control total de la plataforma; administración de cuentas y permisos; resguardo integral y descarga de backups de base de datos en paquetes ZIP con firma de integridad. |

### 1.3. Navegación e Interfaz Institucional
- **Barra de Navegación Superior:** Proporciona acceso directo a los módulos clave: *Dashboard*, *Asistencia*, *Licencias*, *Planillas*, *Personal*, *Catálogos* (para administradores), *Feriados* y *Manual*.
- **Aplicación Web Progresiva (PWA):** Zunin puede instalarse como aplicación de escritorio o en dispositivos móviles mediante el botón institucional `Instalar App`, agilizando el acceso diario en las terminales de Bedelía.
- **Buscador Predictivo con Debounce:** Las pantallas de consulta incorporan filtros de texto en tiempo real que filtran las filas en el navegador al instante y sincronizan la paginación de forma transparente al presionar Enter o pausar la escritura.

---

## Módulo 2: Planta Docente y Cargos

### 2.1. Padrón Docente Institucional
El padrón centraliza la información fidedigna de todos los docentes de la institución:
- **Ruta de Acceso:** Menú `Personal` &rarr; `Docentes` (`/personal/docentes/`).
- **Datos Requeridos:** Apellido, nombres, DNI, CUIL, género, fecha de nacimiento, teléfono y correo electrónico de contacto.
- **Visualización Optimizada:** La grilla presenta el DNI inmediatamente debajo del nombre completo del docente, permitiendo identificar rápidamente al titular sin desplazamientos horizontales.

### 2.2. Alta Obligatoria de Cargos y Designaciones
> **Regla de Negocio Institucional:** Ningún docente puede registrar presentismo ni computar inasistencias sin poseer al menos un cargo o materia activo asignado en la fecha correspondiente.

Para dar de alta una nueva designación docente:
1. Diríjase a `Personal` &rarr; `Docentes` y localice al profesor en la lista.
2. Pulse el botón `+ Cargo` para abrir el formulario de designación vinculado.
3. Seleccione el **Espacio Curricular / Materia** (o el Cargo Institucional si cumple funciones técnico-administrativas).
4. Indique la **Situación de Revista:**
   - *Titular (TIT)*
   - *Interino (INT)*
   - *Suplente (SUP)*
5. Indique el **Turno de Cursado:** *Mañana*, *Tarde* o *Noche*.
6. **Instrumento / Disposición de Designación:** Campo de carácter **estrictamente obligatorio**. Consigne el número oficial de disposición interna o resolución ministerial (ejemplo: `Disp. 145/26` o `Res. 102/20`).
7. **Fecha de Alta:** Campo de carácter **estrictamente obligatorio**. Establece la fecha de inicio efectivo de funciones frente al curso o cargo.

### 2.3. Asignación de Horarios y Distribución por Día
- **Carga Horaria Semanal:** Cantidad total de horas cátedra asignadas a la materia o cargo.
- **Distribución por Día de la Semana:** Se debe especificar la carga horaria correspondiente a cada día hábil (lunes a viernes). Esto permite al motor de asistencia validar con precisión qué docentes deben registrar asistencia en cada turno y jornada.

### 2.4. Régimen de Suplencias y Trazabilidad DP-01
- Si la situación de revista seleccionada es **Suplente**, el sistema exige de forma obligatoria vincular al **Docente Reemplazado**.
- Esto garantiza el cumplimiento del régimen ministerial DP-01, asociando de forma transparente al reemplazante con el docente titular que se encuentra en uso de licencia.

### 2.5. Cese Puntual de Cargos vs. Baja de Legajo
- **Cesar Cargo Individual:** Cuando un docente finaliza el dictado de una materia o suplencia específica pero continúa prestando servicios en otros espacios, ingrese al detalle del cargo y presione `Cesar Cargo`, registrando la fecha efectiva de baja sin afectar sus demás cargos.
- **Baja Definitiva de Legajo:** Si el docente cesa toda actividad en el instituto, se ejecuta la baja lógica desde `Personal` &rarr; `Docentes` &rarr; `Dar de Baja`. Esta acción cesa en cascada todos los cargos activos y preserva de modo inalterable el historial de asistencias y licencias pasadas para auditoría.

---

## Módulo 3: Asistencia y Parte Diario

### 3.1. Modelo Multi-Turno por Cargo (Regla Bedelía / SIE)
En el nivel superior, un mismo docente puede desempeñarse en materias y turnos distintos en una misma fecha. El Sistema Zunin implementa la restricción única `(docente, cargo, fecha)`, permitiendo computar de manera 100% independiente la asistencia en cada turno.

### 3.2. Operatoria de Toma Diaria y Marcas Institucionales
La toma de asistencia se efectúa diariamente desde `Asistencia` &rarr; `Carga Diaria` (`/asistencia/diaria/`). Cada renglón cuenta con las siguientes marcas estandarizadas:

| Marca | Denominación | Significado Operativo | Cómputo e Imputación de Haberes |
| :---: | :--- | :--- | :--- |
| `PR` | **PRESENTE** | El docente asistió a su clase o cargo institucional. | Liquidación normal de haberes. |
| `I` | **INASISTENCIA** | Ausencia sin aviso ni justificación reglamentaria. | Descuento automático de haberes por día/horas. |
| `LIC` | **LICENCIA** | Ausencia amparada en el régimen de licencias estatutarias. | Imputa al Cuadro IL correspondiente (con o sin goce). |
| `P` | **PERMISO** | Justificación reglamentaria o comisión de servicio. | Sin descuento de haberes según encuadre legal. |

### 3.3. Vistas del Parte Diario de Bedelía
Para optimizar el flujo de trabajo en Bedelía, el sistema ofrece dos modalidades de visualización:
- **Vista Planilla Continua (Tipo Excel):** Grilla tabular continua con campos desplegables inmediatos para carga masiva ultra rápida, facilitando la navegación con teclado en terminales administrativas.
- **Vista por Docente (Tarjetas Agrupadas):** Presentación organizada por cada docente donde se muestran en un único bloque todas sus materias y turnos de la fecha seleccionada.
- **Conmutación Inmediata:** Mediante el selector superior de vista, el operador puede alternar entre ambos formatos en tiempo real sin perder los filtros aplicados.

### 3.4. Filtros Operativos y Panel de KPIs
- **Filtro Desplegable de Turno:** Selector limpio para aislar rápidamente la nómina de *Mañana*, *Tarde*, *Noche* o visualizar *Todos los Turnos*.
- **Filtro de Carrera:** Permite acotar el parte diario a una tecnicatura o trayecto formativo en particular.
- **Panel de KPIs Colapsable:** Tarjetas resumen en la parte superior que cuantifican en tiempo real los *Presentes*, *Ausentes*, *Licencias* y *Total del Día*, con botón para colapsar o expandir el panel según el espacio de pantalla disponible.

### 3.5. Justificaciones por Lote y Justificación Diferida
- **Justificaciones por Lote:** Permite seleccionar múltiples cargos con inasistencia y aplicar un encuadre común (por ejemplo, suspensión de actividades o jornada institucional) en un solo clic.
- **Justificación Diferida (Acceso Directo desde Asistencia):** Ubicado en la barra superior de acciones de `/asistencia/` (`asistencia_list.html`). Permite regularizar faltas de días anteriores ante la presentación posterior de certificados médicos o comprobantes reglamentarios, recalculando las marcas de asistencia y actualizando las planillas mensuales en forma retroactiva.

### 3.6. Consulta Histórica y Auditoría
- **Consulta Multicriterio:** Disponible en `/asistencia/consulta/`, permite filtrar por rango de fechas (`Desde` / `Hasta`), docente, materia, estado de presentismo y artículo de licencia.
- **Paginación Estandarizada:** 25 registros por página para garantizar tiempos de respuesta inmediatos en auditorías de ausentismo.

---

## Módulo 4: Régimen de Licencias y Planillas Mensuales

### 4.1. Tipos de Licencia Estatutarios y Situación de Revista
El sistema incorpora el régimen normativo de la Ley 647-E (Estatuto del Docente del Chaco) distinguiendo los topes de días con goce de haberes según la situación de revista:

| Situación de Revista | Artículo Principal | Causal Reglamentaria | Régimen de Haberes y Topes |
| :--- | :--- | :--- | :--- |
| **Docente Titular** | Art. 308 | Afecciones comunes de salud | Hasta 30 días anuales continuos o discontinuos con goce íntegro de haberes. |
| **Docente Interino** | Art. 331-A | Afecciones comunes de salud | Hasta 20 días anuales con goce de haberes, requiriendo antigüedad mínima estatutaria. |
| **Docente Suplente** | Art. 340-A | Afecciones comunes de salud | Hasta 10 días continuos o discontinuos en el ciclo lectivo con goce de haberes. |
| **Todas las Revistas** | Art. 309 / 310 | Largo tratamiento y maternidad | Períodos prolongados sujetos a junta médica y régimen de protección integral. |

### 4.2. Números de Disposición Autoincrementales y Correlativos
Para evitar saltos, huecos o duplicaciones en la documentación institucional, el sistema cuenta con un motor autoincremental de disposiciones:
- Cada nueva licencia o instrumento generado obtiene automáticamente el próximo número correlativo institucional del año en curso (ejemplo: `Disp. 001/2026`, `Disp. 002/2026`).
- El número se asigna en el momento exacto de emisión, garantizando el orden cronológico estricto que exige el Ministerio de Educación.

### 4.3. Conmutación de Instrumentos Legales
Junto a cada renglón de la planilla mensual se encuentra la opción de **Conmutar Instrumento**:
1. Permite alternar entre **Disposición Interna** (emisión del IESETyFP) y **Resolución Ministerial** (del Ministerio de Educación).
2. Posibilita consignar el número de resolución externa una vez homologada la licencia ministerial, actualizando las planillas y exportaciones al instante.

### 4.4. Emisión de Cuadros IL-01 e IL-02
El sistema genera automáticamente los cuadros mensuales consolidados para liquidación de haberes:
- **Cuadro IL-01 (Salud):** Comprende afecciones comunes de corto tratamiento, afecciones de largo tratamiento, accidentes laborales y licencias por maternidad.
- **Cuadro IL-02 (Otras Causales):** Comprende exámenes de estudio, duelo familiar, comisiones oficiales de servicio, razones particulares, gremiales y políticas.
- **Datos Consolidados:** Docente, DNI, período exacto (`Desde` – `Hasta`), total de días de inasistencia, cargo y espacio curricular afectado, turno, artículo estatutario y condición de goce de haberes.

### 4.5. Exportación a Excel/CSV Optimizada con BOM UTF-8
- **Acceso:** Botón `Exportar CSV / Excel` en la cabecera de las planillas mensuales.
- **Compatibilidad Total:** El archivo generado incorpora en su encabezado binario la marca **Byte Order Mark (BOM) UTF-8** (`\ufeff`), garantizando que Microsoft Excel en cualquier versión de Windows reconozca inmediatamente tildes, acentos y la letra ñ sin necesidad de recurrir a asistentes de importación ni conversiones manuales.

---

## Módulo 5: Feriados y Resguardo de Datos

### 5.1. Feriados y Días No Laborables
- **Gestión:** Menú `Feriados` (`/asistencia/feriados/`). Permite registrar feriados nacionales, asuetos provinciales y jornadas institucionales.
- **Resalte Preventivo:** Cuando la fecha seleccionada en el parte diario coincide con un día feriado, la grilla se destaca automáticamente con fondo de advertencia.
- **Exención de Descuentos:** El motor de cálculo mensual excluye automáticamente los días no laborables registrados, evitando que se generen descuentos indebidos en los haberes docentes.
- **Permisos de Eliminación:** Por seguridad institucional, la supresión de feriados registrados está reservada al perfil `Admin_Institucional`.

### 5.2. Resguardo Institucional y Descarga de Backups en ZIP
El sistema Zunin garantiza la protección integral del patrimonio documental de la institución mediante su módulo de copia de seguridad:
- **Acceso:** Restringido a Superusuarios y Administradores Institucionales (`Admin_Institucional`) desde el panel de configuración o mediante el enlace seguro `/backup/exportar/`.
- **Generación en Memoria:** El sistema compila una copia de seguridad en caliente comprimida en formato ZIP, sin interrumpir el funcionamiento de Bedelía.
- **Contenido del Resguardo:**
  - Archivo maestro de base de datos relacional con todos los legajos, asistencias, cargos y licencias históricas.
  - Archivo de verificación `manifest.json` que registra el usuario solicitante, la fecha y hora exacta (ISO 8601), el entorno de ejecución y la **firma criptográfica SHA-256** de la base de datos para certificar su inalterabilidad ante auditorías externas.

### 5.3. Preguntas Frecuentes y Resolución de Incidencias

#### ¿Por qué un docente recién contratado no aparece en el parte diario de hoy?
> **Causa:** El docente fue cargado en el padrón pero aún no cuenta con una designación de **Cargo Docente** activa con fecha igual o anterior a la fecha seleccionada.  
> **Solución:** Ingrese a `Personal` &rarr; `Docentes`, ubique al profesor y presione `+ Cargo`, completando obligatoriamente la fecha de alta, materia, turno y disposición de designación.

#### ¿Cómo justificar una falta ocurrida hace semanas con un certificado médico recién presentado?
> **Solución:** Desde `Asistencia` (`/asistencia/`), presione el botón `Justificación Diferida`, localice la inasistencia injustificada previa por docente o rango de fechas, asigne el tipo de licencia estatutario y confirme la novedad. El sistema recalculará retroactivamente las planillas mensuales.

#### ¿Dónde se descargan las copias de seguridad de la base de datos?
> **Solución:** Los directivos con perfil `Admin_Institucional` disponen del botón de exportación en el menú de mantenimiento para descargar inmediatamente el archivo ZIP con verificación SHA-256.

---
*Manual de Usuario Oficial del Sistema Zunin &bull; Desarrollado para el IESETyFP &bull; 2026*
