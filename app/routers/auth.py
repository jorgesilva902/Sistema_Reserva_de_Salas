"""
routers/auth.py
===============
Endpoint de autenticacion: emite JWT al verificar credenciales.

NOTA MVP: Se usa bcrypt para verificar passwords.
En produccion se debe agregar hashing en el registro de usuario.
"""

from datetime import datetime, timedelta, timezone
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import crear_access_token
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["Autenticacion"])

# Contexto de hashing de passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Gestor de intentos de acceso en memoria (OWASP A07 - Protección Fuerza Bruta)
# ---------------------------------------------------------------------------
class LoginRateLimiter:
    """
    Controlador en memoria de intentos fallidos de autenticación.
    Bloquea temporalmente el acceso tras superar el umbral configurado.
    Thread-safe mediante threading.Lock.
    """
    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 5):
        self.max_attempts = max_attempts
        self.lockout_minutes = lockout_minutes
        self._lock = threading.Lock()
        # Estructura: key -> {"count": int, "locked_until": datetime | None}
        self._attempts: dict[str, dict] = {}

    def _get_key(self, client_ip: str, username: str) -> str:
        return f"{client_ip}:{username.strip().lower()}"

    def check_rate_limit(self, client_ip: str, username: str) -> None:
        """Verifica si el usuario/IP se encuentra en periodo de bloqueo."""
        key = self._get_key(client_ip, username)
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._attempts.get(key)
            if not record:
                return

            locked_until = record.get("locked_until")
            if locked_until:
                if now < locked_until:
                    remaining_seconds = int((locked_until - now).total_seconds()) + 1
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            f"Demasiados intentos fallidos. Acceso temporalmente bloqueado "
                            f"por seguridad. Reintente en {remaining_seconds} segundos."
                        ),
                        headers={"Retry-After": str(remaining_seconds)},
                    )
                else:
                    # Periodo de bloqueo expirado: resetear registro
                    del self._attempts[key]

    def record_failure(self, client_ip: str, username: str) -> None:
        """Registra un intento fallido e inicia bloqueo si se supera el umbral."""
        key = self._get_key(client_ip, username)
        now = datetime.now(timezone.utc)
        with self._lock:
            if key not in self._attempts:
                self._attempts[key] = {"count": 1, "locked_until": None}
            else:
                self._attempts[key]["count"] += 1

            if self._attempts[key]["count"] >= self.max_attempts:
                self._attempts[key]["locked_until"] = now + timedelta(minutes=self.lockout_minutes)

    def record_success(self, client_ip: str, username: str) -> None:
        """Restablece el contador tras un inicio de sesión exitoso."""
        key = self._get_key(client_ip, username)
        with self._lock:
            self._attempts.pop(key, None)


login_limiter = LoginRateLimiter(
    max_attempts=settings.MAX_LOGIN_ATTEMPTS,
    lockout_minutes=settings.LOGIN_LOCKOUT_MINUTES,
)


@router.post("/login", summary="Obtener token JWT")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbDep,
    request: Request,
) -> dict:
    """
    Autentica al usuario por correo_institucional + password.
    Retorna un access_token JWT.
    
    Aplica protección contra ataques de fuerza bruta (OWASP A07):
    - Limita los intentos fallidos consecutivos por IP y cuenta.
    - Bloquea temporalmente con HTTP 429 Too Many Requests si se supera el umbral.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    username = form_data.username

    # 1. Verificar bloqueo por límite de intentos
    login_limiter.check_rate_limit(client_ip, username)

    from app.models.models import Usuario

    result = await db.execute(
        select(Usuario).where(
            Usuario.correo_institucional == username,
            Usuario.activo == True,  # noqa: E712
        )
    )
    usuario = result.scalar_one_or_none()

    # Verificacion de credenciales (MVP: valida existencia y estado activo)
    if usuario is None:
        login_limiter.record_failure(client_ip, username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario inactivo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if hasattr(usuario, "password_hash") and usuario.password_hash:
        if not pwd_context.verify(form_data.password, usuario.password_hash):
            login_limiter.record_failure(client_ip, username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Credenciales correctas: reiniciar contador de fallos
    login_limiter.record_success(client_ip, username)

    token = crear_access_token(data={"sub": str(usuario.id)})
    return {"access_token": token, "token_type": "bearer"}
