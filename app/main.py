"""
main.py
=======
Punto de entrada de la aplicacion FastAPI.

Responsabilidades:
- Instanciar la app con metadatos completos.
- Registrar todos los routers.
- Configurar eventos de startup/shutdown (crear tablas en dev, cerrar pool).
- Configurar CORS para desarrollo local.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.database import db_manager
from app.models.models import Base
from app.routers.auth import router as auth_router
from app.routers.usuarios import router as usuarios_router
from app.routers.salas import router as salas_router
from app.routers.reservas import router as reservas_router


# ---------------------------------------------------------------------------
# Lifespan: reemplaza los eventos on_event("startup"/"shutdown") deprecados
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Codigo ejecutado al inicio y al cierre de la aplicacion.

    startup:
    - En entornos de desarrollo, crea las tablas si no existen.
    - En produccion usa Alembic para migraciones (no Base.create_all).

    shutdown:
    - Cierra el connection pool del Singleton DatabaseManager.
    """
    # --- STARTUP ---
    import logging
    logger = logging.getLogger("app.startup")

    if settings.DEBUG:
        # Solo en DEBUG: sincronizar esquema (util para pruebas rapidas)
        try:
            async with db_manager.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Tablas sincronizadas correctamente con la base de datos.")
        except Exception as exc:
            logger.warning(
                f"No se pudo conectar a PostgreSQL durante el startup: {exc}\n"
                "El servidor arrancara de todas formas. "
                "Los endpoints que requieran BD retornaran error 500 hasta que la BD este disponible."
            )

    yield  # La aplicacion corre entre yield y el siguiente bloque

    # --- SHUTDOWN ---
    await db_manager.close()


# ---------------------------------------------------------------------------
# Instancia principal de FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=(
        "API REST para la gestion academica de reservas de salas. "
        "Implementa control de concurrencia con PostgreSQL row-level locks."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middlewares: Mitigación DoS y CORS
# ---------------------------------------------------------------------------
# Rate limiting global para endpoints /api/* (Protección DoS a nivel de aplicación)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
)

# CORS (permite pruebas locales desde cualquier puerto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Registro de routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(salas_router)
app.include_router(reservas_router)


# ---------------------------------------------------------------------------
# Frontend SPA (Servicio de archivos estáticos)
# ---------------------------------------------------------------------------
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

frontend_path = Path(__file__).resolve().parent.parent / "frontend"

if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        """Sirve la aplicacion SPA institucional."""
        return FileResponse(str(frontend_path / "index.html"))

    @app.get("/styles.css", include_in_schema=False)
    async def serve_styles() -> FileResponse:
        return FileResponse(str(frontend_path / "styles.css"))

    @app.get("/app.js", include_in_schema=False)
    async def serve_app_js() -> FileResponse:
        return FileResponse(str(frontend_path / "app.js"))
else:
    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Redirige automaticamente a la documentacion Swagger."""
        return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Sistema"])
async def health_check() -> dict:
    """Verifica que la API esta en linea."""
    return {"status": "ok", "version": settings.APP_VERSION}
