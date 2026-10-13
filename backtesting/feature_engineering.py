"""
ArbitragePro NextGen - Sports Feature Engineering Pipeline
Transformación de datos crudos de fútbol en matrices de features tabulares para CatBoost.
"""

import os
import sys

# Asegurar importación de módulos raíz
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from typing import List, Dict, Any, Tuple
from domain.ml_models import DixonColesDomain
from infrastructure.database.repositories import TeamRepository

class SportsFeaturePipeline:
    """Extractor determinista de variables explicativas para partidos de fútbol."""

    @staticmethod
    def extract_features_for_match(
        match: Dict[str, Any],
        historical_matches: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera el vector de features para un partido individual.
        Integra los priors de Poisson del motor Dixon-Coles con cuotas de Pinnacle y contexto.
        """
        home = match.get("home", match.get("home_team", ""))
        away = match.get("away", match.get("away_team", ""))
        league = match.get("league", "LaLiga")

        # 1. Recuperar ratings de los equipos desde repositorio
        r_h = TeamRepository.get_by_name(home)
        r_a = TeamRepository.get_by_name(away)
        att_h = r_h.attack if r_h else 1.0
        def_h = r_h.defense if r_h else 1.0
        att_a = r_a.attack if r_a else 1.0
        def_a = r_a.defense if r_a else 1.0

        # 2. Computar distribución física Dixon-Coles
        dc_probs = DixonColesDomain.compute_match_probabilities(
            attack_h=att_h,
            defense_h=def_h,
            attack_a=att_a,
            defense_a=def_a
        )

        # 3. Extraer cuotas de referencia (Pinnacle o Bet365)
        pin_h = float(match.get("pin_1", match.get("odds", {}).get("1X2", {}).get("pinnacle", {}).get("1", 2.0)))
        pin_x = float(match.get("pin_x", match.get("odds", {}).get("1X2", {}).get("pinnacle", {}).get("X", 3.2)))
        pin_a = float(match.get("pin_2", match.get("odds", {}).get("1X2", {}).get("pinnacle", {}).get("2", 3.5)))

        # 4. Días de descanso estimados (por defecto 4.0 días entre partidos)
        home_rest = float(match.get("home_rest_days", 4.0))
        away_rest = float(match.get("away_rest_days", 4.0))

        return {
            "home_team": home,
            "away_team": away,
            "league": league,
            "dixon_p_home": dc_probs["prob_home"],
            "dixon_p_draw": dc_probs["prob_draw"],
            "dixon_p_away": dc_probs["prob_away"],
            "lambda_home": dc_probs["lambda_home_xg"],
            "mu_away": dc_probs["mu_away_xg"],
            "pin_odd_home": pin_h,
            "pin_odd_draw": pin_x,
            "pin_odd_away": pin_a,
            "home_rest_days": home_rest,
            "away_rest_days": away_rest
        }

    @staticmethod
    def prepare_training_dataset(matches: List[Dict[str, Any]]) -> Tuple[List[List[Any]], List[int], List[str]]:
        """
        Convierte una lista cronológica de partidos en matrices X (features) e y (labels 0=1, 1=X, 2=2).
        Retorna (X, y, feature_names).
        """
        label_map = {"1": 0, "X": 1, "2": 2}
        feature_names = [
            "home_team", "away_team", "league",
            "dixon_p_home", "dixon_p_draw", "dixon_p_away",
            "lambda_home", "mu_away",
            "pin_odd_home", "pin_odd_draw", "pin_odd_away",
            "home_rest_days", "away_rest_days"
        ]

        X = []
        y = []

        for m in matches:
            ftr = m.get("ftr", "")
            if ftr not in label_map:
                continue

            feats = SportsFeaturePipeline.extract_features_for_match(m)
            row = [feats[f] for f in feature_names]

            X.append(row)
            y.append(label_map[ftr])

        return X, y, feature_names
