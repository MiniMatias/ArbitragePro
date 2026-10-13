"""
ArbitragePro NextGen - Domain Machine Learning Models
Modelos estocásticos de Poisson bivariado, factores de Dixon-Coles y Brier Score.
"""

import math
from typing import Dict, Any

class DixonColesDomain:
    """Fórmulas cuantitativas de distribución bivariada y Poisson."""

    @staticmethod
    def tau_adjustment(x: int, y: int, lambda_h: float, mu_a: float, rho: float = -0.05) -> float:
        """Ajuste de baja correlación de Dixon-Coles."""
        if x == 0 and y == 0:
            return 1.0 - (lambda_h * mu_a * rho)
        elif x == 0 and y == 1:
            return 1.0 + (lambda_h * rho)
        elif x == 1 and y == 0:
            return 1.0 + (mu_a * rho)
        elif x == 1 and y == 1:
            return 1.0 - rho
        return 1.0

    @staticmethod
    def poisson_pmf(k: int, lmbda: float) -> float:
        """Función de masa de probabilidad Poisson."""
        return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

    @classmethod
    def compute_match_probabilities(
        cls, 
        attack_h: float, 
        defense_h: float, 
        attack_a: float, 
        defense_a: float, 
        home_adv: float = 1.22,
        max_goals: int = 7
    ) -> Dict[str, Any]:
        """Calcula probabilidades exactas de 1X2 normalizadas."""
        lambda_h = max(0.2, attack_h * defense_a * home_adv)
        mu_a = max(0.2, attack_a * defense_h)

        p_home, p_draw, p_away = 0.0, 0.0, 0.0
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                px = cls.poisson_pmf(x, lambda_h)
                py = cls.poisson_pmf(y, mu_a)
                tau = cls.tau_adjustment(x, y, lambda_h, mu_a)
                p_score = max(0.0, px * py * tau)

                if x > y:
                    p_home += p_score
                elif x == y:
                    p_draw += p_score
                else:
                    p_away += p_score

        tot = p_home + p_draw + p_away
        if tot > 0:
            p_home /= tot
            p_draw /= tot
            p_away /= tot

        return {
            "lambda_home_xg": round(lambda_h, 2),
            "mu_away_xg": round(mu_a, 2),
            "prob_home": round(p_home, 4),
            "prob_draw": round(p_draw, 4),
            "prob_away": round(p_away, 4),
            "fair_odd_home": round(1.0 / p_home, 2) if p_home > 0 else 999.0,
            "fair_odd_draw": round(1.0 / p_draw, 2) if p_draw > 0 else 999.0,
            "fair_odd_away": round(1.0 / p_away, 2) if p_away > 0 else 999.0
        }

    @staticmethod
    def calculate_brier_score(pred_home: float, pred_draw: float, pred_away: float, actual: str) -> float:
        """Calcula el Brier Score: BS = sum((p_i - y_i)^2)."""
        y_h = 1.0 if actual == "1" else 0.0
        y_x = 1.0 if actual == "X" else 0.0
        y_a = 1.0 if actual == "2" else 0.0
        return round(((pred_home - y_h) ** 2) + ((pred_draw - y_x) ** 2) + ((pred_away - y_a) ** 2), 4)

# Alias para compatibilidad hacia atrás
DixonColesEngine = DixonColesDomain

