"""
ArbitragePro NextGen - Learning Application Service
Coordina el bucle de aprendizaje continuo, cálculo de Brier Score y reducción de sesgos.
"""

from typing import Dict, Any
import json
import time
from domain.ml_models import DixonColesDomain
from infrastructure.database.repositories import TeamRepository, MatchRepository
from config import LEARNING_RATE_BAYES, MAX_CONSECUTIVE_ERRORS_TEAM

class LearningService:
    """Caso de uso: Liquidación de partidos y actualización bayesiana de ratings."""

    @staticmethod
    def settle_match(event_id: str, home_team: str, away_team: str, home_score: int, away_score: int) -> Dict[str, Any]:
        r_h = TeamRepository.get_by_name(home_team)
        r_a = TeamRepository.get_by_name(away_team)

        if not r_h or not r_a:
            return {"error": "Equipos no encontrados en base de datos"}

        # Predicciones del modelo
        probs = DixonColesDomain.compute_match_probabilities(r_h.attack, r_h.defense, r_a.attack, r_a.defense)

        actual_outcome = "1" if home_score > away_score else ("X" if home_score == away_score else "2")
        bs = DixonColesDomain.calculate_brier_score(probs["prob_home"], probs["prob_draw"], probs["prob_away"], actual_outcome)

        # Residuales
        res_h = home_score - probs["lambda_home_xg"]
        res_a = away_score - probs["mu_away_xg"]

        # Actualización bayesiana con tasa adaptativa
        eta = LEARNING_RATE_BAYES * (r_h.uncertainty + r_a.uncertainty) / 2.0
        r_h.attack = max(0.5, round(r_h.attack + (eta * res_h * 0.15), 3))
        r_h.defense = max(0.5, round(r_h.defense - (eta * res_a * 0.12), 3))
        r_h.uncertainty = max(0.3, round(r_h.uncertainty * 0.96, 3))
        r_h.matches_played += 1

        r_a.attack = max(0.5, round(r_a.attack + (eta * res_a * 0.15), 3))
        r_a.defense = max(0.5, round(r_a.defense - (eta * res_h * 0.12), 3))
        r_a.uncertainty = max(0.3, round(r_a.uncertainty * 0.96, 3))
        r_a.matches_played += 1

        # Detección de fallas críticas y cuarentena
        was_catastrophic = bs > 0.50
        r_h.consecutive_errors = (r_h.consecutive_errors + 1) if was_catastrophic else 0
        r_a.consecutive_errors = (r_a.consecutive_errors + 1) if was_catastrophic else 0
        r_h.is_quarantined = (r_h.consecutive_errors >= MAX_CONSECUTIVE_ERRORS_TEAM)
        r_a.is_quarantined = (r_a.consecutive_errors >= MAX_CONSECUTIVE_ERRORS_TEAM)

        # Persistir cambios
        TeamRepository.save(r_h)
        TeamRepository.save(r_a)

        res_json = json.dumps({"res_home": round(res_h, 2), "res_away": round(res_a, 2)})
        MatchRepository.save_settled(event_id, home_team, away_team, home_score, away_score, probs["prob_home"], probs["prob_draw"], probs["prob_away"], bs, res_json)

        return {
            "event_id": event_id,
            "final_score": f"{home_score} - {away_score}",
            "actual_outcome": actual_outcome,
            "brier_score": bs,
            "residuals": {"home": round(res_h, 2), "away": round(res_a, 2)},
            "learning_rate": round(eta, 4),
            "updated_ratings": {
                home_team: {"attack": r_h.attack, "defense": r_h.defense, "uncertainty": r_h.uncertainty, "quarantined": r_h.is_quarantined},
                away_team: {"attack": r_a.attack, "defense": r_a.defense, "uncertainty": r_a.uncertainty, "quarantined": r_a.is_quarantined}
            }
        }

    @staticmethod
    def get_team_rating(team_name: str) -> Dict[str, Any]:
        """Obtiene el rating estructurado de un equipo para retrocompatibilidad."""
        r = TeamRepository.get_by_name(team_name)
        if r:
            return {
                "team_name": r.team_name,
                "league": r.league,
                "attack": r.attack,
                "defense": r.defense,
                "uncertainty": r.uncertainty,
                "consecutive_errors": r.consecutive_errors,
                "is_quarantined": r.is_quarantined,
                "matches_played": r.matches_played
            }
        return {"team_name": team_name, "league": "Generic", "attack": 1.0, "defense": 1.0, "uncertainty": 1.0, "consecutive_errors": 0, "is_quarantined": False, "matches_played": 0}

    @classmethod
    def settle_match_and_learn(cls, event_id: str, home_team: str, away_team: str, home_score: int, away_score: int, predicted_probs: Any = None) -> Dict[str, Any]:
        """Alias compatible para liquidación y aprendizaje."""
        return cls.settle_match(event_id, home_team, away_team, home_score, away_score)

# Alias para compatibilidad hacia atrás
BayesianContinuousLearner = LearningService

