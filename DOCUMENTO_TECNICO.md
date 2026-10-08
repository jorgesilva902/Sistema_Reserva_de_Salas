# Documento Técnico de Arquitectura y Funcionamiento
## Sistema de Reserva de Salas Académicas (EVA 3 — INACAP)

---

## 1. Resumen Ejecutivo y Propósito

El **Sistema de Reserva de Salas** es una API REST asíncrona de alto rendimiento diseñada para la gestión académica de espacios físicos (laboratorios, auditorios, salas de clases y salas de reuniones). 

El sistema resuelve la problemática de asignación de espacios, control de aforos, prevención de solapamientos horarios mediante **bloqueos a nivel de fila (*Row-Level Locks*)** en PostgreSQL, y control de accesos basado en roles (**RBAC**) con autenticación mediante **JSON Web Tokens (JWT)**.

---

## 2. Stack Tecnológico

| Capa / Componente | Tecnología | Versión | Rol en el Sistema |
| :--- | :--- | :--- | :--- |
| **Lenguaje** | Python | 3.12+ | Lenguaje base con soporte de concurrencia asíncrona nativa (`async`/`await`). |
| **Framework Web** | FastAPI | 0.115.0 | Framework web asíncrono de alto rendimiento basado en Starlette y Pydantic. |
| **Servidor ASGI** | Uvicorn | 0.30.6 | Servidor HTTP asíncrono para ejecutar la aplicación en entornos locales y producción. |
| **Base de Datos** | PostgreSQL | 18 | Motor relacional transaccional ACID con soporte para tipos ENUM nativos y Row Locks. |
| **ORM / Acceso a Datos**| SQLAlchemy (Async) | 2.0.35 | Mapeo objeto-relacional asíncrono utilizando la API 2.0 moderna (`Mapped`, `mapped_column`). |
| **Driver de Base de Datos**| asyncpg | 0.29.0 | Driver de PostgreSQL en Python ultrarrápido y puramente asíncrono. |
| **Validación y DTOs** | Pydantic / Pydantic Settings | 2.9.2 | Validación estricta de tipos de entrada/salida y lectura tipada de variables de entorno. |
| **Seguridad y Criptografía**| Python-Jose & Passlib (Bcrypt)| 3.3.0 / 1.7.4 | Generación/validación de tokens JWT (HS256) y hashing seguro de contraseñas. |

---

## 3. Arquitectura del Proyecto y Estructura de Directorios

La aplicación implementa una arquitectura modular inspirada en **Clean Architecture** y separación por capas de responsabilidad:

```text
Reserva_de_salas_ver0/
│
├── .env                     # Variables de entorno locales (credenciales BD, secret key JWT)
├── .env.example             # Plantilla de variables de entorno para despliegue
├── .gitignore               # Exclusiones de Git (__pycache__, .env, etc.)
├── requirements.txt         # Especificación exacta de dependencias de Python
├── DOCUMENTO_TECNICO.md     # Documentación técnica completa del sistema
│
├── app/                     # Paquete principal de la aplicación
│   ├── __init__.py          # Inicializador del paquete app
│   ├── main.py              # Punto de entrada de FastAPI, lifespan, middleware CORS y routers
│   ├── database.py          # Gestión de conexión a PostgreSQL (Patrón Singleton con AsyncEngine)
│   │
│   ├── core/                # Núcleo transversal de configuración y seguridad
│   │   ├── __init__.py
│   │   ├── config.py        # Configuración tipada vía pydantic-settings (.env)
│   │   └── security.py      # Generación/verificación JWT y dependencia get_current_user
│   │
│   ├── models/              # Modelos ORM relacionales (Tablas de SQLAlchemy)
│   │   ├── __init__.py
│   │   └── models.py        # Clases Base, Usuario, Sala, Reserva y ENUMs PostgreSQL
│   │
│   ├── schemas/             # Esquemas de validación y DTOs (Pydantic)
│   │   ├── __init__.py
│   │   ├── usuario.py       # UsuarioBase, UsuarioCreate, UsuarioRead
│   │   ├── sala.py          # SalaBase, SalaCreate, SalaRead
│   │   └── reserva.py       # ReservaBase, ReservaCreate, ReservaRead, ReservaCancelUpdate
│   │
│   └── routers/             # Capa de controladores / Endpoints de la API REST
│       ├── __init__.py
│       ├── auth.py          # POST /api/auth/login (Emisión de credenciales JWT)
│       ├── usuarios.py      # POST /api/usuarios/, GET /api/usuarios/me, GET /api/usuarios/{id}
│       ├── salas.py         # GET /api/salas/, POST /api/salas/
│       └── reservas.py      # POST /api/reservas/ (concurrencia crítica), GET, PATCH (asistir/cancelar)
│
└── scripts/                 # Scripts de utilidad y mantenimiento
    └── init_db.sql          # Script SQL para creación inicial de la base de datos
```

