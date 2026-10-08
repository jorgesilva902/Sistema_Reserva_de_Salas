"""
schemas/usuario.py
==================
Esquemas Pydantic para el modelo Usuario.
Separados en Create (entrada) y Read (salida) para seguir el patron DTO.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.models import RolUsuario


class UsuarioBase(BaseModel):
    rut: str = Field(..., min_length=8, max_length=12, examples=["12345678-9"])
    nombre: str = Field(..., min_length=2, max_length=150)
    correo_institucional: EmailStr
    rol: RolUsuario = RolUsuario.ALUMNO


class UsuarioCreate(UsuarioBase):
    """Datos requeridos para registrar un nuevo usuario."""
    pass


class UsuarioRead(UsuarioBase):
    """Datos devueltos por la API al consultar un usuario."""
    id: int
    contador_cancelaciones: int
    activo: bool
    creado_en: datetime

    model_config = {"from_attributes": True}
