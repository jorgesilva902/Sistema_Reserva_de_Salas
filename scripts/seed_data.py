"""
scripts/seed_data.py
====================
Poblamiento inicial de datos (Seed) para pruebas del sistema.
"""

import asyncio
from app.database import db_manager
from app.models.models import Usuario, Sala, RolUsuario
from sqlalchemy import select

async def seed():
    async with db_manager.session_factory() as session:
        # Verificar si ya existen usuarios
        res_u = await session.execute(select(Usuario))
        if not res_u.scalars().first():
            usuarios = [
                Usuario(
                    rut="12345678-5",
                    nombre="Juan Pérez (Alumno)",
                    correo_institucional="alumno@inacap.cl",
                    rol=RolUsuario.ALUMNO,
                    activo=True,
                ),
                Usuario(
                    rut="9876543-2",
                    nombre="Prof. Carlos Soto (Docente)",
                    correo_institucional="docente@inacap.cl",
                    rol=RolUsuario.DOCENTE,
                    activo=True,
                ),
                Usuario(
                    rut="11223344-5",
                    nombre="María González (Encargada)",
                    correo_institucional="encargado@inacap.cl",
                    rol=RolUsuario.ENCARGADO,
                    activo=True,
                ),
                Usuario(
                    rut="22334455-6",
                    nombre="Administrador Sistema",
                    correo_institucional="admin@inacap.cl",
                    rol=RolUsuario.ADMIN,
                    activo=True,
                ),
            ]
            session.add_all(usuarios)
            print("Usuarios de prueba creados.")

        # Verificar si ya existen salas
        res_s = await session.execute(select(Sala))
        if not res_s.scalars().first():
            salas = [
                Sala(acronimo="LAB", numero="101", capacidad=30, estado_habilitacion=True),
                Sala(acronimo="LAB", numero="102", capacidad=25, estado_habilitacion=True),
                Sala(acronimo="AUD", numero="01", capacidad=120, estado_habilitacion=True),
                Sala(acronimo="SALA", numero="201", capacidad=40, estado_habilitacion=True),
                Sala(acronimo="SALA", numero="305", capacidad=35, estado_habilitacion=True),
                Sala(acronimo="CONF", numero="01", capacidad=15, estado_habilitacion=True),
            ]
            session.add_all(salas)
            print("Salas de prueba creadas.")

        await session.commit()
    await db_manager.close()
    print("Seed completado exitosamente.")

if __name__ == "__main__":
    asyncio.run(seed())