---

## 4. Patrones de Diseño Implementados

### 4.1. Patrón Singleton (`DatabaseManager` en `app/database.py`)
- **Problema**: Crear múltiples *connection pools* a la base de datos en una aplicación web satura las conexiones de PostgreSQL y degrada severamente el rendimiento.
- **Solución**: Se implementó una clase `DatabaseManager` con *Double-Checked Locking* y `threading.Lock` para asegurar que exista **una única instancia del motor asíncrono (`AsyncEngine`)** y de la fábrica de sesiones (`async_sessionmaker`) durante todo el ciclo de vida del servidor.

### 4.2. Patrón DTO (Data Transfer Object) con Pydantic (`app/schemas/`)
- Desacoplamiento entre la estructura interna de las tablas de la base de datos y la interfaz pública expuesta a los clientes HTTP.
- Se crean variantes especializadas para cada operación:
  - `*Create`: Valida los datos requeridos para crear la entidad (rechaza campos de sólo lectura).
  - `*Read`: Serializa la respuesta hacia el cliente, ocultando datos sensibles.
  - `*Update`: Permite modificaciones parciales y controladas.

### 4.3. Patrón Dependency Injection (Inyección de Dependencias de FastAPI)
- Desacoplamiento de componentes mediante `Depends`:
  - `db: AsyncSession = Depends(get_db)`: Provee una sesión de base de datos aislada por solicitud HTTP.
  - `current_user: Usuario = Depends(get_current_user)`: Valida el token JWT y extrae al usuario autenticado antes de ingresar a la función del controlador.

### 4.4. Patrón Unit of Work Transaccional (`get_db`)
- Garantiza que cada solicitud HTTP se ejecute dentro de un contexto transaccional atómico:
  - Si la operación concluye con éxito, se ejecuta `commit()` automáticamente.
  - Si ocurre cualquier error o excepción HTTP, se ejecuta `rollback()` liberando bloqueos.
  - La sesión siempre se cierra en el bloque `finally`.

---

## 5. Mecanismo de Control de Concurrencia (Prevención de Solapamientos)

### El Problema de la Condición de Carrera (*Race Condition*)
En sistemas de reserva bajo arquitectura MVCC (*Multi-Version Concurrency Control*) como PostgreSQL, dos usuarios que intentan reservar la misma sala en el mismo bloque horario simultáneamente podrían leer la sala como "libre" antes de que el otro guarde los cambios, provocando una **doble reserva (*double booking*)**.

### La Solución Implementada: *Row-Level Locking* (`SELECT ... FOR UPDATE`)
En el archivo `app/routers/reservas.py`, el método `crear_reserva` implementa el siguiente protocolo:

1. **Adquisición del Bloqueo Exclusivo**:
   ```python
   reservas_activas_stmt = (
       select(Reserva)
       .where(
           and_(
               Reserva.id_sala == payload.id_sala,
               Reserva.fecha == payload.fecha,
               Reserva.estado == EstadoReserva.ACTIVA,
           )
       )
       .with_for_update()  # <-- Bloqueo a nivel de fila en PostgreSQL
       .execution_options(populate_existing=True)
   )
   ```
2. **Serialización**:
   - La primera transacción que evalúa la disponibilidad para la combinación `id_sala` + `fecha` bloquea las filas de reservas activas.
   - Cualquier petición concurrente queda en espera (*suspended*) hasta que la primera transacción confirme (`commit`) o cancele (`rollback`).
