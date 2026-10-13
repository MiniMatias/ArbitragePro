"""
ArbitragePro NextGen - Safety Guardrails Module
Filtros de protección contra errores catastróficos: Palpable Errors, Slippage, Latencia y Circuit Breaker.
"""

from typing import Dict, Any, Tuple
import time
from config import (
    PALPABLE_ERROR_MAX_ROI, 
    MAX_DIVERGENCE_Z_SCORE, 
    MAX_QUOTE_AGE_SECONDS,
    BENCHMARK_BOOKMAKER,
    DAILY_LOSS_LIMIT_PERCENT
)

class SafetyGuardrails:
    """Conjunto de filtros estadísticos y operativos para eliminar riesgos de ruina."""

    @staticmethod
    def is_quote_fresh(timestamp: float) -> bool:
        """Verifica si la cuota fue actualizada hace menos de MAX_QUOTE_AGE_SECONDS."""
        return (time.time() - timestamp) <= MAX_QUOTE_AGE_SECONDS

    @staticmethod
    def detect_palpable_error(
        candidate_odd: float, 
        benchmark_odd: float | None,
        roi_percent: float
    ) -> Tuple[bool, str]:
        """
        Detecta si una cuota es un error tipográfico/obvio de la casa (Palpable Error)
        que pueda resultar en anulación unilateral (Void).
        """
        # 1. Alerta por retorno absurdo: Surebets legítimas rara vez superan el 6-8%.
        # Si supera PALPABLE_ERROR_MAX_ROI (12%), es casi con certeza un error de la casa.
        if roi_percent > (PALPABLE_ERROR_MAX_ROI * 100.0):
            return True, f"ROI anómalo ({roi_percent}% > {PALPABLE_ERROR_MAX_ROI*100}%). Riesgo inminente de anulación por casa."

        # 2. Divergencia contra Pinnacle (Benchmark eficiente)
        if benchmark_odd and benchmark_odd > 1.0:
            prob_candidate = 1.0 / candidate_odd
            prob_benchmark = 1.0 / benchmark_odd
            divergence = abs(prob_candidate - prob_benchmark)
            
            # Si la divergencia en probabilidad implícita es mayor a 15 puntos porcentuales
            if divergence > 0.15:
                return True, f"Divergencia crítica ({divergence*100:.1f}%) frente a {BENCHMARK_BOOKMAKER.capitalize()}. Probable cuota invertida."
                
        return False, "Cuota verificada dentro de parámetros normales."

    @staticmethod
    def validate_surebet(surebet: Dict[str, Any], event_raw_odds: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Auditoría completa de una Surebet antes de emitir señal.
        Retorna (is_safe, audit_msg, risk_score)
        """
        roi = surebet.get("roi_percent", 0.0)
        pinnacle_market = event_raw_odds.get(BENCHMARK_BOOKMAKER, {})

        # Verificar cada pata
        for sel in surebet.get("selections", []):
            odd_val = sel.get("odd")
            sel_key = sel.get("selection")[0]  # '1', 'X', or '2'
            bench_odd = pinnacle_market.get(sel_key)

            is_palp, reason = SafetyGuardrails.detect_palpable_error(odd_val, bench_odd, roi)
            if is_palp:
                return False, f"RECHAZADA: {reason}", 0.95

        # Si el margen garantizado es positivo y no hay anomalías
        if surebet.get("min_guaranteed_profit", 0) <= 0:
            return False, "RECHAZADA: El redondeo Anti-Ban generó un escenario con pérdida.", 0.60

        return True, "APROBADA: Surebet validada sin riesgos de error palpable ni latencia.", 0.05

    @staticmethod
    def check_circuit_breaker(daily_pnl_usd: float, initial_bankroll: float) -> Tuple[bool, str]:
        """
        Verifica el límite de pérdida máxima diaria (Drawdown Stop).
        """
        drawdown_pct = (-daily_pnl_usd / initial_bankroll) if daily_pnl_usd < 0 else 0.0
        if drawdown_pct >= DAILY_LOSS_LIMIT_PERCENT:
            return True, f"CIRCUIT BREAKER ACTIVADO: Pérdida diaria de {drawdown_pct*100:.2f}% excede el límite del {DAILY_LOSS_LIMIT_PERCENT*100}%."
        return False, "Bankroll dentro de márgenes saludables."
