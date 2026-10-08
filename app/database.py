"""
database.py
===========
Gestion de la conexion a PostgreSQL con SQLAlchemy asincrono.

Patron aplicado: SINGLETON
Se garantiza que exista una unica instancia del engine y del
AsyncSessionLocal a lo largo del ciclo de vida de la aplicacion.
Esto evita la creacion de multiples connection pools en memoria,
lo que seria costoso y podria agotar los recursos de la BD.
"""

from __future__ import annotations

import threading
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


# ---------------------------------------------------------------------------
# Clase Singleton: DatabaseManager
# ---------------------------------------------------------------------------
class DatabaseManager:
    """
    Singleton que encapsula el engine asincrono y la fabrica de sesiones.

    Por que Singleton aqui:
    - El connection pool de PostgreSQL es un recurso caro de inicializar.
    - SQLAlchemy ya gestiona internamente el pool; necesitamos exactamente
      una instancia de `engine` que lo administre.
    - Usamos un lock de threading (_lock) para que la instancia sea
      thread-safe incluso si Python cambia a un runtime multi-hilo.
    """

    _instance: "DatabaseManager | None" = None
    _lock: threading.Lock = threading.Lock()

    # Atributos de instancia tipados para el analizador estatico
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    def __new__(cls) -> "DatabaseManager":
        # Doble verificacion (double-checked locking) para no adquirir el
        # lock en cada llamada una vez que la instancia ya existe.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialize()
                    cls._instance = instance
        return cls._instance

    # ------------------------------------------------------------------
    # Inicializacion interna (se llama UNA SOLA VEZ)
    # ------------------------------------------------------------------
    def _initialize(self) -> None:
        """
        Crea el engine asincrono apuntando a PostgreSQL y la fabrica de
        sesiones reutilizable (session_factory / AsyncSessionLocal).

        Parametros del pool:
          pool_size     -> N de conexiones permanentes en el pool.
          max_overflow  -> Conexiones extra permitidas cuando el pool
                          esta lleno (se destruyen al liberar).
          pool_timeout  -> Segundos que un cliente espera por una
                          conexion libre antes de lanzar TimeoutError.
          pool_pre_ping -> Verifica la conexion antes de usarla;
                          descarta conexiones muertas automaticamente.
        """
        self.engine = create_async_engine(
            settings.DATABASE_URL,      # postgresql+asyncpg://...
            echo=settings.DB_ECHO_SQL,  # log SQL en desarrollo
            pool_size=10,
            max_overflow=5,
            pool_timeout=30,
            pool_pre_ping=True,
        )

        # async_sessionmaker es la version asincrona de sessionmaker.
        # expire_on_commit=False evita que los atributos del objeto queden
        # expirados (inaccesibles) despues de hacer commit, lo que es
        # especialmente importante en endpoints async donde no queremos
        # recargar la BD al acceder a campos ya cargados.
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    # ------------------------------------------------------------------
    # Metodos publicos
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Cierra el pool de conexiones de forma ordenada al apagar la app."""
        await self.engine.dispose()


# ---------------------------------------------------------------------------
# Instancia global accesible desde el resto de la aplicacion
# ---------------------------------------------------------------------------
# Al importar este modulo, se crea (o reutiliza) la instancia Singleton.
db_manager = DatabaseManager()


# ---------------------------------------------------------------------------
# Dependencia FastAPI: get_db
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador asincrono usado como dependencia de FastAPI (Depends).

    Uso en un router:
        @router.get("/ejemplo")
        async def ejemplo(db: AsyncSession = Depends(get_db)):
            ...

    Garantias:
    - Abre una nueva sesion por cada request HTTP.
    - Hace commit automatico si todo va bien.
    - Hace rollback si ocurre cualquier excepcion (incluidas las HTTP).
    - Cierra la sesion SIEMPRE en el bloque `finally`.
    """
    async with db_manager.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
