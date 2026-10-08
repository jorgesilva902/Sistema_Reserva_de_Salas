"""
core/rate_limiter.py
====================
Middleware de mitigacion de Denegacion de Servicio (DoS) a nivel de aplicacion.

Responsabilidades:
- Limitar el numero maximo de peticiones por minuto por direccion IP y usuario.
- Algoritmo de Ventana Deslizante (Sliding Window) en memoria thread-safe.
- Proteger endpoints de la API REST (/api/*) ante inundaciones (flooding).
- Responder con HTTP 429 Too Many Requests y cabecera Retry-After cuando se exceda la cuota.
"""

from collections import defaultdict, deque
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware global para mitigar DoS limitando el ratio de peticiones entrantes.
    """
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # Mapea client_key -> deque de timestamps (segundos)
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def _get_client_key(self, request: Request) -> str:
        """Identifica de forma unica el origen por IP y token de usuario si existe."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "127.0.0.1"

        # Si incluye token Bearer, asociar cuota al usuario autenticado
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token_fingerprint = auth_header[-10:]
            return f"{ip}:user:{token_fingerprint}"

        return f"{ip}:anon"

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Solo aplicar limitador de tasa a endpoints de la API (/api/*)
        # Se omiten recursos estaticos (/static), Swagger UI (/docs) y health checks
        if not path.startswith("/api/"):
            return await call_next(request)

        client_key = self._get_client_key(request)
        now = time.time()

        with self._lock:
            queue = self._history[client_key]

            # 1. Purgar timestamps que salieron de la ventana deslizante
            while queue and queue[0] <= now - self.window_seconds:
                queue.popleft()

            # 2. Comprobar si se sobrepaso el umbral permitido
            if len(queue) >= self.requests_per_minute:
                oldest = queue[0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            "Limite de peticiones excedido (Proteccion anti-DoS a nivel de aplicacion). "
                            f"Por favor reintente en {retry_after} segundos."
                        )
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # 3. Registrar el timestamp actual
            queue.append(now)
            remaining = self.requests_per_minute - len(queue)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
