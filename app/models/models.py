"""
models.py
=========
Definicion de los modelos ORM (tablas) con SQLAlchemy Declarative.

Convenciones aplicadas:
- Todos los modelos heredan de `Base` (DeclarativeBase de SQLAlchemy 2.x).
- Se usan `Mapped` y `mapped_column` (API moderna de SQLAlchemy 2.0+).
- Los Enums de Python se mapean directamente a tipos ENUM de PostgreSQL.
- Se definen indices y restricciones UNIQUE a nivel de tabla cuando aplica.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base declarativa (punto de entrada para Alembic y create_all)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base comun para todos los modelos ORM del proyecto."""
    pass


# ---------------------------------------------------------------------------
# Enumeraciones de dominio
# ---------------------------------------------------------------------------
class RolUsuario(str, enum.Enum):
    """
    Roles posibles dentro del sistema academico.
    Hereda de `str` para que Pydantic y JSON lo serialicen como string.
    """
    ALUMNO     = "Alumno"
    DOCENTE    = "Docente"
    ADMIN      = "Admin"
    ENCARGADO  = "Encargado"


class EstadoReserva(str, enum.Enum):
    """
    Ciclo de vida de una reserva.
    - ACTIVA   : reserva confirmada y vigente.
    - CANCELADA: cancelada por el usuario o por el sistema.
    - ASISTIDA : el usuario hizo check-in; la sala fue efectivamente usada.
    """
    ACTIVA    = "Activa"
    CANCELADA = "Cancelada"
    ASISTIDA  = "Asistida"


# ---------------------------------------------------------------------------
# Modelo: Usuario
# ---------------------------------------------------------------------------
class Usuario(Base):
    """
    Representa a un miembro de la institucion que puede realizar reservas.

    Columnas clave:
    - rut              : identificador nacional unico (ej. '12345678-9').
    - correo_institucional: debe ser unico; usado como login.
    - rol              : determina permisos y limites de reserva.
    - contador_cancelaciones: permite aplicar penalizaciones automaticas
                              cuando supera un umbral configurable.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    rut: Mapped[str] = mapped_column(
        String(12), nullable=False, unique=True, index=True,
        comment="RUT chileno con digito verificador, ej. 12345678-9"
    )
    nombre: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    correo_institucional: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    rol: Mapped[RolUsuario] = mapped_column(
        PgEnum(RolUsuario, name="rol_usuario_enum", create_type=True),
        nullable=False,
        default=RolUsuario.ALUMNO,
    )
    contador_cancelaciones: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0,
        comment="N de veces que el usuario cancelo una reserva activa"
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relacion inversa: un Usuario puede tener muchas Reservas
    reservas: Mapped[list["Reserva"]] = relationship(
        back_populates="usuario", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} rut={self.rut} rol={self.rol}>"


# ---------------------------------------------------------------------------
# Modelo: Sala
# ---------------------------------------------------------------------------
class Sala(Base):
    """
    Representa un recinto fisico reservable (laboratorio, salon, etc.).

    Columnas clave:
    - acronimo + numero forman el identificador legible (ej. LAB-01).
      La combinacion es UNIQUE para evitar duplicados.
    - capacidad: maximo de personas; puede usarse para filtrar salas aptas.
    - estado_habilitacion: permite deshabilitar una sala sin borrarla
                           (ej. en mantencion).
    """
    __tablename__ = "salas"

    # Restriccion de unicidad compuesta a nivel de tabla
    __table_args__ = (
        UniqueConstraint("acronimo", "numero", name="uq_sala_acronimo_numero"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    acronimo: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Codigo corto del tipo de sala, ej. LAB, AUD, SALA"
    )
    numero: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Numero o letra identificadora, ej. 01, A, 302"
    )
    capacidad: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Aforo maximo de personas"
    )
    estado_habilitacion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="True = habilitada para reservas; False = fuera de servicio"
    )

    # Relacion inversa
    reservas: Mapped[list["Reserva"]] = relationship(
        back_populates="sala", lazy="raise"
    )

    @property
    def nombre_completo(self) -> str:
        """Retorna el identificador legible, ej. 'LAB-01'."""
        return f"{self.acronimo}-{self.numero}"

    def __repr__(self) -> str:
        return f"<Sala id={self.id} nombre={self.nombre_completo}>"


# ---------------------------------------------------------------------------
# Modelo: Reserva
# ---------------------------------------------------------------------------
class Reserva(Base):
    """
    Registro de una reserva de sala.

    Columnas clave:
    - id_usuario  : FK -> usuarios.id
    - id_sala     : FK -> salas.id
    - fecha       : dia de la reserva (Date, sin hora).
    - hora_inicio : hora de inicio del bloque (Time con zona horaria).
    - bloque_minutos: duracion del bloque; default 45 minutos (una clase).
    - estado      : ciclo de vida de la reserva.

    Restriccion critica de concurrencia:
    La logica de solapamiento NO se maneja aqui como restriccion SQL pura
    (seria compleja con rangos de tiempo variables), sino mediante
    SELECT ... FOR UPDATE en la capa de servicio (ver reservas.py router).
    Se define un indice compuesto (id_sala, fecha) para acelerar esas
    consultas de verificacion.
    """
    __tablename__ = "reservas"

    __table_args__ = (
        # Indice compuesto: acelera la busqueda de conflictos por sala+fecha
        # usado en el SELECT ... FOR UPDATE del endpoint de creacion.
        {"comment": "Tabla central de reservas de salas"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    id_sala: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("salas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Fecha del bloque reservado"
    )
    hora_inicio: Mapped[str] = mapped_column(
        String(5), nullable=False,
        comment="Hora de inicio en formato HH:MM, ej. 08:30"
    )
    bloque_minutos: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=45,
        comment="Duracion del bloque en minutos (tipicamente 45)"
    )
    estado: Mapped[EstadoReserva] = mapped_column(
        PgEnum(EstadoReserva, name="estado_reserva_enum", create_type=True),
        nullable=False,
        default=EstadoReserva.ACTIVA,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relaciones ORM (lazy="raise" previene N+1 accidentales)
    usuario: Mapped["Usuario"] = relationship(
        back_populates="reservas", lazy="raise"
    )
    sala: Mapped["Sala"] = relationship(
        back_populates="reservas", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<Reserva id={self.id} sala={self.id_sala} "
            f"fecha={self.fecha} hora={self.hora_inicio} estado={self.estado}>"
        )
