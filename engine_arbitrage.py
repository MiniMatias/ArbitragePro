"""
ArbitragePro NextGen - Quantitative Arbitrage Engine
Cálculo de Surebets, asignación óptima de capital y algoritmo Anti-Ban.
"""

from typing import List, Dict, Any, Tuple
import math

class ArbitrageEngine:
    """Motor determinista de arbitraje deportivo."""

    @staticmethod
    def calculate_margin(odds: List[float]) -> Tuple[float, float, bool]:
        """
        Calcula el margen de mercado L = sum(1 / odd).
        Retorna (L, roi_percent, is_surebet)
        """
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
    def calculate_stakes(
        odds: List[float], 
        total_investment: float, 
        anti_ban: bool = True
    ) -> Dict[str, Any]:
        """
        Calcula los stakes por cuota.
        Si anti_ban es True, redondea a enteros distribuyendo la diferencia para evitar sospechas.
        """
        sum_inverse, roi_percent, is_surebet = ArbitrageEngine.calculate_margin(odds)
        n = len(odds)
        
        # 1. Stakes teóricos continuos
        raw_stakes = [total_investment / (sum_inverse * o) for o in odds]
        
        final_stakes = []
        if anti_ban:
            # Redondeo al entero más cercano
            rounded = [int(round(s)) for s in raw_stakes]
            diff = int(total_investment) - sum(rounded)
            
            # Asignar la discrepancia entera al stake de mayor valor
            if diff != 0 and rounded:
                max_idx = rounded.index(max(rounded))
                rounded[max_idx] += diff
                
            final_stakes = rounded
        else:
            final_stakes = [round(s, 2) for s in raw_stakes]
            
        # 2. Desglose detallado de escenarios y retornos netos
        scenarios = []
        actual_total = sum(final_stakes)
        for i, (odd, stake) in enumerate(zip(odds, final_stakes)):
            payout = round(stake * odd, 2)
            net_profit = round(payout - actual_total, 2)
            scenarios.append({
                "outcome_index": i,
                "odd": odd,
                "stake": stake,
                "payout": payout,
                "net_profit": net_profit,
                "is_profitable": net_profit >= 0.0
            })
            
        min_guaranteed_profit = min(s["net_profit"] for s in scenarios) if scenarios else 0.0
        
        return {
            "sum_inverse_l": sum_inverse,
            "roi_percent": roi_percent,
            "is_surebet": is_surebet,
            "anti_ban_active": anti_ban,
            "total_investment": actual_total,
            "stakes": final_stakes,
            "raw_stakes": [round(s, 2) for s in raw_stakes],
            "scenarios": scenarios,
            "min_guaranteed_profit": min_guaranteed_profit
        }

    @staticmethod
    def find_best_arbitrage(event: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Recorre las cuotas multi-bookmaker de un evento para encontrar la mejor combinación de Surebet.
        """
        market = event.get("odds", {}).get("1X2", {})
        if not market:
            return None
            
        # Extraer mejores cuotas por selección (1, X, 2)
        best_odds = {}
        for sel in ["1", "X", "2"]:
            best_odd = 0.0
            best_bm = None
            for bm, odds_dict in market.items():
                val = odds_dict.get(sel, 0.0)
                if val > best_odd:
                    best_odd = val
                    best_bm = bm
            if best_odd > 1.0:
                best_odds[sel] = {"odd": best_odd, "bookmaker": best_bm}
                
        if len(best_odds) < 3:
            return None
            
        odds_list = [best_odds["1"]["odd"], best_odds["X"]["odd"], best_odds["2"]["odd"]]
        sum_l, roi, is_surebet = ArbitrageEngine.calculate_margin(odds_list)
        
        if is_surebet:
            stakes_calc = ArbitrageEngine.calculate_stakes(odds_list, 100.0, anti_ban=True)
            return {
                "event_id": event.get("event_id"),
                "event_name": f"{event.get('home_team')} vs {event.get('away_team')}",
                "league": event.get("league"),
                "selections": [
                    {"selection": "1 (Local)", "bookmaker": best_odds["1"]["bookmaker"], "odd": best_odds["1"]["odd"], "stake": stakes_calc["stakes"][0]},
                    {"selection": "X (Empate)", "bookmaker": best_odds["X"]["bookmaker"], "odd": best_odds["X"]["odd"], "stake": stakes_calc["stakes"][1]},
                    {"selection": "2 (Visita)", "bookmaker": best_odds["2"]["bookmaker"], "odd": best_odds["2"]["odd"], "stake": stakes_calc["stakes"][2]}
                ],
                "roi_percent": roi,
                "sum_l": sum_l,
                "total_investment": stakes_calc["total_investment"],
                "min_guaranteed_profit": stakes_calc["min_guaranteed_profit"],
                "scenarios": stakes_calc["scenarios"]
            }
        return None
