"""
schemas/reserva.py
==================
Esquemas Pydantic para el modelo Reserva.
"""

import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.models import EstadoReserva

# Patron de validacion para hora HH:MM
_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ReservaBase(BaseModel):
    id_sala: int = Field(..., gt=0)
    fecha: date
    hora_inicio: str = Field(
        ...,
        examples=["08:30"],
        description="Hora de inicio del bloque en formato HH:MM (24h)",
    )
    bloque_minutos: int = Field(default=45, ge=15, le=240)

    @field_validator("hora_inicio")
    @classmethod
    def validar_formato_hora(cls, v: str) -> str:
        if not _HORA_RE.match(v):
            raise ValueError("hora_inicio debe tener formato HH:MM (24h), ej. 08:30")
        return v

    @field_validator("fecha")
    @classmethod
    def no_fecha_pasada(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("No se puede reservar en una fecha pasada")
        return v


class ReservaCreate(ReservaBase):
    """
    Payload del cliente para crear una reserva.
    id_usuario se inyecta desde el token JWT, no se acepta del body.
    """
    pass


class ReservaRead(ReservaBase):
    """Datos devueltos por la API al consultar una reserva."""
    id: int
    id_usuario: int
    estado: EstadoReserva
    creado_en: datetime
    actualizado_en: datetime

    model_config = {"from_attributes": True}


class ReservaCancelUpdate(BaseModel):
    """Payload para cambiar el estado de una reserva (cancelar, marcar asistencia)."""
    estado: EstadoReserva
