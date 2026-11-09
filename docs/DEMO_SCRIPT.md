# Guión Oficial de Demostración y Defensa ante Cátedra

### Proyecto Zunin - Sistema de Gestión de Asistencia y Licencias (IESETyFP)
**Instancia:** Defensa Final de Hackatón / Proyecto Intercátedra  
**Tiempo estimado:** 10 a 15 minutos  

---

## ⚠️ Nota Técnica Inicial Obligatoria

> **NOTA DE EJECUCIÓN:** Para fines de la presente demostración interactiva ante la cátedra, el sistema se ejecuta con **`DEBUG=True`** en el archivo `.env`. Esta configuración permite el servicio inmediato de archivos estáticos (Tailwind CSS, manifiesto PWA e iconos institucionales) y facilita la inspección ágil del entorno local sin requerir un servidor proxy inverso (Nginx) en la máquina de presentación. En servidores productivos, el sistema se despliega bajo `DEBUG=False`, Gunicorn y Nginx con SSL.

---

## 🛠️ Preparación Previa (3 minutos antes de comenzar)

Abre la terminal en la raíz del proyecto y ejecuta la siguiente secuencia de comandos para garantizar un estado limpio, consistente y poblado:

```powershell
# 1. Aplicar migraciones
python manage.py migrate

# 2. Configurar roles y usuarios institucionales
python manage.py crear_usuarios

# 3. Poblar datos demostrativos con un mes completo (Octubre 2026) y planilla emitida
python manage.py poblar_datos --reset --generar-planilla

# 4. Iniciar el servidor local
python manage.py runserver
```

Abre en el navegador: `http://127.0.0.1:8000/`.

---

## 👥 Credenciales Rápidas para la Demostración

| Rol | Usuario | Contraseña | Objetivo en la Demo |
| :--- | :--- | :--- | :--- |
| **Operadora de Bedelía** | `zaquino` | `Bedelia123!` | Mostrar la carga diaria, justificaciones y planillas mensuales. |
| **Directivo / Administrador** | `director` | `Director123!` | Mostrar el panel de alertas, reportes gerenciales y permisos globales. |
| **Superusuario** | `admin` | `admin123` | Acceso a panel de Django para auditoría profunda. |

---

## 🎬 Paso a Paso de la Demostración

### ACTO 1: Introducción y Contexto Institucional (1 minuto)
1. **Qué decir:**
   > *"Buenos días profesora/evaluadores. Presentamos el Sistema Zunin, desarrollado específicamente para el IESETyFP. El problema central que resolvimos fue la gestión de bedelía: históricamente, el control de asistencia y las licencias de más de 100 docentes se registraban en archivos Excel dispersos, lo que provocaba inconsistencias de horas, pérdida de correlatividades anuales y demoras de semanas en la liquidación ministerial. Desarrollamos una plataforma basada en Django 5 y Tailwind CSS que digitaliza de punta a punta este proceso con auditoría estricta y cumplimiento estatutario."*

---

### ACTO 2: Autenticación y Seguridad Basada en Roles (RBAC) (2 minutos)
1. **Acción en pantalla:** Iniciar sesión con la operadora de Bedelía:
   - **Usuario:** `zaquino`
   - **Contraseña:** `Bedelia123!`
2. **Qué mostrar:**
   - La interfaz limpia adaptada a su rol: acceso a *Asistencia Diaria*, *Justificaciones*, *Catálogo de Licencias* y *Planillas*.
   - Entrar al listado de Docentes (`/personal/docentes/`): notar que Bedelía puede ver y editar datos, pero **NO tiene botón de eliminación**.
   - Si se intenta ingresar manualmente por URL a una acción destructiva de borrado, el sistema dispara una pantalla **`403 Forbidden` personalizada** con el diseño institucional.
3. **Qué decir:**
   > *"Implementamos un control de acceso RBAC estricto (RN-05). Bedelía tiene permitido cargar y justificar asistencia, pero las bajas lógicas están restringidas exclusivamente al rol directivo para garantizar la inmutabilidad de los datos históricos."*

---

### ACTO 3: Gestión de Personal, Carreras y Materias (2 minutos)
1. **Acción en pantalla:**
   - Ir a **Cargos Docentes** o al **Hub de Catálogos** (`/personal/catalogos/`).
   - Mostrar la relación entre el **Docente**, la **Carrera** (ej: Tecnicatura en Desarrollo de Software), el **Espacio Curricular** (ej: Programación I) y el **Cargo**.
2. **Qué destacar:**
   - La distribución horaria semanal: cada cargo tiene definidas sus horas por día de la semana (Lunes a Domingo).
3. **Qué decir:**
   > *"El sistema desacopla los docentes de sus designaciones (RN-01). Esto permite calcular al minuto cuántas horas cátedra corresponden liquidar o descontar ante una inasistencia, según el día de la semana en que ocurrió la novedad."*

---

### ACTO 4: Carga de Asistencia Diaria y Feriados (2 minutos)
1. **Acción en pantalla:**
   - Ir a **Asistencia Diaria** (`/asistencia/diaria/`).
   - Seleccionar la fecha del día o una fecha de cursado (ej: un lunes).
   - Mostrar la matriz unificada: cada docente aparece con sus materias asignadas para ese día.
   - Modificar el estado de un docente de `Presente` a `Ausente` (`I`) y guardar.
