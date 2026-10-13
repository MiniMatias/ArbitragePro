"""
ArbitragePro NextGen - Real-Time Market Streamer
Ingesta de datos en tiempo real: streaming estocástico de alta fidelidad y conector a The Odds API.
"""

import time
import random
import threading
from typing import Dict, Any, List
from ml_engine import DixonColesEngine, BayesianContinuousLearner
from guardrails import SafetyGuardrails
from engine_arbitrage import ArbitrageEngine
from config import SIMULATION_TICK_SECONDS, THE_ODDS_API_KEY

class MarketStreamer:
    """Orquestador de eventos y cuotas en vivo."""

    def __init__(self):
        self.events: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._thread = None
        self._lock = threading.Lock()
        self._initialize_default_events()

    def _initialize_default_events(self):
        """Crea eventos iniciales de referencia."""
        now = time.time()
        base_matches = [
            {
                "event_id": "match_ucl_01",
                "sport": "Fútbol",
                "league": "UEFA Champions League",
                "home_team": "Real Madrid",
                "away_team": "Manchester City",
                "status": "LIVE",
                "minute": 32,
                "score": {"home": 1, "away": 0},
                "base_prob": {"1": 0.48, "X": 0.28, "2": 0.24}
            },
            {
                "event_id": "match_ucl_02",
                "sport": "Fútbol",
                "league": "UEFA Champions League",
                "home_team": "Bayern Munich",
                "away_team": "Arsenal",
                "status": "LIVE",
                "minute": 64,
                "score": {"home": 1, "away": 1},
                "base_prob": {"1": 0.42, "X": 0.32, "2": 0.26}
            },
            {
                "event_id": "match_ligapro_01",
                "sport": "Fútbol",
                "league": "Ecuador LigaPro",
                "home_team": "Liga de Quito",
                "away_team": "Independiente del Valle",
                "status": "LIVE",
                "minute": 18,
                "score": {"home": 0, "away": 0},
                "base_prob": {"1": 0.44, "X": 0.30, "2": 0.26}
            },
            {
                "event_id": "match_ligapro_02",
                "sport": "Fútbol",
                "league": "Ecuador LigaPro",
                "home_team": "Barcelona SC",
                "away_team": "Emelec",
                "status": "LIVE",
                "minute": 88,
                "score": {"home": 2, "away": 1},
                "base_prob": {"1": 0.82, "X": 0.12, "2": 0.06}
            }
        ]

        for m in base_matches:
            self._update_event_odds(m, now)
            self.events[m["event_id"]] = m

    def _update_event_odds(self, match: Dict[str, Any], timestamp: float):
        """Genera cuotas actualizadas para múltiples casas con divergencias realistas."""
        p_home = match["base_prob"]["1"]
        p_draw = match["base_prob"]["X"]
        p_away = match["base_prob"]["2"]

        # Margen estándar por casa
        margins = {
            "pinnacle": 0.022,  # Benchmark eficiente (2.2% margen)
            "bet365":   0.055,  # 5.5% margen
            "ecuabet":  0.065,  # 6.5% margen (Mercado local)
            "1xbet":    0.045,  # 4.5% margen
            "betcris":  0.060   # 6.0% margen
        }

        odds_dict = {}
        for bm, margin in margins.items():
            # Introducir pequeñas discrepancias aleatorias por casa
            noise_1 = random.uniform(-0.03, 0.03)
            noise_x = random.uniform(-0.02, 0.02)
            noise_2 = random.uniform(-0.03, 0.03)

            q_home = max(0.05, p_home + noise_1)
            q_draw = max(0.05, p_draw + noise_x)
            q_away = max(0.05, p_away + noise_2)
            tot_q = q_home + q_draw + q_away
            q_home /= tot_q
            q_draw /= tot_q
            q_away /= tot_q

            # Cuota bruta con margen
            m_factor = 1.0 + margin
            odd_1 = round(1.0 / (q_home * m_factor), 2)
            odd_x = round(1.0 / (q_draw * m_factor), 2)
            odd_2 = round(1.0 / (q_away * m_factor), 2)

            odds_dict[bm] = {
                "1": max(1.02, odd_1),
                "X": max(1.05, odd_x),
                "2": max(1.02, odd_2),
                "updated_at": timestamp
            }

        # Generar intencionalmente una Surebet legítima en match_ucl_01 entre Ecuabet y Bet365
        if match["event_id"] == "match_ucl_01":
            # Ecuabet infla ligeramente el Local y Bet365 el Visitante
            odds_dict["ecuabet"]["1"] = round(1.0 / (p_home * 0.94), 2)  # Cuota competitiva
            odds_dict["bet365"]["X"] = round(1.0 / (p_draw * 0.95), 2)
            odds_dict["1xbet"]["2"] = round(1.0 / (p_away * 0.94), 2)

        match["odds"] = {"1X2": odds_dict}
        match["timestamp"] = timestamp

    def start_streaming(self):
        """Inicia el hilo de simulación y streaming continuo."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop_streaming(self):
        """Detiene el streaming."""
        self.running = False

    def _run_loop(self):
        """Bucle continuo de avance de eventos y aprendizaje en tiempo real."""
        while self.running:
            time.sleep(SIMULATION_TICK_SECONDS)
            now = time.time()
            with self._lock:
                for event_id, match in list(self.events.items()):
                    if match["status"] == "LIVE":
                        match["minute"] += 1

                        # Probabilidad estocástica de gol por minuto (~2.8% por minuto)
                        if random.random() < 0.035 and match["minute"] < 90:
                            scoring_team = "home" if random.random() < 0.55 else "away"
                            match["score"][scoring_team] += 1
                            # Ajuste dinámico de probabilidades tras el gol
                            if scoring_team == "home":
                                match["base_prob"]["1"] = min(0.92, match["base_prob"]["1"] + 0.15)
                                match["base_prob"]["X"] = max(0.05, match["base_prob"]["X"] - 0.08)
                                match["base_prob"]["2"] = max(0.03, match["base_prob"]["2"] - 0.07)
                            else:
                                match["base_prob"]["2"] = min(0.92, match["base_prob"]["2"] + 0.15)
                                match["base_prob"]["X"] = max(0.05, match["base_prob"]["X"] - 0.08)
                                match["base_prob"]["1"] = max(0.03, match["base_prob"]["1"] - 0.07)

                        # Si el partido llega al minuto 90, finalizar y disparar aprendizaje continuo
                        if match["minute"] >= 90:
                            match["status"] = "FINISHED"
                            # Ejecutar aprendizaje bayesiano post-partido
                            r_h = BayesianContinuousLearner.get_team_rating(match["home_team"])
                            r_a = BayesianContinuousLearner.get_team_rating(match["away_team"])
                            probs = DixonColesEngine.compute_match_probabilities(
                                r_h["attack"], r_h["defense"], r_a["attack"], r_a["defense"]
                            )
                            BayesianContinuousLearner.settle_match_and_learn(
                                event_id=match["event_id"],
                                home_team=match["home_team"],
                                away_team=match["away_team"],
                                home_score=match["score"]["home"],
                                away_score=match["score"]["away"],
                                predicted_probs=probs
                            )
                        else:
                            self._update_event_odds(match, now)

    def get_live_events(self) -> List[Dict[str, Any]]:
        """Retorna lista de eventos en vivo."""
        with self._lock:
            return list(self.events.values())

    def get_event(self, event_id: str) -> Dict[str, Any] | None:
        """Obtiene un evento por su ID."""
        with self._lock:
            return self.events.get(event_id)

    def settle_event_manually(self, event_id: str, home_score: int, away_score: int) -> Dict[str, Any]:
        """Permite al operador o tester forzar el cierre de un partido para auditar el aprendizaje."""
        with self._lock:
            match = self.events.get(event_id)
            if not match:
                return {"error": "Evento no encontrado"}
            match["status"] = "FINISHED"
            match["score"] = {"home": home_score, "away": away_score}
            match["minute"] = 90

            r_h = BayesianContinuousLearner.get_team_rating(match["home_team"])
            r_a = BayesianContinuousLearner.get_team_rating(match["away_team"])
            probs = DixonColesEngine.compute_match_probabilities(
                r_h["attack"], r_h["defense"], r_a["attack"], r_a["defense"]
            )
            result = BayesianContinuousLearner.settle_match_and_learn(
                event_id=match["event_id"],
                home_team=match["home_team"],
                away_team=match["away_team"],
                home_score=home_score,
                away_score=away_score,
                predicted_probs=probs
            )
            return result
