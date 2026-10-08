# 🏫 Sistema de Reserva de Salas Académicas

Sistema integral para la gestión y reserva de espacios académicos (laboratorios, auditorios, salas de clases y salas de reuniones), desarrollado con una arquitectura asíncrona de alto rendimiento en **FastAPI**, **PostgreSQL** y un frontend interactivo moderno.

---

## 🚀 Características Principales

- **Concurrencia y Prevención de Solapamientos**: Manejo de concurrencia crítica mediante bloqueos a nivel de fila (*Row-Level Locking* con `SELECT ... FOR UPDATE`) en PostgreSQL para evitar sobre-reservas simultáneas.
- **Seguridad y Control de Acceso (RBAC)**: Autenticación mediante **JWT (JSON Web Tokens)** con algoritmo HS256 y hashing de contraseñas con **Bcrypt**. Roles diferenciados: `ADMIN`, `DOCENTE` y `ESTUDIANTE`.
- **Protección contra Fuerza Bruta y Rate Limiting**: Bloqueo temporal tras intentos fallidos de inicio de sesión y limitación de tasa de solicitudes por minuto.
- **Frontend Moderno**: Interfaz web reactiva con diseño limpio, soporte para temas, gestión de reservas en tiempo real y visualización de disponibilidad.
- **Documentación Interactiva Automática**: Swagger UI (`/docs`) y ReDoc (`/redoc`) generados nativamente por FastAPI.
- **Mapeo Objeto-Relacional Asíncrono**: SQLAlchemy 2.0 (Async) utilizando el driver de alto rendimiento `asyncpg`.

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Descripción |
| :--- | :--- | :--- |
| **Backend** | Python 3.12+ / FastAPI | Framework web asíncrono de alto rendimiento |
| **Servidor ASGI** | Uvicorn | Servidor web asíncrono para Python |
| **Base de Datos** | PostgreSQL 15+ | Motor de base de datos relacional transaccional |
| **ORM / Driver** | SQLAlchemy 2.0 (Async) + `asyncpg` | Mapeo objeto-relacional y driver asíncrono nativo |
| **Validación / DTOs** | Pydantic v2 | Esquemas de datos y tipado estricto |
| **Seguridad** | Python-Jose & Passlib | Tokens JWT y encriptación segura de contraseñas |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+) | Interfaz de usuario dinámica y responsiva |

---

## 📂 Estructura del Proyecto

```text
Reserva_de_salas/
│
├── app/
│   ├── core/                  # Seguridad, tokens JWT, rate limiting y configuración
│   │   ├── config.py          # Configuración tipada mediante pydantic-settings
│   │   ├── rate_limiter.py    # Control de tasa de peticiones y bloqueo por intentos
│   │   └── security.py        # Hashing de passwords y validación de tokens
│   ├── models/                # Modelos ORM (SQLAlchemy)
│   │   └── models.py          # Entidades Usuario, Sala, Reserva y ENUMs
│   ├── schemas/               # Esquemas DTO de validación (Pydantic)
│   │   ├── auth.py
│   │   ├── reserva.py
│   │   ├── sala.py
│   │   └── usuario.py
│   ├── routers/               # Controladores y endpoints REST
│   │   ├── auth.py            # Autenticación y login
│   │   ├── usuarios.py        # Gestión de perfiles y usuarios
│   │   ├── salas.py           # Gestión y consulta de salas
│   │   └── reservas.py        # Creación y cancelación de reservas con lock
│   ├── database.py            # Singleton de conexión asíncrona a PostgreSQL
│   └── main.py                # Punto de entrada de la aplicación FastAPI
│
├── frontend/                  # Interfaz web del cliente
│   ├── index.html             # Estructura del panel de usuario
│   ├── styles.css             # Estilos modernos y responsivos
│   └── app.js                 # Lógica del cliente y consumo de la API REST
│
├── scripts/
│   ├── init_db.sql            # Script de inicialización DDL de base de datos
│   └── seed_data.py           # Script para poblar datos iniciales y usuarios de prueba
│
├── .env.example               # Plantilla de variables de entorno
├── .gitignore                 # Archivos y carpetas excluidos del control de versiones
├── requirements.txt           # Dependencias del proyecto
├── DOCUMENTO_TECNICO.md       # Documento técnico detallado de arquitectura
└── README.md                  # Este documento
```

