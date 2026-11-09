# Sistema Zunin - Gestión de Asistencia y Licencias Docentes (IESETyFP)

Plataforma web integral desarrollada para el **IESETyFP (Instituto de Educación Superior de Educación Técnica y Formación Profesional)**. Su propósito es centralizar, digitalizar y automatizar los procesos de Bedelía: registro diario de asistencia docente, justificación diferida de inasistencias y emisión consolidada de planillas mensuales (cuadros IL-01 e IL-02), reemplazando planillas en hojas de cálculo por un sistema seguro, auditable y escalable.

---

## 🏛️ Arquitectura del Sistema

El proyecto sigue una arquitectura modular y desacoplada en Django 5:

- **`apps.personal`**: Gestión integral del legajo docente, catálogo de cargos, carreras, espacios curriculares y designaciones horarias semanales.
- **`apps.asistencia`**: Registro de partes diarios unificados por docente y cargo, control de Días No Laborables/Feriados y carga masiva.
- **`apps.licencias`**: Catálogo estatutario de licencias docentes, motor de consolidación mensual de horas afectadas y conmutación de instrumentos (Disposición Interna / Resolución Ministerial).
- **`apps.core`**: Módulo transversal con control de accesos basado en roles (RBAC), auditoría automática (`audit_save`), Dashboard gerencial y Panel de Alertas en tiempo real.

---

## 🚀 Puesta en Marcha Rápida (Entorno Local y Demo)

### 1. Clonar el repositorio
```bash
git clone https://github.com/NeumannMaxii/zunin.git
cd zunin
```

### 2. Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Copiar el archivo `.env.example` como `.env`:
```powershell
copy .env.example .env
```
*(Por defecto, si `DB_NAME` está vacío, el sistema utilizará SQLite local `db.sqlite3` para máxima agilidad).*

### 5. Ejecutar migraciones e inicializar base de datos
```bash
python manage.py migrate
python manage.py crear_usuarios
python manage.py poblar_datos --reset --generar-planilla
```

### 6. Iniciar el servidor
```bash
python manage.py runserver
```
Acceder en el navegador a: `http://127.0.0.1:8000/`.

---

## ⚠️ Nota de Ejecución para la Demostración / Defensa

> **IMPORTANTE:** Por practicidad operativa para la defensa final y evaluación ante la cátedra, la demostración interactiva del sistema se ejecuta con **`DEBUG=True`** en el archivo `.env`. Esto garantiza el servicio inmediato de archivos estáticos (Tailwind CSS, iconos PWA, tipografías Inter) y la visualización detallada de cualquier traza sin necesidad de configurar un servidor web inverso adicional en la máquina local.

---

## 🔐 Usuarios y Roles de Demostración

| Usuario | Contraseña | Rol / Grupo | Permisos Principales |
| :--- | :--- | :--- | :--- |
| `admin` | `admin123` | **Superusuario** | Acceso total al panel administrativo de Django y auditoría. |
| `director` | `Director123!` | **Admin_Institucional** | Gestión completa de personal, licencias y bajas lógicas. |
| `zaquino` | `Bedelia123!` | **Bedelia_Operadoras** | Carga de asistencia diaria, justificación diferida y emisión mensual (sin borrado). |
| `mudarte` | `Bedelia123!` | **Bedelia_Operadoras** | Operadora de Bedelía para pruebas de concurrencia. |
| `msosa` | `Consulta123!` | **Consulta_Directiva** | Acceso de solo lectura al dashboard e informes ejecutivos. |

---

## 🌐 Guía de Despliegue en Servidor de Producción (Linux / Ubuntu VPS)

Para el despliegue permanente en servidores Linux, seguir la siguiente arquitectura recomendada:

### 1. Variables de Entorno de Producción (`.env`)
```ini
DEBUG=False
SECRET_KEY=clave_segura_de_produccion_generada_aleatoriamente
ALLOWED_HOSTS=zunin.iesetyfp.edu.ar,127.0.0.1

# Base de Datos MySQL
DB_ENGINE=mysql
DB_NAME=zunin_prod
DB_USER=zunin_user
DB_PASSWORD=PasswordSeguraMySQL123!
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 2. Recolección de Archivos Estáticos
```bash
python manage.py collectstatic --noinput
```

### 3. Servicio Systemd para Gunicorn (`/etc/systemd/system/zunin.service`)
```ini
[Unit]
Description=Gunicorn daemon para Sistema Zunin IESETyFP
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/zunin
ExecStart=/var/www/zunin/.venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/zunin.sock \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```
Activar y arrancar el servicio:
```bash
sudo systemctl start zunin
sudo systemctl enable zunin
```

### 4. Configuración de Servidor Web Inverso Nginx (`/etc/nginx/sites-available/zunin`)
```nginx
server {
    listen 80;
    server_name zunin.iesetyfp.edu.ar;

    location /static/ {
        alias /var/www/zunin/staticfiles/;
    }

    location /media/ {
        alias /var/www/zunin/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/zunin.sock;
    }
}
```
Habilitar el sitio y reiniciar Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/zunin /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. Certificado SSL con Let's Encrypt (HTTPS)
```bash
sudo certbot --nginx -d zunin.iesetyfp.edu.ar
```

---

## 🧪 Pruebas Automatizadas y Calidad de Código

El proyecto cuenta con una cobertura integral de pruebas unitarias, de integración y End-to-End:

```bash
# Ejecutar la suite completa de pruebas (242 tests)
python manage.py test

# Ejecutar el test E2E con simulación temporal (Ticket 14)
python manage.py test apps.core.tests.test_ticket_14_e2e_tiempo

# Verificación de estilo y conformidad PEP8 (Linter)
flake8 .
```

---

## 📚 Documentación Adicional

- [Matriz de Trazabilidad de Requerimientos y Reglas de Negocio](docs/MATRIZ_TRAZABILIDAD.md)
- [Guión Oficial para Demostración y Defensa ante Cátedra](docs/DEMO_SCRIPT.md)
- [Decisiones de Arquitectura y Diseño](docs/DECISIONES_ARQUITECTURA.md)
- [Diagrama Entidad-Relación y Estructura de Datos](docs/DER.md)
- [Manual de Usuario del Sistema](docs/manual_usuario.md)
