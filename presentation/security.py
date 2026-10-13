"""
ArbitragePro NextGen - Presentation Security Middleware
Protección estricta: Headers de seguridad, Path Traversal Guard, Anti-DoS Payload Limits y Rate Limiting.
"""

import os
import time
import re
from typing import Dict, Tuple, Optional, Any

import hashlib
import secrets
import threading

# Constantes de Seguridad
MAX_PAYLOAD_BYTES = 65536  # 64 KB máximo por solicitud para prevenir ataques de denegación de servicio (DoS)
MAX_URI_LENGTH = 2048  # Límite RFC 7230 para prevención de desbordamiento de búfer y ataques ReDoS
RATE_LIMIT_MAX_REQUESTS = 120  # Máximo de solicitudes por ventana
RATE_LIMIT_WINDOW_SECONDS = 60.0  # Ventana de 1 minuto

class RateLimiter:
    """
    Limitador de tasa en memoria thread-safe con pseudonimización criptográfica (Sliding Window).
    Cumple con el principio de minimización de datos (GDPR Art. 5.1.c / LOPDP Art. 10):
    Las direcciones IP reales jamás se conservan en texto plano en memoria ni en logs.
    """
    _salt: str = secrets.token_hex(16)
    _requests: Dict[str, list] = {}
    _lock = threading.Lock()

    @classmethod
    def _hash_ip(cls, client_ip: str) -> str:
        """Genera un identificador pseudonimizado irreversible con sal volátil."""
        raw = f"{cls._salt}:{client_ip}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:32]

    @classmethod
    def is_allowed(cls, client_ip: str) -> bool:
        now = time.time()
        ip_key = cls._hash_ip(client_ip)

        with cls._lock:
            cls._cleanup(now)

            if ip_key not in cls._requests:
                cls._requests[ip_key] = []

            # Filtrar solo solicitudes dentro de la ventana actual
            cls._requests[ip_key] = [t for t in cls._requests[ip_key] if (now - t) < RATE_LIMIT_WINDOW_SECONDS]

            if len(cls._requests[ip_key]) >= RATE_LIMIT_MAX_REQUESTS:
                return False

            cls._requests[ip_key].append(now)
            return True

    @classmethod
    def _cleanup(cls, now: float):
        """Limpia registros antiguos para evitar fugas de memoria (llamado dentro de _lock)."""
        if len(cls._requests) > 1000:
            for k in list(cls._requests.keys()):
                cls._requests[k] = [t for t in cls._requests[k] if (now - t) < RATE_LIMIT_WINDOW_SECONDS]
                if not cls._requests[k]:
                    del cls._requests[k]


class SecurityGuard:
    """Conjunto de defensas de seguridad de nivel empresarial para el servidor HTTP."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
    }

    @classmethod
    def validate_safe_path(cls, requested_path: str, base_directory: str) -> Tuple[bool, Optional[str]]:
        """
        Previene vulnerabilidades de Path Traversal (ej. ../../etc/passwd o ..\\Windows).
        Verifica que la ruta resuelta esté estrictamente contenida dentro del directorio base.
        """
        # Rechazar caracteres de escape sospechosos
        if "\0" in requested_path or "%2e" in requested_path.lower():
            return False, None

        # Limpiar ruta
        clean_path = requested_path.lstrip("/\\")
        full_path = os.path.abspath(os.path.join(base_directory, clean_path))
        base_dir_abs = os.path.abspath(base_directory)

        # El prefijo absoluto debe ser exactamente el directorio base
        if not full_path.startswith(base_dir_abs):
            return False, None

        # Mitigación de nombres reservados de dispositivo en Windows (ej. CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        filename_base = os.path.splitext(os.path.basename(full_path))[0].upper()
        reserved_devices = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
        }
        if filename_base in reserved_devices:
            return False, None

        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return False, None

        return True, full_path

    @staticmethod
    def sanitize_settle_input(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Valida y sanea los parámetros de liquidación de partidos.
        Evita inyección de datos aberrantes o desbordamiento de tipos.
        """
        if not isinstance(data, dict):
            return False, "El cuerpo de la solicitud debe ser un objeto JSON válido.", {}

        event_id = str(data.get("event_id", "")).strip()
        # event_id solo debe contener caracteres alfanuméricos, guiones bajos o medios
        if not re.match(r"^[a-zA-Z0-9_\-]{3,64}$", event_id):
            return False, "Identificador de evento inválido.", {}

        try:
            home_score = int(data.get("home_score", 0))
            away_score = int(data.get("away_score", 0))
        except (ValueError, TypeError):
            return False, "Los marcadores deben ser números enteros válidos.", {}

        # Validación de rango realista
        if home_score < 0 or home_score > 50 or away_score < 0 or away_score > 50:
            return False, "Los marcadores deben encontrarse en el rango de 0 a 50.", {}

        return True, "OK", {
            "event_id": event_id,
            "home_score": home_score,
            "away_score": away_score
        }