---

## ⚙️ Instalación y Puesta en Marcha

### 1. Clonar el Repositorio

```bash
git clone https://github.com/jorgesilva902/Sistema_Reserva_de_Salas.git
cd Sistema_Reserva_de_Salas
```

### 2. Crear y Activar Entorno Virtual

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

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

Copia el archivo `.env.example` a `.env`:

```bash
cp .env.example .env
```

Edita `.env` con la configuración de tu PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://postgres:tu_password@localhost:5432/reservas_db
DB_ECHO_SQL=false

SECRET_KEY=clave_secreta_para_firmar_jwt_cambiar_en_produccion
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=5
RATE_LIMIT_PER_MINUTE=60

APP_TITLE=Sistema de Reserva de Salas
APP_VERSION=0.1.0
DEBUG=true
```

### 5. Inicializar la Base de Datos y Datos de Prueba

Crea la base de datos `reservas_db` en PostgreSQL y ejecuta los datos iniciales:

```bash
# Crear tablas y poblar datos semilla (salas y usuarios iniciales)
python scripts/seed_data.py
```

### 6. Ejecutar el Servidor de Desarrollo

```bash
uvicorn app.main:app --reload --port 8000
```

- **Frontend Web**: [http://localhost:8000/](http://localhost:8000/)
- **Documentación Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentación ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔑 Usuarios de Prueba Predefinidos

Al ejecutar el script de semillas (`seed_data.py`), se crean las siguientes credenciales para pruebas:

| Rol | Correo Electrónico | Contraseña por Defecto | Permisos Principales |
| :--- | :--- | :--- | :--- |
| **Administrador** | `admin@inacap.cl` | `Admin123!` | Gestión total de salas, usuarios y reservas |
| **Docente** | `docente@inacap.cl` | `Docente123!` | Reservar laboratorios, auditorios y salas |
| **Estudiante** | `estudiante@inacap.cl` | `Estudiante123!` | Reservar salas de estudio y reuniones |

---

## 📡 Resumen de Endpoints de la API

### Autenticación (`/api/auth`)
- `POST /api/auth/login`: Autentica credenciales y retorna token Bearer JWT.

### Salas (`/api/salas`)
- `GET /api/salas/`: Lista todas las salas con filtros (tipo, capacidad mínima, disponibilidad).
- `GET /api/salas/{id}`: Obtiene detalles de una sala específica.
- `POST /api/salas/`: Crea una nueva sala *(Requiere rol Administrador)*.
- `PUT /api/salas/{id}`: Actualiza una sala existente *(Requiere rol Administrador)*.

### Reservas (`/api/reservas`)
- `GET /api/reservas/`: Lista las reservas del usuario autenticado (o todas si es Administrador).
- `POST /api/reservas/`: Crea una reserva garantizando exclusión horaria mediante Row-Locking.
- `PATCH /api/reservas/{id}/cancelar`: Cancela una reserva vigente.
- `GET /api/reservas/disponibilidad`: Consulta horarios disponibles por sala y fecha.

---

## 📄 Documentación Adicional

Para más información sobre la arquitectura, decisiones de diseño, patrones implementados y diagramas técnicos, consulta el archivo [DOCUMENTO_TECNICO.md](DOCUMENTO_TECNICO.md).

---

## 👨‍💻 Autor

Desarrollado para la Evaluación de Ingeniería de Software / Desarrollo Ágil — INACAP.
Repositorio: [jorgesilva902/Sistema_Reserva_de_Salas](https://github.com/jorgesilva902/Sistema_Reserva_de_Salas)
