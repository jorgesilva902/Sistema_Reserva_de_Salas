"""
routers/salas.py
================
Endpoints CRUD para el recurso Sala y catálogo de Tipos de Sala.

Endpoints de Salas:
  GET    /api/salas/           -> listar salas
  POST   /api/salas/           -> crear sala  [Admin/Encargado]
  GET    /api/salas/{sala_id}  -> detalle de sala
  PUT    /api/salas/{sala_id}  -> editar sala [Admin/Encargado]
  DELETE /api/salas/{sala_id}  -> eliminar sala (soft-delete) [Admin]

Endpoints de Tipos de Sala:
  GET    /api/salas/tipos/           -> listar tipos
  POST   /api/salas/tipos/           -> crear tipo [Admin]
  DELETE /api/salas/tipos/{acronimo} -> eliminar tipo [Admin]
"""

from typing import Annotated

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.models import RolUsuario, Sala, Usuario
from app.schemas.sala import SalaCreate, SalaRead, SalaUpdate, TipoSalaCreate, TipoSalaRead

router = APIRouter(prefix="/api/salas", tags=["Salas"])

DbDep       = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]

# ---------------------------------------------------------------------------
# Catálogo de Tipos de Sala en memoria (persiste mientras corra el servidor)
# En producción se migraría a una tabla BD.
# ---------------------------------------------------------------------------
_tipos_sala: dict[str, str] = {
    "LAB":  "Laboratorio de Computación / Práctica",
    "AUD":  "Auditorio Institucional",
    "SALA": "Sala de Clases Teórica",
    "CONF": "Sala de Conferencias / Reuniones",
}


# ===========================================================================
# TIPOS DE SALA
# ===========================================================================

@router.get("/tipos/", response_model=list[TipoSalaRead], tags=["Tipos de Sala"])
async def listar_tipos_sala(current_user: CurrentUser) -> list[TipoSalaRead]:
    """Lista todos los tipos de sala disponibles en el catálogo."""
    return [TipoSalaRead(acronimo=k, descripcion=v) for k, v in _tipos_sala.items()]


@router.post(
    "/tipos/",
    response_model=TipoSalaRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Tipos de Sala"],
)
async def crear_tipo_sala(
    payload: TipoSalaCreate,
    current_user: CurrentUser,
) -> TipoSalaRead:
    """Crea un nuevo tipo de sala. Solo Admin puede hacerlo."""
    if current_user.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Administrador puede gestionar tipos de sala.")

    acronimo = payload.acronimo.upper()
    if acronimo in _tipos_sala:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El tipo de sala '{acronimo}' ya existe.",
        )

    _tipos_sala[acronimo] = payload.descripcion
    return TipoSalaRead(acronimo=acronimo, descripcion=payload.descripcion)


@router.delete(
    "/tipos/{acronimo}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tipos de Sala"],
)
async def eliminar_tipo_sala(
    acronimo: Annotated[str, Path(min_length=1, max_length=10)],
    current_user: CurrentUser,
) -> None:
    """Elimina un tipo de sala del catálogo. Solo Admin."""
    if current_user.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Administrador puede gestionar tipos de sala.")

    acronimo_upper = acronimo.upper()
    if acronimo_upper not in _tipos_sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tipo '{acronimo_upper}' no encontrado.")

    del _tipos_sala[acronimo_upper]


# ===========================================================================
# SALAS — CRUD COMPLETO
# ===========================================================================

@router.get("/", response_model=list[SalaRead])
async def listar_salas(
    db: DbDep,
    current_user: CurrentUser,
    solo_habilitadas: bool = True,
) -> list[SalaRead]:
    """Lista todas las salas, opcionalmente filtrando solo las habilitadas."""
    stmt = select(Sala)
    if solo_habilitadas:
        stmt = stmt.where(Sala.estado_habilitacion == True)  # noqa: E712
    result = await db.execute(stmt.order_by(Sala.acronimo, Sala.numero))
    return [SalaRead.model_validate(s) for s in result.scalars().all()]


