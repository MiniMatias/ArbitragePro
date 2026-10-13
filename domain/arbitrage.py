"""
ArbitragePro NextGen - Domain Arbitrage Rules
Reglas matemáticas puras para detección de Surebets y distribución Anti-Ban.
"""

from typing import List, Dict, Any, Tuple

class ArbitrageDomain:
    """Reglas invariantes de arbitraje determinista."""

    @staticmethod
    def calculate_margin(odds: List[float]) -> Tuple[float, float, bool]:
        """Calcula el margen inverso L = sum(1/odd) y ROI."""
        if not odds or any(o <= 1.0 for o in odds):
            return 1.0, 0.0, False
        
        sum_inverse = sum(1.0 / o for o in odds)
        is_surebet = sum_inverse < 1.0
        
        if is_surebet:
            roi_percent = ((1.0 / sum_inverse) - 1.0) * 100.0
        else:
            roi_percent = -((sum_inverse - 1.0) * 100.0)
            
        return round(sum_inverse, 4), round(roi_percent, 2), is_surebet

    @staticmethod
    def calculate_stakes(odds: List[float], total_investment: float, anti_ban: bool = True) -> Dict[str, Any]:
        """Calcula stakes proporcionales con redondeo entero Anti-Ban."""
        sum_l, roi, is_surebet = ArbitrageDomain.calculate_margin(odds)
        raw_stakes = [total_investment / (sum_l * o) for o in odds]
        
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