2. **Probar un día no laborable:**
   - Ir a `/asistencia/feriados/` y mostrar cómo se cargan los asuetos o feriados institucionales (Ticket 4).
   - Mostrar que el motor mensual omite automáticamente esas fechas en la liquidación (RN-02).
3. **Qué decir:**
   > *"El parte diario unificado permite cargar la asistencia en lote de toda la institución en menos de un minuto. Además, el sistema tiene inteligencia de calendario: omite automáticamente fines de semana y feriados registrados."*

---

### ACTO 5: Justificación Diferida y Resoluciones Ministeriales (3 minutos)
1. **Acción en pantalla:**
   - Ir a **Justificación Diferida** (`/licencias/justificacion-diferida/`).
   - Seleccionar el docente que marcamos como ausente.
   - En el campo de **Artículo**, comenzar a tipear `340` o `341`.
   - Mostrar cómo la **API de autocompletado predictivo** (Ticket 10) sugiere la licencia correspondiente y autocompleta el código y el cuadro mensual.
2. **Conmutación de Resolución Ministerial (Ticket 10.3):**
   - En la misma justificación o en la pantalla de planillas, mostrar el conmutador de instrumento legal:
   - Cambiar de **Disposición Interna** a **Resolución Ministerial** e ingresar el número oficial externo: `Res. 1450/2026 M.E.C.C.y T.`.
   - Guardar el cambio y verificar la insignia distintiva en la tabla.
3. **Qué decir:**
   > *"Muchas licencias provienen directamente del Ministerio de Educación de la Provincia y no de la rectoría interna. Incorporamos la capacidad de conmutar entre Disposiciones internas y Resoluciones Ministeriales, preservando el número oficial externo en toda la trazabilidad."*

---

### ACTO 6: Planillas Mensuales (IL-01 / IL-02) y Exportación CSV (2 minutos)
1. **Acción en pantalla:**
   - Ir a **Planillas Mensuales** (`/licencias/planillas/`).
   - Filtrar por Mes: `10` y Año: `2026`.
   - Mostrar los cuadros **IL-01** (Licencias Médicas) e **IL-02** (Inasistencias y Permisos).
   - Mostrar el desglose exacto de horas afectadas y la disposición asignada.
   - Hacer clic en **Exportar CSV**.
   - Abrir el archivo descargado y mostrar las columnas normalizadas y que la Resolución figura con el texto `Resolución 1450/2026 M.E.C.C.y T.`.
2. **Qué decir:**
   > *"La consolidación mensual antes tomaba días de conciliación manual. Aquí el motor agrupa bloques contiguos de licencias (RN-11), calcula las horas exactas y genera la planilla oficial lista para enviar al Ministerio en formato CSV conforme a la normativa vigente."*

---

### ACTO 7: Simulación Temporal y Reinicio Anual de Correlativos (2 minutos)
1. **Qué explicar:**
   > *"Una regla crítica del reglamento institucional es la correlatividad anual (RN-04): las disposiciones van del 001/2026 al final del año, pero al comenzar un nuevo año lectivo en Enero, el contador debe reiniciarse estrictamente a 001/2027 sin colisionar con el histórico ni perder la trazabilidad."*
2. **Demostración en terminal:**
   - Ejecutar la prueba automatizada End-to-End con simulación de tiempo real mediante la librería `freezegun`:
   ```powershell
   python manage.py test apps.core.tests.test_ticket_14_e2e_tiempo
   ```
   - Mostrar el resultado en verde (`OK`) en la terminal:
   > *"Esta prueba E2E viaja en el tiempo de Diciembre 2026 a Enero 2027 simulando el paso del tiempo y valida que el sistema emitió la primera disposición del nuevo año como '001/2027'."*

---

### ACTO 8: Dashboard Gerencial y Alertas Institucionales (1 minuto)
1. **Acción en pantalla:**
   - Cerrar sesión de Bedelía e ingresar con el usuario directivo:
     - **Usuario:** `director`
     - **Contraseña:** `Director123!`
   - Visualizar el **Dashboard Principal** (`/`):
     - Tarjetas de métricas: Total de inasistencias del mes, porcentaje de asistencia promedio.
     - **Panel de Alertas Preventivas (Ticket 12):**
       - Alertas por acumulación de inasistencias críticas (más de 3 ausencias sin justificar).
       - Alertas de licencias próximas a vencer.
       - Detección de docentes activos sin designación horaria vigente.
2. **Qué decir:**
   > *"Para el equipo directivo, el sistema ofrece un panel de control con alertas tempranas para prevenir ausentismos reiterados y garantizar la cobertura de suplencias antes de que se pierdan horas de clase."*

---

### ACTO 9: Cierre y Preguntas (1 minuto)
1. **Resumen final:**
   - **242 pruebas automatizadas** en verde cubriendo el 100% de los requerimientos.
   - **0 errores de flake8** (código limpio, tipado y estricto).
   - Documentación exhaustiva en `/docs`: Matriz de Trazabilidad, Decisiones de Arquitectura y Diagrama DER.
   - Agradecer a la cátedra y quedar a disposición para responder preguntas técnicas o funcionales.