3. **Algoritmo de Intersección de Intervalos Semiabiertos**:
   Dos intervalos de tiempo $[A_{\text{inicio}}, A_{\text{fin}})$ y $[B_{\text{inicio}}, B_{\text{fin}})$ colisionan si y solo si:
   $$\text{Inicio}_A < \text{Fin}_B \quad \land \quad \text{Inicio}_B < \text{Fin}_A$$
4. **Resolución Determinista**:
   - Si se detecta solapamiento: Se retorna inmediatamente `HTTP 409 Conflict` y la transacción se aborta (`rollback`), liberando el cerrojo.
   - Si el espacio está disponible: Se inserta la nueva reserva y al hacer `commit` se libera el cerrojo, permitiendo que la siguiente petición evalúe el nuevo estado actualizado.

---

## 6. Modelo de Datos y Esquema Relacional

```mermaid
erDiagram
    USUARIOS ||--o{ RESERVAS : "realiza"
    SALAS ||--o{ RESERVAS : "es reservada en"

    USUARIOS {
        bigint id PK
        varchar rut UK "RUT único chileno"
        varchar nombre
        varchar correo_institucional UK "Login único"
        rol_usuario_enum rol "ALUMNO, DOCENTE, ADMIN, ENCARGADO"
        smallint contador_cancelaciones
        boolean activo
        timestamptz creado_en
    }

    SALAS {
        int id PK
        varchar acronimo "Ej. LAB, AUD, SALA"
        varchar numero "Ej. 01, A, 302"
        smallint capacidad "Aforo máximo"
        boolean estado_habilitacion "Habilitada / Fuera de servicio"
    }

    RESERVAS {
        bigint id PK
        bigint id_usuario FK
        int id_sala FK
        date fecha "Fecha de la reserva"
        varchar hora_inicio "Formato HH:MM"
        smallint bloque_minutos "Duración (ej. 45 min)"
        estado_reserva_enum estado "ACTIVA, CANCELADA, ASISTIDA"
        timestamptz creado_en
        timestamptz actualizado_en
    }
```

### Enumeraciones de Dominio (PostgreSQL ENUMs)
- **`rol_usuario_enum`**: `'ALUMNO'`, `'DOCENTE'`, `'ADMIN'`, `'ENCARGADO'`
- **`estado_reserva_enum`**: `'ACTIVA'`, `'CANCELADA'`, `'ASISTIDA'`

### Restricciones e Índices Clave
- `uq_sala_acronimo_numero`: Restricción UNIQUE compuesta sobre `(acronimo, numero)` para evitar salas duplicadas (ej. no pueden existir dos salas "LAB-01").
- `ix_usuarios_rut` y `ix_usuarios_correo_institucional`: Índices únicos para búsquedas y logins de complejidad $O(1)$.
- `ix_reservas_id_sala` e `ix_reservas_id_usuario`: Índices sobre llaves foráneas para optimizar consultas y bloqueos transaccionales.

---

## 7. Modelo de Seguridad y Control de Acceso (RBAC)

### Matriz de Permisos por Rol

| Recurso / Acción | ALUMNO | DOCENTE | ENCARGADO | ADMIN |
| :--- | :---: | :---: | :---: | :---: |
| **Registrarse (`POST /api/usuarios/`)** | Sí | Sí | Sí | Sí |
| **Ver perfil propio (`GET /api/usuarios/me`)** | Sí | Sí | Sí | Sí |
| **Ver otros usuarios (`GET /api/usuarios/{id}`)** | No | No | Sí | Sí |
| **Listar salas disponibles (`GET /api/salas/`)** | Sí | Sí | Sí | Sí |
| **Crear nuevas salas (`POST /api/salas/`)** | No | No | Sí | Sí |
| **Crear reserva (`POST /api/reservas/`)** | Sí | Sí | Sí | Sí |
| **Listar reservas** | Solo propias | Solo propias | Todas | Todas |
| **Cancelar reserva propia** | Sí (suma sanción)| Sí (suma sanción)| Sí | Sí |
| **Marcar asistencia / Check-in** | No | No | Sí | Sí |

