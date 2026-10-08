"""
core/security.py
================
Utilidades de autenticacion JWT y dependencia get_current_user.

Flujo:
1. El cliente hace POST /api/auth/login con rut + password.
2. El servidor verifica credenciales y emite un JWT firmado.
3. En cada request protegido el cliente envia el token en el header:
   Authorization: Bearer <token>
4. La dependencia `get_current_user` valida el token y retorna
   el objeto Usuario, que se inyecta en los endpoints.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

# pyrefly: ignore [missing-import]
from fastapi import Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
# pyrefly: ignore [missing-import]
from sqlalchemy import select
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.models.models import Usuario

# Esquema de seguridad: espera header "Authorization: Bearer <token>"
bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Helpers de JWT
# ---------------------------------------------------------------------------
def crear_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Genera un JWT firmado con HS256."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verificar_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza HTTPException si es invalido."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Dependencia FastAPI: get_current_user
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Usuario:
    """
    Dependencia que extrae y valida el usuario autenticado desde el JWT.

    Uso en un endpoint:
        @router.get("/protegido")
        async def endpoint(user: Usuario = Depends(get_current_user)):
            ...
    """
    payload = verificar_token(credentials.credentials)

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto (sub) definido",
        )

    result = await db.execute(
        select(Usuario).where(Usuario.id == int(user_id), Usuario.activo == True)  # noqa: E712
    )
    usuario = result.scalar_one_or_none()

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )

    return usuario
