"""
ArbitragePro NextGen - Telegram & Discord Alert Dispatcher
Notificador en tiempo real para Surebets aprobadas, Value Bets de alta convicción y alertas de riesgo.
Cero dependencias externas (usa urllib nativo de Python).
"""

import urllib.request
import urllib.parse
import json
import threading
from typing import Dict, Any, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import THE_ODDS_API_KEY

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

class AlertDispatcher:
    """Despachador asíncrono de alertas push a Telegram y webhooks."""

    @staticmethod
    def send_telegram_message(message_html: str) -> bool:
        """Envía un mensaje formateado en HTML a Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            # Modo simulado si no hay credenciales configuradas
            safe_text = message_html.encode('ascii', 'replace').decode('ascii')
            print(f"[ALERTA TELEGRAM SIMULADA]\n{safe_text}\n{'-'*40}")
            return True

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message_html,
            "parse_mode": "HTML"
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=4.0) as res:
                return res.status == 200
        except Exception as e:
            print(f"[ERROR TELEGRAM]: {e}")
            return False

    @classmethod
    def dispatch_surebet_alert_async(cls, surebet: Dict[str, Any]):
        """Despacha alerta de Surebet en un hilo secundario para no bloquear el motor."""
        threading.Thread(target=cls._send_surebet_alert, args=(surebet,), daemon=True).start()

    @classmethod
    def _send_surebet_alert(cls, arb: Dict[str, Any]):
        selections_text = ""
        for s in arb.get("selections", []):
            selections_text += f"🔹 <b>{s['selection']}</b>: Apostar <b>${s['stake']} USD</b> en <b>{s['bookmaker'].upper()}</b> (Cuota: <code>{s['odd']}</code>)\n"

        msg = (
            f"🚨 <b>SUREBET VERIFICADA (+{arb.get('roi_percent')}% ROI)</b>\n\n"
            f"⚽ <b>Evento:</b> {arb.get('event_name')}\n"
            f"🏆 <b>Liga:</b> {arb.get('league')}\n\n"
            f"{selections_text}\n"
            f"💰 <b>Inversión Total:</b> ${arb.get('total_investment')} USD\n"
            f"💵 <b>Ganancia Neta Mínima:</b> +${arb.get('min_guaranteed_profit')} USD\n"
            f"🛡️ <b>Filtro Anti-Palpable Error:</b> ✅ APROBADO\n"
            f"🎯 <b>Redondeo Anti-Ban:</b> ACTIVO (Stakes enteros)"
        )
        cls.send_telegram_message(msg)

    @classmethod
    def dispatch_value_bet_alert_async(cls, value_bet: Dict[str, Any]):
        """Despacha alerta de Value Bet institucional."""
        threading.Thread(target=cls._send_value_alert, args=(value_bet,), daemon=True).start()

    @classmethod
    def _send_value_alert(cls, vb: Dict[str, Any]):
        msg = (
            f"🧠 <b>VALUE BET IA DIXON-COLES (+{vb.get('edge_percent')}% EDGE)</b>\n\n"
            f"⚽ <b>Partido:</b> {vb.get('match')} (Minuto {vb.get('minute')}')\n"
            f"🎯 <b>Selección:</b> <b>{vb.get('selection')}</b>\n"
            f"🏢 <b>Casa:</b> <b>{vb.get('bookmaker').upper()}</b> @ <code>{vb.get('market_odd')}</code>\n"
            f"📐 <b>Cuota Justa Modelo:</b> <code>{vb.get('fair_model_odd')}</code> (Prob: {vb.get('model_probability')}%)\n"
            f"📊 <b>Stake Recomendado (Quarter-Kelly):</b> <b>${vb.get('recommended_stake_usd')} USD</b>\n"
            f"🔒 <b>Confianza Brier Score:</b> {vb.get('brier_score_confidence')}"
        )
        cls.send_telegram_message(msg)

if __name__ == "__main__":
    # Test rápido de formato de alerta
    sample_surebet = {
        "event_name": "Real Madrid vs Manchester City",
        "league": "UEFA Champions League",
        "roi_percent": 4.15,
        "total_investment": 100,
        "min_guaranteed_profit": 4.15,
        "selections": [
            {"selection": "1 (Local)", "bookmaker": "ecuabet", "odd": 2.15, "stake": 48},
            {"selection": "X (Empate)", "bookmaker": "bet365", "odd": 3.60, "stake": 29},
            {"selection": "2 (Visita)", "bookmaker": "1xbet", "odd": 3.45, "stake": 23}
        ]
    }
    print("Probando envío de alerta...")
    AlertDispatcher.dispatch_surebet_alert_async(sample_surebet)
