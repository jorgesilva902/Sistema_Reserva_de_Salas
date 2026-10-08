import os
import re
from datetime import date, timedelta
import pytest
import requests

BASE_URL = os.getenv("STAGING_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

VALID_CREDENTIALS_ALUMNO = {
    "username": "alumno@inacap.cl",
    "password": "PasswordSegura123!"
}

INVALID_CREDENTIALS = {
    "username": "alumno@inacap.cl",
    "password": "ContrasenaIncorrecta999"
}

USUARIO_B_ID = 9999


@pytest.fixture(scope="session")
def alumno_token():
    payload = {
        "username": VALID_CREDENTIALS_ALUMNO["username"],
        "password": VALID_CREDENTIALS_ALUMNO["password"]
    }
    response = requests.post(f"{BASE_URL}/api/auth/login", data=payload)
    assert response.status_code == 200, f"Fallo al autenticar fixture: {response.text}"
    token = response.json().get("access_token")
    assert token is not None, "El access_token no está presente en la respuesta"
    return token


@pytest.fixture(scope="session")
def auth_headers_alumno(alumno_token):
    return {
        "Authorization": f"Bearer {alumno_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="session")
def alumno_profile(auth_headers_alumno):
    response = requests.get(f"{BASE_URL}/api/usuarios/me", headers=auth_headers_alumno)
    if response.status_code == 200:
        return response.json()
    return {"id": 1, "rol": "ALUMNO"}


def test_cp05_login_credenciales_validas():
    """CP-05: Enviar POST a /api/auth/login con credenciales válidas; verificar HTTP 200 y token JWT válido."""
    response = requests.post(f"{BASE_URL}/api/auth/login", data=VALID_CREDENTIALS_ALUMNO)
    assert response.status_code == 200, f"Se esperaba HTTP 200 pero se obtuvo {response.status_code}"
    data = response.json()
    assert "access_token" in data, "Respuesta no contiene 'access_token'"
    assert data.get("token_type", "").lower() == "bearer"
    token = data["access_token"]
    jwt_regex = r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$"
    assert re.match(jwt_regex, token) is not None, "El formato del token no corresponde a un JWT estándar"
    assert len(token.split(".")) == 3, "El token JWT debe poseer 3 segmentos separados por punto"


def test_cp06_login_password_incorrecto():
    """CP-06: Enviar POST a /api/auth/login con contraseña incorrecta; verificar que retorna HTTP 401."""
    response = requests.post(f"{BASE_URL}/api/auth/login", data=INVALID_CREDENTIALS)
    assert response.status_code == 401, f"Se esperaba HTTP 401 Unauthorized pero se obtuvo {response.status_code}"


def test_cp08_endpoint_administrativo_rol_alumno(auth_headers_alumno, alumno_profile):
    """CP-08: Enviar GET a endpoint administrativo con JWT rol 'ALUMNO'; verificar HTTP 403 Forbidden."""
    otro_usuario_id = alumno_profile["id"] + 1
    response = requests.get(f"{BASE_URL}/api/usuarios/{otro_usuario_id}", headers=auth_headers_alumno)
    assert response.status_code == 403, f"Se esperaba HTTP 403 Forbidden pero se obtuvo {response.status_code}"


def test_cp09_delete_reserva_titular(auth_headers_alumno):
    """CP-09: Enviar DELETE a /api/reservas/{id} con JWT del titular; verificar que el estado HTTP es 200."""
    # Buscar una reserva existente del usuario o crear una nueva con fecha dinámica
    list_res = requests.get(f"{BASE_URL}/api/reservas/", headers=auth_headers_alumno)
    reserva_id = None
    if list_res.status_code == 200 and list_res.json():
        reserva_id = list_res.json()[0]["id"]
    else:
        import time
        dia_offset = int(time.time()) % 100 + 10
        fecha_reserva = (date.today() + timedelta(days=dia_offset)).isoformat()
        reserva_payload = {
            "id_sala": 1,
            "fecha": fecha_reserva,
            "hora_inicio": "14:00",
            "bloque_minutos": 45
        }
        crear_res = requests.post(f"{BASE_URL}/api/reservas/", json=reserva_payload, headers=auth_headers_alumno)
        if crear_res.status_code in [200, 201]:
            reserva_id = crear_res.json()["id"]

    assert reserva_id is not None, "No se pudo obtener una reserva para ejecutar DELETE"
    delete_res = requests.delete(f"{BASE_URL}/api/reservas/{reserva_id}", headers=auth_headers_alumno)
    assert delete_res.status_code == 200, f"Se esperaba HTTP 200 pero se obtuvo {delete_res.status_code} ({delete_res.text})"


def test_cp13_solapamiento_horario_conflicto(auth_headers_alumno):
    """CP-13: POST a /api/reservas con reserva 10:00 a 11:00 e intento 10:30 a 11:30; verificar HTTP 409 Conflict."""
    fecha_reserva = (date.today() + timedelta(days=20)).isoformat()
    payload_base = {
        "id_sala": 1,
        "fecha": fecha_reserva,
        "hora_inicio": "10:00",
        "bloque_minutos": 60
    }
    setup_res = requests.post(f"{BASE_URL}/api/reservas/", json=payload_base, headers=auth_headers_alumno)
    assert setup_res.status_code in [201, 409], f"Error al preparar reserva base: {setup_res.text}"

    payload_conflicto = {
        "id_sala": 1,
        "fecha": fecha_reserva,
        "hora_inicio": "10:30",
        "bloque_minutos": 60
    }
    conflicto_res = requests.post(f"{BASE_URL}/api/reservas/", json=payload_conflicto, headers=auth_headers_alumno)
    assert conflicto_res.status_code == 409, f"Se esperaba HTTP 409 Conflict pero se obtuvo {conflicto_res.status_code}"


def test_cp10_inyeccion_sql_campos_reserva(auth_headers_alumno):
    """CP-10: POST a /api/reservas inyectando SQL; verificar HTTP 422 o sin error de motor SQL (no 500)."""
    payload_sqli = {
        "id_sala": 1,
        "fecha": (date.today() + timedelta(days=25)).isoformat(),
        "hora_inicio": "' OR '1'='1",
        "bloque_minutos": 45
    }
    response = requests.post(f"{BASE_URL}/api/reservas/", json=payload_sqli, headers=auth_headers_alumno)
    assert response.status_code != 500, f"Fallo de seguridad SQL: el servidor devolvió HTTP 500: {response.text}"
    assert response.status_code == 422, f"Se esperaba HTTP 422 Unprocessable Entity pero se obtuvo {response.status_code}"


def test_cp50_inyeccion_usuario_id_en_reserva(auth_headers_alumno, alumno_profile):
    """CP-50: POST a /api/reservas inyectando usuario_id de Usuario B; verificar reserva asignada a Usuario A."""
    import time
    usuario_a_id = alumno_profile["id"]
    offset = int(time.time() * 10) % 500 + 40
    fecha_reserva = (date.today() + timedelta(days=offset)).isoformat()
    payload_idor = {
        "id_sala": 2,
        "fecha": fecha_reserva,
        "hora_inicio": "16:00",
        "bloque_minutos": 45,
        "usuario_id": USUARIO_B_ID,
        "id_usuario": USUARIO_B_ID
    }
    response = requests.post(f"{BASE_URL}/api/reservas/", json=payload_idor, headers=auth_headers_alumno)
    assert response.status_code in [200, 201], f"Error al crear reserva: {response.text}"
    reserva_creada = response.json()
    id_usuario_final = reserva_creada.get("id_usuario") or reserva_creada.get("usuario_id")
    assert id_usuario_final == usuario_a_id, f"Vulnerabilidad IDOR: Reserva asignada a {id_usuario_final} en vez de {usuario_a_id}"
    assert id_usuario_final != USUARIO_B_ID, "La reserva adoptó el usuario_id inyectado"


def test_cp46_flujo_secuencial_e2e():
    """CP-46: Flujo Login -> GET /api/disponibilidad -> POST /api/reservas -> DELETE /api/reservas/{id}."""
    login_res = requests.post(f"{BASE_URL}/api/auth/login", data=VALID_CREDENTIALS_ALUMNO)
    assert login_res.status_code == 200, f"Fallo autenticación: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    fecha_test = (date.today() + timedelta(days=35)).isoformat()
    disp_res = requests.get(f"{BASE_URL}/api/disponibilidad?id_sala=1&fecha={fecha_test}", headers=headers)
    assert disp_res.status_code == 200, f"Endpoint /api/disponibilidad falló o no existe: HTTP {disp_res.status_code}"

    payload_reserva = {
        "id_sala": 1,
        "fecha": fecha_test,
        "hora_inicio": "12:00",
        "bloque_minutos": 45
    }
    reserva_res = requests.post(f"{BASE_URL}/api/reservas/", json=payload_reserva, headers=headers)
    assert reserva_res.status_code in [200, 201], f"Fallo al reservar bloque: {reserva_res.text}"
    reserva_id = reserva_res.json()["id"]

    delete_res = requests.delete(f"{BASE_URL}/api/reservas/{reserva_id}", headers=headers)
    assert delete_res.status_code == 200, f"Fallo al eliminar reserva: HTTP {delete_res.status_code}"
