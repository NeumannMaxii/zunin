# Sistema de Gestión de Asistencia y Licencias Docentes - IESETyFP

Sistema web institucional desarrollado para el **IESETyFP (Instituto de Educación Superior de Educación Técnica y Formación Profesional)**. Su objetivo principal es modernizar, centralizar y automatizar los procesos de bedelía vinculados al registro diario de asistencia docente y la gestión integral de licencias, reemplazando las planillas administrativas en hojas de cálculo (Excel) con un sistema robusto, auditable y escalable.

---

## 🚀 Tecnologías Principales

- **Lenguaje:** Python 3.11+
- **Framework Web:** Django 5.x
- **Bases de Datos:** MySQL (soporte vía `PyMySQL` o `mysqlclient`) con fallback inteligente a SQLite para desarrollo local ágil.
- **Frontend:** Django Templates estilizados con Tailwind CSS.
- **Procesamiento de Datos:** Pandas & OpenPyXL (para importación/exportación de planillas históricas).
- **Control de Calidad & CI:** Flake8, Black, pruebas unitarias con `django.test` y GitHub Actions.

---

## 🛠️ Guía de Instalación y Puesta en Marcha Local

Sigue estos pasos para configurar y ejecutar el entorno de desarrollo en tu máquina:

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd Zunin
```

### 2. Crear y Activar el Entorno Virtual

En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

En Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
*(Si encuentras restricciones de ejecución en PowerShell, ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copia el archivo de ejemplo para generar tu archivo `.env`:

En Linux / macOS:
```bash
cp .env.example .env
```
En Windows:
```powershell
copy .env.example .env
```

> **Nota sobre Base de Datos:**
> Por defecto, si dejas `DB_NAME=` vacío en el archivo `.env`, el sistema usará automáticamente **SQLite** (`db.sqlite3`), permitiendo comenzar a trabajar inmediatamente sin configurar un servidor MySQL local. Si deseas conectar a MySQL, completa los valores de `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`.

### 5. Ejecutar Migraciones y Crear Superusuario
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Iniciar el Servidor de Desarrollo
```bash
python manage.py runserver
```

El sistema estará disponible en `http://127.0.0.1:8000/`.

---

## 🧪 Pruebas y Validación de Código

Para verificar que la configuración sea correcta y ejecutar los tests:
```bash
python manage.py check
python manage.py test
```

Para análisis de formato y linting:
```bash
flake8
black --check .
```

---

## 🌿 Flujo de Trabajo Git Flow

Para garantizar la estabilidad del proyecto y el trabajo en equipo, se establecen las siguientes reglas obligatorias:

1. **Ramas Principales:**
   - `main`: Contiene únicamente código estable y listo para producción. **Queda terminantemente prohibido hacer commits directos a `main`**.
   - `develop` (o branch base de integración): Rama de integración para las nuevas funcionalidades.

2. **Convenciones de Nombres para Ramas de Trabajo:**
   - Nuevas funcionalidades: `feature/nombre-de-la-funcionalidad` (ej. `feature/carga-asistencia-diaria`).
   - Corrección de errores: `bugfix/descripcion-del-error` (ej. `bugfix/calculo-dias-licencia`).
   - Correcciones críticas en producción: `hotfix/descripcion-urgente`.

3. **Ciclo de Contribución:**
   - Crear una nueva rama desde `main` (o `develop` según la etapa):
     ```bash
     git checkout -b feature/nueva-funcionalidad
     ```
   - Realizar commits atómicos y descriptivos.
   - Subir la rama y abrir un **Pull Request (PR)** hacia la rama correspondiente.
   - Todo PR debe pasar la integración continua (CI de GitHub Actions) y contar con la revisión de al menos un miembro del equipo antes del merge.

---

## 📌 Flujo de Pull Requests y Entregas

Para mantener la trazabilidad, control de calidad y visibilidad en las entregas, **todo Pull Request (PR) debe utilizar la plantilla oficial (`.github/pull_request_template.md`) e incluir obligatoriamente**:

1. **Descripción concisa de los cambios:** Explicación técnica y funcional de la solución implementada.
2. **Enlace al Ticket de Trello asociado:** Vínculo o nombre de la tarjeta en el tablero del IESETyFP.
3. **Evidencia visual (Obligatorio):** Captura de pantalla o GIF demostrativo arrastrado en el cuerpo del PR que valide el funcionamiento de la interfaz (Tailwind CSS) o de los procesos en terminal.
4. **Checklist de verificación:** Confirmación de que las pruebas (`python manage.py test`) pasaron en verde y no se versionaron credenciales ni archivos `.env`.

