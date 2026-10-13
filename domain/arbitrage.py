"""
ArbitragePro NextGen - Domain Arbitrage Rules
Reglas matemáticas puras para detección de Surebets y distribución Anti-Ban.
"""

import math
from typing import List, Dict, Any, Tuple

class ArbitrageDomain:
    """Reglas invariantes de arbitraje determinista con validación numérica estricta."""

    @staticmethod
    def _is_valid_odd(odd: Any) -> bool:
        """Verifica que una cuota sea un número real estrictamente válido (> 1.001 y finito)."""
        if not isinstance(odd, (int, float)):
            return False
        if math.isnan(odd) or math.isinf(odd):
            return False
        return odd > 1.001

    @staticmethod
    def calculate_margin(odds: List[float]) -> Tuple[float, float, bool]:
        """
        Calcula el margen inverso L = sum(1/odd) y ROI.
        Blindado contra NaN, infinitos, cuotas no finitas y división por cero.
        """
        if not odds or len(odds) < 2 or not all(ArbitrageDomain._is_valid_odd(o) for o in odds):
            return 1.0, 0.0, False
        
        sum_inverse = sum(1.0 / float(o) for o in odds)
        if math.isnan(sum_inverse) or math.isinf(sum_inverse) or sum_inverse <= 0.0:
            return 1.0, 0.0, False

        is_surebet = sum_inverse < 1.0
        
        if is_surebet:
            roi_percent = ((1.0 / sum_inverse) - 1.0) * 100.0
        else:
            roi_percent = -((sum_inverse - 1.0) * 100.0)
            
        return round(sum_inverse, 4), round(roi_percent, 2), is_surebet

    @staticmethod
    def calculate_stakes(odds: List[float], total_investment: float, anti_ban: bool = True) -> Dict[str, Any]:
        """Calcula stakes proporcionales con redondeo entero discreto y blindaje numérico."""
        if (not isinstance(total_investment, (int, float)) or 
            math.isnan(total_investment) or 
            math.isinf(total_investment) or 
            total_investment <= 0.0):
            total_investment = 100.0

        sum_l, roi, is_surebet = ArbitrageDomain.calculate_margin(odds)
        if sum_l <= 0.0 or not odds or len(odds) < 2:
            return {
                "sum_inverse_l": 1.0,
                "roi_percent": 0.0,
                "is_surebet": False,
                "anti_ban": anti_ban,
                "total_investment": 0.0,
                "stakes": [],
                "raw_stakes": [],
                "scenarios": [],
                "min_guaranteed_profit": 0.0
            }

        raw_stakes = [total_investment / (sum_l * float(o)) for o in odds]
        
        if anti_ban:
            rounded = [int(round(s)) for s in raw_stakes]
            diff = int(total_investment) - sum(rounded)
            if diff != 0 and rounded:
                max_idx = rounded.index(max(rounded))
                rounded[max_idx] += diff
            final_stakes = rounded
        else:
            final_stakes = [round(s, 2) for s in raw_stakes]

        actual_total = sum(final_stakes)
        scenarios = []
        for i, (odd, stake) in enumerate(zip(odds, final_stakes)):
            payout = round(stake * odd, 2)
            profit = round(payout - actual_total, 2)
            scenarios.append({
                "outcome_index": i,
                "odd": odd,
                "stake": stake,
                "payout": payout,
                "profit": profit,
                "is_profitable": profit >= 0.0
            })

        min_profit = min(s["profit"] for s in scenarios) if scenarios else 0.0
        return {
            "sum_inverse_l": sum_l,
            "roi_percent": roi,
            "is_surebet": is_surebet,
            "anti_ban": anti_ban,
            "total_investment": actual_total,
            "stakes": final_stakes,
            "raw_stakes": [round(s, 2) for s in raw_stakes],
            "scenarios": scenarios,
            "min_guaranteed_profit": min_profit
        }