@router.post("/", response_model=SalaRead, status_code=status.HTTP_201_CREATED)
async def crear_sala(
    payload: SalaCreate,
    db: DbDep,
    current_user: CurrentUser,
) -> SalaRead:
    """Crea una sala nueva. Solo Admin y Encargado pueden hacerlo."""
    if current_user.rol not in (RolUsuario.ADMIN, RolUsuario.ENCARGADO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")

    existe = await db.execute(
        select(Sala).where(Sala.acronimo == payload.acronimo, Sala.numero == payload.numero)
    )
    if existe.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La sala {payload.acronimo}-{payload.numero} ya existe.",
        )

    sala = Sala(**payload.model_dump())
    db.add(sala)
    await db.flush()
    await db.refresh(sala)
    return SalaRead.model_validate(sala)


@router.get("/{sala_id}", response_model=SalaRead)
async def obtener_sala(
    sala_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> SalaRead:
    """Obtiene el detalle de una sala por su ID."""
    result = await db.execute(select(Sala).where(Sala.id == sala_id))
    sala = result.scalar_one_or_none()
    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    return SalaRead.model_validate(sala)


@router.put("/{sala_id}", response_model=SalaRead)
async def actualizar_sala(
    sala_id: Annotated[int, Path(gt=0)],
    payload: SalaUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> SalaRead:
    """Actualiza los datos de una sala. Solo Admin y Encargado."""
    if current_user.rol not in (RolUsuario.ADMIN, RolUsuario.ENCARGADO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")

    result = await db.execute(select(Sala).where(Sala.id == sala_id).with_for_update())
    sala = result.scalar_one_or_none()

    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    # Verificar unicidad si se cambian acronimo o número
    datos = payload.model_dump(exclude_none=True)
    nuevo_acronimo = datos.get("acronimo", sala.acronimo)
    nuevo_numero   = datos.get("numero",   sala.numero)

    if nuevo_acronimo != sala.acronimo or nuevo_numero != sala.numero:
        conflicto = await db.execute(
            select(Sala).where(
                Sala.acronimo == nuevo_acronimo,
                Sala.numero == nuevo_numero,
                Sala.id != sala_id,
            )
        )
        if conflicto.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La sala {nuevo_acronimo}-{nuevo_numero} ya existe.",
            )

    for campo, valor in datos.items():
        setattr(sala, campo, valor)

    await db.flush()
    await db.refresh(sala)
    return SalaRead.model_validate(sala)


@router.delete("/{sala_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_sala(
    sala_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    """
    Soft-delete de una sala (deshabilita). Solo Admin puede eliminar permanentemente.
    En esta implementación realiza un soft-delete (estado_habilitacion=False).
    """
    if current_user.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Administrador puede eliminar salas.")

    result = await db.execute(select(Sala).where(Sala.id == sala_id).with_for_update())
    sala = result.scalar_one_or_none()

    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    sala.estado_habilitacion = False
    await db.flush()


@router.patch("/{sala_id}/deshabilitar", response_model=SalaRead)
async def deshabilitar_sala(
    sala_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> SalaRead:
    """Deshabilita una sala (soft-disable). Solo Admin y Encargado."""
    if current_user.rol not in (RolUsuario.ADMIN, RolUsuario.ENCARGADO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")

    result = await db.execute(select(Sala).where(Sala.id == sala_id).with_for_update())
    sala = result.scalar_one_or_none()

    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    sala.estado_habilitacion = False
    await db.flush()
    await db.refresh(sala)
    return SalaRead.model_validate(sala)


@router.patch("/{sala_id}/habilitar", response_model=SalaRead)
async def habilitar_sala(
    sala_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> SalaRead:
    """Habilita una sala previamente deshabilitada. Solo Admin y Encargado."""
    if current_user.rol not in (RolUsuario.ADMIN, RolUsuario.ENCARGADO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")

    result = await db.execute(select(Sala).where(Sala.id == sala_id).with_for_update())
    sala = result.scalar_one_or_none()

    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")

    sala.estado_habilitacion = True
    await db.flush()
    await db.refresh(sala)
    return SalaRead.model_validate(sala)
