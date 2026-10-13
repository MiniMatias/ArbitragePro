"""
ArbitragePro NextGen - Production Server
Servidor HTTP y API REST en Python puro (cero dependencias externas) con streaming y endpoints de auditoría.
"""

import http.server
import socketserver
import json
import os
import time
from typing import Any
from urllib.parse import urlparse, parse_qs
from database import init_db, seed_default_teams, get_connection
from market_streamer import MarketStreamer
from engine_arbitrage import ArbitrageEngine
from guardrails import SafetyGuardrails
from ml_engine import DixonColesEngine, BayesianContinuousLearner
from backtesting.backtest_engine import BacktestEngine
from config import PORT, HOST, INITIAL_BANKROLL, FRACTIONAL_KELLY

# Inicializar Base de Datos y Streaming
init_db()
seed_default_teams()
streamer = MarketStreamer()
streamer.start_streaming()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

class ArbitrageProHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador HTTP para la API REST y frontend de ArbitragePro."""

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self.send_error(404, "File not found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Rutas Estáticas
        if path == "/" or path == "/index.html":
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path == "/style.css":
            self._serve_file(os.path.join(STATIC_DIR, "style.css"), "text/css; charset=utf-8")
            return
        elif path == "/app.js":
            self._serve_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
            return

        # 2. Endpoints de la API REST
        if path == "/api/status":
            metrics = BayesianContinuousLearner.get_system_calibration_metrics()
            self._send_json({
                "status": "ONLINE",
                "engine": "ArbitragePro NextGen Quantitative & ML",
                "streaming_active": streamer.running,
                "initial_bankroll": INITIAL_BANKROLL,
                "kelly_fraction": FRACTIONAL_KELLY,
                "calibration": metrics,
                "timestamp": time.time()
            })

        elif path == "/api/live-events":
            events = streamer.get_live_events()
            self._send_json({"events": events, "count": len(events)})

        elif path == "/api/surebets":
            events = streamer.get_live_events()
            approved_surebets = []
            rejected_alerts = []

            for ev in events:
                raw_odds = ev.get("odds", {}).get("1X2", {})
                cand = ArbitrageEngine.find_best_arbitrage(ev)
                if cand:
                    is_safe, msg, risk_score = SafetyGuardrails.validate_surebet(cand, raw_odds)
                    cand["safety_status"] = "APPROVED" if is_safe else "REJECTED"
                    cand["audit_message"] = msg
                    cand["risk_score"] = risk_score
                    if is_safe:
                        approved_surebets.append(cand)
                    else:
                        rejected_alerts.append(cand)

            self._send_json({
                "approved_surebets": approved_surebets,
                "rejected_alerts": rejected_alerts,
                "total_detected": len(approved_surebets) + len(rejected_alerts)
            })

        elif path == "/api/value-bets":
            events = streamer.get_live_events()
            value_signals = []

            for ev in events:
                home_team = ev.get("home_team")
                away_team = ev.get("away_team")

                # Obtener ratings actualizados
                r_h = BayesianContinuousLearner.get_team_rating(home_team)
                r_a = BayesianContinuousLearner.get_team_rating(away_team)

                # Si alguno de los equipos está en cuarentena de seguridad, descartar señales predictivas
                if r_h.get("is_quarantined") or r_a.get("is_quarantined"):
                    continue

                probs = DixonColesEngine.compute_match_probabilities(
                    r_h["attack"], r_h["defense"], r_a["attack"], r_a["defense"]
                )

                # Comparar con cuotas de mercado de Pinnacle y Ecuabet
                market_1x2 = ev.get("odds", {}).get("1X2", {})
                sel_map = [("1", "prob_home", "fair_odd_home", home_team),
                           ("X", "prob_draw", "fair_odd_draw", "Empate"),
                           ("2", "prob_away", "fair_odd_away", away_team)]

                for sel, p_key, f_key, sel_name in sel_map:
                    model_prob = probs[p_key]
                    fair_odd = probs[f_key]

                    # Buscar la mejor cuota disponible en el mercado para esta selección
                    best_odd = 0.0
                    best_bm = None
                    for bm, odds_d in market_1x2.items():
                        val = odds_d.get(sel, 0.0)
                        if val > best_odd:
                            best_odd = val
                            best_bm = bm

                    if best_odd > fair_odd:
                        edge = round(((model_prob * best_odd) - 1.0) * 100.0, 2)
                        # Solo emitir si el Edge supera el 3.0%
                        if edge >= 3.0:
                            # Kelly Fraccional
                            b = best_odd - 1.0
                            p = model_prob
                            q = 1.0 - p
                            raw_kelly = (p * b - q) / b if b > 0 else 0
                            rec_stake = max(5.0, round(INITIAL_BANKROLL * raw_kelly * FRACTIONAL_KELLY, 2))

                            value_signals.append({
                                "event_id": ev.get("event_id"),
                                "match": f"{home_team} vs {away_team}",
                                "league": ev.get("league"),
                                "minute": ev.get("minute"),
                                "score": f"{ev.get('score', {}).get('home')}-{ev.get('score', {}).get('away')}",
                                "selection": f"{sel} ({sel_name})",
                                "bookmaker": best_bm,
                                "market_odd": best_odd,
                                "fair_model_odd": fair_odd,
                                "model_probability": round(model_prob * 100, 1),
                                "edge_percent": edge,
                                "recommended_stake_usd": rec_stake,
                                "brier_score_confidence": round(1.0 - r_h["uncertainty"]*0.3, 2)
                            })

            self._send_json({"value_signals": value_signals, "count": len(value_signals)})

        elif path == "/api/calibration":
            metrics = BayesianContinuousLearner.get_system_calibration_metrics()
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM settled_matches ORDER BY settled_at DESC LIMIT 10")
            recent_settled = [dict(row) for row in c.fetchall()]

            c.execute("SELECT team_name, attack, defense, uncertainty, consecutive_errors, is_quarantined FROM team_ratings")
            teams = [dict(row) for row in c.fetchall()]
            conn.close()

            self._send_json({
                "metrics": metrics,
                "recent_settled_matches": recent_settled,
                "teams_state": teams
            })

        elif path == "/api/backtest/run":
            engine = BacktestEngine(initial_bankroll=INITIAL_BANKROLL)
            results = engine.run_backtest()
            self._send_json(results)
        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/settle":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            event_id = data.get("event_id", "match_ucl_01")
            home_score = int(data.get("home_score", 2))
            away_score = int(data.get("away_score", 1))

            result = streamer.settle_event_manually(event_id, home_score, away_score)
            self._send_json({"settlement_result": result})
        else:
            self.send_error(404, "Endpoint not found")

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), ArbitrageProHandler) as httpd:
        print(f"[ARBITRAGEPRO ENGINE] Servidor activo y escuchando en http://{HOST}:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
