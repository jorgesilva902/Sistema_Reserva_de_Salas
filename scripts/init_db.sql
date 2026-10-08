-- Script de inicializacion de la BD para el Sistema de Reserva de Salas
-- Ejecutar como superusuario postgres:
--   psql -U postgres -f scripts/init_db.sql

-- 1. Crear la base de datos (si no existe)
SELECT 'CREATE DATABASE reservas_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'reservas_db')\gexec

-- 2. Conectar a la base de datos
\c reservas_db

-- 3. Las tablas se crean automaticamente via SQLAlchemy (Base.metadata.create_all)
--    cuando DEBUG=true en el .env y se inicia el servidor.
--    Este script solo garantiza que la BD existe.

-- 4. (Opcional) Usuario de aplicacion con permisos limitados (buena practica):
-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reservas_app') THEN
--     CREATE ROLE reservas_app LOGIN PASSWORD 'cambiar_en_produccion';
--   END IF;
-- END
-- $$;
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO reservas_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO reservas_app;

SELECT 'Base de datos reservas_db lista.' AS estado;
