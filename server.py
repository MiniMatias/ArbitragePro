"""
ArbitragePro NextGen - Robust Production Server (Layered Architecture)
Punto de entrada HTTP con arquitectura en capas, middleware de seguridad, rate limiting y cero vulnerabilidades expuestas.
"""

import http.server
import socketserver
import json
import os
import time
from urllib.parse import urlparse
from typing import Any, Dict

from infrastructure.database import init_db, seed_default_teams
from market_streamer import MarketStreamer
from alerts.telegram_bot import AlertDispatcher
from config import PORT, HOST, INITIAL_BANKROLL, FRACTIONAL_KELLY

from presentation.security import SecurityGuard, RateLimiter, MAX_PAYLOAD_BYTES, MAX_URI_LENGTH
from presentation.controllers import MarketController, CalibrationController, BacktestController

# 1. Inicialización de Capas de Infraestructura
init_db()
seed_default_teams()
streamer = MarketStreamer()
streamer.start_streaming()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

class RobustArbitrageProHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador HTTP blindado: headers seguros, anti-traversal, rate limiting y sanitización."""

    def _get_client_ip(self) -> str:
        """Obtiene la IP del cliente para rate limiting."""
        client_address = self.client_address
        return client_address[0] if client_address else "127.0.0.1"

    def _apply_security_headers(self):
        """Aplica headers de seguridad institucionales (OWASP compliant)."""
        for header, value in SecurityGuard.SECURITY_HEADERS.items():
            self.send_header(header, value)

    def _send_json(self, data: Any, status: int = 200):
        """Envía respuesta JSON con encabezados de seguridad completos."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._apply_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str):
        """Respuesta de error sanitizada (sin fugas de traza o rutas internas)."""
        self._send_json({"error": message, "status_code": status}, status=status)

    def _serve_static(self, relative_path: str, content_type: str):
        """Sirve archivos estáticos con validación anti-Path Traversal estricta."""
        is_safe, safe_full_path = SecurityGuard.validate_safe_path(relative_path, STATIC_DIR)
        if not is_safe or not safe_full_path:
            self._send_error_json(404, "Recurso no encontrado.")
            return

        try:
            with open(safe_full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self._apply_security_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self._send_error_json(500, "Error interno al leer recurso estático.")

    def do_GET(self):
        # 0. Mitigación de Desbordamiento de Buffer de URI (RFC 7230)
        if len(self.path) > MAX_URI_LENGTH:
            self._send_error_json(414, "URI Too Long: La URL excede el límite permitido.")
            return

        # 1. Protección de Rate Limiting por IP (Pseudonimizada)
        client_ip = self._get_client_ip()
        if not RateLimiter.is_allowed(client_ip):
            self._send_error_json(429, "Límite de solicitudes excedido. Intente nuevamente en 60 segundos.")
            return

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            # 2. Enrutamiento Estático
            if path == "/" or path == "/index.html":
                self._serve_static("index.html", "text/html; charset=utf-8")
                return
            elif path == "/style.css":
                self._serve_static("style.css", "text/css; charset=utf-8")
                return
            elif path == "/app.js":
                self._serve_static("app.js", "application/javascript; charset=utf-8")
                return

            # 3. Enrutamiento de API REST (Delega en Controladores)
            events = streamer.get_live_events()

            if path == "/api/status":
                self._send_json({
                    "status": "ONLINE",
                    "engine": "ArbitragePro NextGen Layered Architecture",
                    "streaming_active": streamer.running,
                    "initial_bankroll": INITIAL_BANKROLL,
                    "kelly_fraction": FRACTIONAL_KELLY,
                    "timestamp": time.time()
                })

            elif path == "/api/live-events":
                res = MarketController.get_live_events(events)
                self._send_json(res)

            elif path == "/api/surebets":
                res = MarketController.get_surebets(events)
                # Alerta asíncrona si hay Surebets con ROI >= 3%
                for arb in res.get("approved_surebets", []):
                    if arb.get("roi_percent", 0) >= 3.0:
                        AlertDispatcher.dispatch_surebet_alert_async(arb)
                self._send_json(res)

            elif path == "/api/value-bets":
                res = MarketController.get_value_bets(events)
                self._send_json(res)

            elif path == "/api/calibration":
                res = CalibrationController.get_calibration_summary()
                self._send_json(res)

            elif path == "/api/backtest/run":
                res = BacktestController.run_backtest()
                self._send_json(res)

            else:
                self._send_error_json(404, "Endpoint no encontrado.")

        except Exception as e:
            # Blindaje contra fuga de excepciones internas
            self._send_error_json(500, "Error interno del servidor.")

    def do_POST(self):
        # 0. Mitigación de Desbordamiento de Buffer de URI (RFC 7230)
        if len(self.path) > MAX_URI_LENGTH:
            self._send_error_json(414, "URI Too Long: La URL excede el límite permitido.")
            return

        # 1. Rate Limiting por IP (Pseudonimizada)
        client_ip = self._get_client_ip()
        if not RateLimiter.is_allowed(client_ip):
            self._send_error_json(429, "Límite de solicitudes excedido.")
            return

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            # 2. Protección Anti-DoS por Tamaño de Payload
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                self._send_error_json(400, "Encabezado Content-Length inválido.")
                return

            if content_length > MAX_PAYLOAD_BYTES:
                self._send_error_json(413, f"El tamaño de la carga ({content_length} bytes) excede el máximo permitido ({MAX_PAYLOAD_BYTES} bytes).")
                return

            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                raw_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except json.JSONDecodeError:
                self._send_error_json(400, "Cuerpo de solicitud JSON mal formado.")
                return

            # 3. Enrutamiento POST Sanitizado
            if path == "/api/settle":
                is_valid, msg, clean_data = SecurityGuard.sanitize_settle_input(raw_json)
                if not is_valid:
                    self._send_error_json(400, msg)
                    return

                res = CalibrationController.settle_match(clean_data, streamer.get_live_events())
                self._send_json(res)
            else:
                self._send_error_json(404, "Endpoint POST no encontrado.")

        except Exception:
            self._send_error_json(500, "Error interno al procesar solicitud POST.")

# Alias para compatibilidad hacia atrás
ArbitrageProHandler = RobustArbitrageProHandler

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), RobustArbitrageProHandler) as httpd:
        print(f"[ARBITRAGEPRO ENGINE] Servidor robusto y blindado activo en http://{HOST}:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
