"""
routers/usuarios.py
===================
Endpoints CRUD basicos para el recurso Usuario.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.models import RolUsuario, Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioRead

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])

DbDep       = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


@router.post("/", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
async def crear_usuario(payload: UsuarioCreate, db: DbDep) -> UsuarioRead:
    """Registro de nuevo usuario (endpoint publico para el MVP)."""
    # Verificar unicidad de RUT y correo
    existe = await db.execute(
        select(Usuario).where(
            (Usuario.rut == payload.rut) | (Usuario.correo_institucional == payload.correo_institucional)
        )
    )
    if existe.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese RUT o correo institucional.",
        )

    usuario = Usuario(**payload.model_dump())
    db.add(usuario)
    await db.flush()
    await db.refresh(usuario)
    return UsuarioRead.model_validate(usuario)


@router.get("/me", response_model=UsuarioRead)
async def obtener_perfil_propio(current_user: CurrentUser) -> UsuarioRead:
    """Retorna el perfil del usuario autenticado."""
    return UsuarioRead.model_validate(current_user)


@router.get("/{usuario_id}", response_model=UsuarioRead)
async def obtener_usuario(
    usuario_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> UsuarioRead:
    """Obtener usuario por ID. Solo Admin y Encargado pueden ver otros perfiles."""
    if current_user.rol not in (RolUsuario.ADMIN, RolUsuario.ENCARGADO):
        if current_user.id != usuario_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = result.scalar_one_or_none()

    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return UsuarioRead.model_validate(usuario)
