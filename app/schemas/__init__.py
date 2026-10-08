# app/schemas/__init__.py
from .usuario import UsuarioCreate, UsuarioRead
from .sala import SalaCreate, SalaRead
from .reserva import ReservaCreate, ReservaRead

__all__ = [
    "UsuarioCreate", "UsuarioRead",
    "SalaCreate", "SalaRead",
    "ReservaCreate", "ReservaRead",
]
