"""
ArbitragePro NextGen - End-to-End Server Verification Script
Inicia el servidor en un hilo de fondo y valida cada endpoint REST y archivo estático.
"""

import threading
import time
import urllib.request
import json
import socketserver
from server import ArbitrageProHandler, HOST, PORT

def test_all_endpoints():
    server = socketserver.TCPServer((HOST, PORT), ArbitrageProHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Servidor temporal iniciado en http://{HOST}:{PORT}")

    time.sleep(1.0) # Esperar a que el servidor inicialice

    endpoints = [
        ("/", "text/html"),
        ("/style.css", "text/css"),
        ("/app.js", "application/javascript"),
        ("/api/status", "application/json"),
        ("/api/live-events", "application/json"),
        ("/api/surebets", "application/json"),
        ("/api/value-bets", "application/json"),
        ("/api/calibration", "application/json"),
        ("/api/backtest/run", "application/json")
    ]

    base_url = f"http://{HOST}:{PORT}"
    success_count = 0

    for path, expected_content_type in endpoints:
        url = f"{base_url}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            status = response.status
            content_type = response.headers.get("Content-Type")
            body = response.read()

            assert status == 200, f"Error en {path}: status {status}"
            assert expected_content_type in content_type, f"Error de content-type en {path}: {content_type}"
            print(f"[OK] {path.ljust(20)} -> Status: {status} | Size: {len(body)} bytes | Type: {content_type.split(';')[0]}")
            success_count += 1

    # Probar endpoint POST /api/settle
    post_url = f"{base_url}/api/settle"
    payload = json.dumps({"event_id": "match_ucl_01", "home_score": 2, "away_score": 1}).encode("utf-8")
    req_post = urllib.request.Request(post_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_post) as post_res:
        post_data = json.loads(post_res.read().decode("utf-8"))
        assert "settlement_result" in post_data
        # Verificar OWASP Security Headers
        assert post_res.headers.get("X-Content-Type-Options") == "nosniff"
        assert post_res.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in post_res.headers
        print(f"[OK] POST /api/settle     -> Status: {post_res.status} | Res: {post_data['settlement_result']['final_score']} (BS: {post_data['settlement_result']['brier_score']}) | OWASP Headers OK")
        success_count += 1

    # Probar rechazo de URI excesiva (>2048 chars -> 414 URI Too Long)
    long_path = "/api/status?" + "x=" * 2100
    try:
        urllib.request.urlopen(f"{base_url}{long_path}")
        assert False, "Debe rechazar URIs que superen los 2048 caracteres"
    except urllib.error.HTTPError as err:
        assert err.code == 414, f"Esperaba código 414 pero recibió {err.code}"
        print(f"[OK] 414 URI Too Long     -> Status: {err.code} | Rechazado correctamente")
        success_count += 1

    server.shutdown()
    print(f"\nTODOS LOS ENDPOINTS Y CONTROLES DE SEGURIDAD VALIDADOS ({success_count}/{len(endpoints)+2}) EXITOSAMENTE.")

if __name__ == "__main__":
    test_all_endpoints()
