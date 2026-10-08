"""
routers/reservas.py
===================
Router FastAPI para el recurso /api/reservas.

LOGICA CRITICA: Control de concurrencia con SELECT ... FOR UPDATE
=================================================================
PostgreSQL es un sistema MVCC (Multi-Version Concurrency Control).
Por defecto, dos transacciones pueden leer la misma fila simultaneamente
sin bloquearse. Esto significa que si dos requests llegan al mismo
milisegundo y ambos verifican disponibilidad antes de que el primero
confirme, ambos podrian ver la sala "libre" y crear reservas solapadas.

Solucion implementada: Row-Level Lock (bloqueo a nivel de fila)
--------------------------------------------------------------
Mediante `SELECT ... FOR UPDATE`, la primera transaccion que lea las
reservas existentes de una sala+fecha las BLOQUEA. La segunda transaccion
que intente leer las mismas filas quedara SUSPENDIDA hasta que la primera
haga commit o rollback. Cuando se libera el lock:
  - Si la primera confirmo la reserva -> la segunda la encontrara y
    detectara el solapamiento -> HTTP 409.
  - Si la primera hizo rollback -> la segunda procedera normalmente.

Esto garantiza serializabilidad del proceso critico sin necesidad de
implementar un sistema de colas externo para este MVP.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.models import EstadoReserva, Reserva, Sala, Usuario
from app.schemas.reserva import ReservaCancelUpdate, ReservaCreate, ReservaRead

router = APIRouter(prefix="/api/reservas", tags=["Reservas"])

# ---------------------------------------------------------------------------
# Tipos de dependencia anotados (DRY + legibilidad)
# ---------------------------------------------------------------------------
DbDep      = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


# ===========================================================================
# POST /api/reservas  — CREACION CON CONTROL DE CONCURRENCIA
# ===========================================================================
@router.post(
    "/",
    response_model=ReservaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva reserva de sala",
    description=(
        "Reserva un bloque horario para una sala. "
        "Implementa bloqueo a nivel de fila (SELECT FOR UPDATE) para "
        "prevenir solapamientos en accesos concurrentes."
    ),
)
async def crear_reserva(
    payload: ReservaCreate,
    db: DbDep,
    current_user: CurrentUser,
) -> ReservaRead:
    """
    Flujo transaccional con Row-Level Lock:

    1. Verificar que la sala exista y este habilitada.
    2. Calcular ventana de tiempo del nuevo bloque (inicio, fin).
    3. SELECT ... FOR UPDATE sobre reservas activas de la misma sala+fecha.
    4. Detectar solapamiento con cualquier reserva bloqueada.
    5. Si hay conflicto -> HTTP 409 (el lock se libera con el rollback).
    6. Si no hay conflicto -> INSERT de la nueva reserva + commit.
    """

    # -----------------------------------------------------------------------
    # PASO 1: Verificar existencia y estado de la sala
    # -----------------------------------------------------------------------
    # Nota: esta consulta NO necesita FOR UPDATE porque la habilitacion
    # de la sala cambia raramente y no es parte de la seccion critica.
    sala_result = await db.execute(
        select(Sala).where(
            Sala.id == payload.id_sala,
            Sala.estado_habilitacion == True,  # noqa: E712
        )
    )
    sala = sala_result.scalar_one_or_none()

    if sala is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sala con id={payload.id_sala} no encontrada o no habilitada.",
        )

    # -----------------------------------------------------------------------
    # PASO 2: Calcular la ventana de tiempo del bloque solicitado
    # -----------------------------------------------------------------------
    # Convertimos hora_inicio (string "HH:MM") a un objeto time de Python.
    hora_h, hora_m = map(int, payload.hora_inicio.split(":"))
    inicio_nuevo: time = time(hora_h, hora_m)

    # Calculamos la hora de fin sumando bloque_minutos al inicio.
    inicio_dt = datetime.combine(date.today(), inicio_nuevo)
    fin_dt    = inicio_dt + timedelta(minutes=payload.bloque_minutos)
    fin_nuevo: time = fin_dt.time()

    # -----------------------------------------------------------------------
    # PASO 3: SELECT ... FOR UPDATE — BLOQUEO TRANSACCIONAL A NIVEL DE FILA
    # -----------------------------------------------------------------------
    # Con_execution_options(populate_existing=True) asegura que SQLAlchemy
    # no use datos cacheados en la sesion actual.
    #
    # .with_for_update() genera el SQL:
    #   SELECT * FROM reservas WHERE id_sala=? AND fecha=? AND estado='Activa'
    #   FOR UPDATE
    #
    # Efecto en PostgreSQL:
    # - La TX actual ADQUIERE un lock exclusivo sobre cada fila leida.
    # - Cualquier otra TX que intente leer esas mismas filas con FOR UPDATE
    #   quedara BLOQUEADA hasta que esta TX haga commit o rollback.
    # - Las TX que lean SIN FOR UPDATE veran el snapshot anterior (MVCC),
    #   pero no podran obtener su propio FOR UPDATE hasta que liberemos.
    reservas_activas_stmt = (
        select(Reserva)
        .where(
            and_(
                Reserva.id_sala == payload.id_sala,
                Reserva.fecha == payload.fecha,
                Reserva.estado == EstadoReserva.ACTIVA,
            )
        )
        .with_for_update()           # <-- SELECT ... FOR UPDATE
        .execution_options(populate_existing=True)
    )

    result = await db.execute(reservas_activas_stmt)
    reservas_existentes: list[Reserva] = result.scalars().all()

    # -----------------------------------------------------------------------
    # PASO 4: Detectar solapamiento con las reservas bloqueadas
    # -----------------------------------------------------------------------
    # Dos bloques [A_inicio, A_fin) y [B_inicio, B_fin) se solapan si y
    # solo si: A_inicio < B_fin AND B_inicio < A_fin
    # (algoritmo de interseccion de intervalos estandar)
    for reserva in reservas_existentes:
        r_h, r_m = map(int, reserva.hora_inicio.split(":"))
        r_inicio: time = time(r_h, r_m)

        r_inicio_dt = datetime.combine(date.today(), r_inicio)
        r_fin_dt    = r_inicio_dt + timedelta(minutes=reserva.bloque_minutos)
        r_fin: time  = r_fin_dt.time()

        # Evaluamos interseccion de intervalos semiabiertos
        hay_solapamiento = inicio_nuevo < r_fin and r_inicio < fin_nuevo

        if hay_solapamiento:
            # El bloque ya esta ocupado: lanzamos HTTP 409 Conflict.
            # FastAPI invocara el rollback automaticamente (via get_db),
            # lo que LIBERA el row-level lock adquirido en el PASO 3.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"La sala '{sala.nombre_completo}' ya tiene una reserva activa "
                    f"el {payload.fecha} que se solapa con el bloque "
                    f"{payload.hora_inicio} (+{payload.bloque_minutos} min). "
                    f"Reserva en conflicto id={reserva.id}."
                ),
            )

    # -----------------------------------------------------------------------
    # PASO 5: No hay conflicto -> Insertar la nueva reserva
    # -----------------------------------------------------------------------
    # En este punto somos la unica TX con lock sobre las filas de esa sala
    # para esa fecha. Procedemos a crear la reserva de forma segura.
    nueva_reserva = Reserva(
        id_usuario=current_user.id,
        id_sala=payload.id_sala,
        fecha=payload.fecha,
        hora_inicio=payload.hora_inicio,
        bloque_minutos=payload.bloque_minutos,
        estado=EstadoReserva.ACTIVA,
    )
    db.add(nueva_reserva)

    # -----------------------------------------------------------------------
    # PASO 6: Confirmar la transaccion (commit)
    # -----------------------------------------------------------------------
    # El `await db.flush()` persiste el INSERT en la TX actual y asigna
    # el id autogenerado por PostgreSQL, sin hacer commit aun.
    # El commit real lo realiza get_db() al finalizar el endpoint.
    await db.flush()
    await db.refresh(nueva_reserva)

    # Una vez hecho el commit (en get_db), el row-level lock se LIBERA
    # automaticamente. La siguiente TX que estaba esperando podra leer
    # la nueva reserva y detectara el solapamiento correctamente.

    return ReservaRead.model_validate(nueva_reserva)


# ===========================================================================
# GET /api/reservas  — LISTADO CON FILTROS
# ===========================================================================
@router.get(
    "/",
    response_model=list[ReservaRead],
    summary="Listar reservas con filtros opcionales",
)
async def listar_reservas(
    db: DbDep,
    current_user: CurrentUser,
    sala_id:  int | None = Query(default=None, description="Filtrar por ID de sala"),
    fecha:    date | None = Query(default=None, description="Filtrar por fecha (YYYY-MM-DD)"),
    estado:   EstadoReserva | None = Query(default=None),
    limit:    int = Query(default=50, le=200),
    offset:   int = Query(default=0, ge=0),
) -> list[ReservaRead]:
    """
    Retorna reservas filtradas. Los Admins y Encargados ven todas;
    Alumnos y Docentes solo ven las propias.
    """
    from app.models.models import RolUsuario

    stmt = select(Reserva)

    # Filtro de visibilidad por rol
    if current_user.rol in (RolUsuario.ALUMNO, RolUsuario.DOCENTE):
        stmt = stmt.where(Reserva.id_usuario == current_user.id)

    # Filtros opcionales
    if sala_id is not None:
        stmt = stmt.where(Reserva.id_sala == sala_id)
    if fecha is not None:
        stmt = stmt.where(Reserva.fecha == fecha)
    if estado is not None:
        stmt = stmt.where(Reserva.estado == estado)

    stmt = stmt.order_by(Reserva.fecha, Reserva.hora_inicio).limit(limit).offset(offset)

    result = await db.execute(stmt)
    reservas = result.scalars().all()
    return [ReservaRead.model_validate(r) for r in reservas]


# ===========================================================================
# GET /api/reservas/{id}  — DETALLE
# ===========================================================================
@router.get(
    "/{reserva_id}",
    response_model=ReservaRead,
    summary="Obtener detalle de una reserva",
)
async def obtener_reserva(
    reserva_id: Annotated[int, Path(gt=0)],
    db: DbDep,
    current_user: CurrentUser,
) -> ReservaRead:
    from app.models.models import RolUsuario

    result = await db.execute(
        select(Reserva).where(Reserva.id == reserva_id)
    )
    reserva = result.scalar_one_or_none()

    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")

    # Verificar permisos: solo el propietario o roles privilegiados
    if (
        current_user.rol in (RolUsuario.ALUMNO, RolUsuario.DOCENTE)
        and reserva.id_usuario != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    return ReservaRead.model_validate(reserva)


# ===========================================================================
# PATCH /api/reservas/{id}  — CANCELAR / MARCAR ASISTENCIA
# ===========================================================================
@router.patch(
    "/{reserva_id}",
    response_model=ReservaRead,
    summary="Actualizar el estado de una reserva (cancelar o marcar asistencia)",
)
async def actualizar_estado_reserva(
    reserva_id: Annotated[int, Path(gt=0)],
    payload: ReservaCancelUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> ReservaRead:
    from app.models.models import RolUsuario

    result = await db.execute(
        select(Reserva).where(Reserva.id == reserva_id).with_for_update()
    )
    reserva = result.scalar_one_or_none()

    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")

    if reserva.estado != EstadoReserva.ACTIVA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se puede modificar una reserva en estado '{reserva.estado}'.",
        )

    # Solo el propietario puede cancelar; Encargado/Admin pueden hacer todo
    if (
        current_user.rol in (RolUsuario.ALUMNO, RolUsuario.DOCENTE)
        and reserva.id_usuario != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    reserva.estado = payload.estado

    # Si el usuario cancela, incrementar su contador de cancelaciones
    if payload.estado == EstadoReserva.CANCELADA:
        result_usr = await db.execute(
            select(Usuario).where(Usuario.id == reserva.id_usuario).with_for_update()
        )
        usuario_reserva = result_usr.scalar_one()
        usuario_reserva.contador_cancelaciones += 1

    await db.flush()
    await db.refresh(reserva)
    return ReservaRead.model_validate(reserva)
