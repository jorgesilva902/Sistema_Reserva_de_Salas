"""
schemas/sala.py
===============
Esquemas Pydantic para el modelo Sala y Tipos de Sala.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SalaBase(BaseModel):
    acronimo: str = Field(..., min_length=1, max_length=10, examples=["LAB"])
    numero: str = Field(..., min_length=1, max_length=10, examples=["01"])
    capacidad: int = Field(..., gt=0, le=500)
    estado_habilitacion: bool = True


class SalaCreate(SalaBase):
    """Datos requeridos para crear una nueva sala."""
    pass


class SalaUpdate(BaseModel):
    """Datos opcionales para actualizar una sala existente (PATCH/PUT)."""
    acronimo: Optional[str] = Field(None, min_length=1, max_length=10)
    numero: Optional[str] = Field(None, min_length=1, max_length=10)
    capacidad: Optional[int] = Field(None, gt=0, le=500)
    estado_habilitacion: Optional[bool] = None


class SalaRead(SalaBase):
    """Datos devueltos por la API al consultar una sala."""
    id: int
    nombre_completo: str  # propiedad calculada del ORM

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tipos de Sala (gestionados como catálogo configurable)
# ---------------------------------------------------------------------------
class TipoSalaCreate(BaseModel):
    """Datos para crear un tipo de sala."""
    acronimo: str = Field(..., min_length=1, max_length=10, examples=["LAB"])
    descripcion: str = Field(..., min_length=1, max_length=100, examples=["Laboratorio de Computación"])


class TipoSalaRead(TipoSalaCreate):
    """Datos devueltos al consultar un tipo de sala."""
    pass