### 7.2. Mitigación de Denegación de Servicio (DoS) y Rate Limiting
- **Protección global anti-DoS a nivel de aplicación**: Implementación de `RateLimitMiddleware` en [`app/core/rate_limiter.py`](file:///c:/Users/Usuario/OneDrive%20-%20INACAP/Desarrollo_Agil/Ingiener%C3%ADa_Software/EVA%203/Reserva_de_salas_ver0/app/core/rate_limiter.py) con algoritmo de ventana deslizante (*Sliding Window*). Restringe el tráfico entrante sobre todos los endpoints de la API (`/api/*`) a un máximo configurable (por defecto 60 peticiones/minuto) por dirección de origen (IP) y usuario autenticado.
- **Protección contra fuerza bruta (OWASP A07)**: Control específico en `POST /api/auth/login` con bloqueo temporal de 5 minutos al acumular 5 intentos fallidos consecutivos.
- **Respuestas estándar**: En caso de rebasar las cuotas establecidas, la API retorna inmediatamente `HTTP 429 Too Many Requests` acompañado de las cabeceras `Retry-After`, `X-RateLimit-Limit` y `X-RateLimit-Remaining`.

---

## 8. Catálogo Completo de Endpoints

### 8.1. Sistema y Monitoreo
- `GET /`: Redirección automática a la documentación Swagger UI (`/docs`).
- `GET /health`: Chequeo de estado y versión del sistema (`{"status": "ok", "version": "0.1.0"}`).
- `GET /docs`: Interfaz interactiva Swagger para pruebas de endpoints en vivo.
- `GET /redoc`: Documentación técnica formal de la API.

### 8.2. Autenticación (`/api/auth`)
- `POST /api/auth/login`: Recibe credenciales en formato OAuth2 (`username` = correo, `password`) y retorna el token JWT Bearer. Implementa protección contra fuerza bruta (OWASP A07) con bloqueo temporal tras intentos fallidos consecutivos (`HTTP 429 Too Many Requests`).

### 8.3. Usuarios (`/api/usuarios`)
- `POST /api/usuarios/`: Registro de un nuevo usuario en el sistema.
- `GET /api/usuarios/me`: Perfil del usuario actualmente autenticado (obtenido desde el token JWT).
- `GET /api/usuarios/{usuario_id}`: Consulta de usuario por ID (restringido a Admin y Encargado).

### 8.4. Salas (`/api/salas`)
- `GET /api/salas/`: Lista las salas del recinto, permitiendo filtrar sólo aquellas habilitadas (`solo_habilitadas=true`).
- `POST /api/salas/`: Registro de una nueva sala física con su aforo y código (restringido a Admin y Encargado).

### 8.5. Reservas (`/api/reservas`)
- `POST /api/reservas/`: Crea una nueva reserva para una sala, fecha y hora. Protegido con `SELECT ... FOR UPDATE` para evitar solapamientos concurrentes.
- `GET /api/reservas/`: Lista las reservas con filtros opcionales (`sala_id`, `fecha`, `estado`, `limit`, `offset`).
- `GET /api/reservas/{reserva_id}`: Detalle de una reserva en particular.
- `PATCH /api/reservas/{reserva_id}`: Permite cancelar una reserva (incrementando el contador de cancelaciones del usuario si corresponde) o marcarla como `ASISTIDA` (check-in de asistencia).

---

## 9. Instrucciones de Despliegue y Uso Local

### 1. Prerrequisitos
- Python 3.12+
- PostgreSQL 18 instalado y en ejecución

### 2. Configuración del entorno
Configurar el archivo `.env` en la raíz del proyecto:
```env
DATABASE_URL=postgresql+asyncpg://postgres:TU_CONTRASEÑA@localhost:5432/reservas_db
DB_ECHO_SQL=true
SECRET_KEY=clave_secreta_segura_para_firmar_jwt
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
APP_TITLE=Sistema de Reserva de Salas
APP_VERSION=0.1.0
DEBUG=true
```

### 3. Ejecución del Servidor
```powershell
uvicorn app.main:app --reload
```

### 4. Acceso al Sistema
- Interfaz interactiva de pruebas: **http://127.0.0.1:8000/docs**
- Verificación del servicio: **http://127.0.0.1:8000/health**
