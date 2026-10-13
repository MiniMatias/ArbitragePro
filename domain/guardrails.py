"""
ArbitragePro NextGen - Domain Guardrails
Reglas y umbrales para eliminar riesgos catastróficos y ruina de capital.
"""

from typing import Tuple, Dict, Any, List

class GuardrailsDomain:
    """Reglas invariantes de mitigación de riesgo."""

    @staticmethod
    def is_palpable_error(candidate_odd: float, benchmark_odd: float | None, roi_pct: float = 0.0, max_roi: float = 12.0, **kwargs) -> Tuple[bool, str]:
        """Detecta si una cuota tiene riesgo de anulación por la casa (Palpable Error)."""
        if "roi_percent" in kwargs:
            roi_pct = kwargs["roi_percent"]

        if roi_pct > max_roi:
            return True, f"ROI anómalo ({roi_pct}% > {max_roi}%). Riesgo de anulación por casa."

        if benchmark_odd and benchmark_odd > 1.0:
            prob_candidate = 1.0 / candidate_odd
            prob_benchmark = 1.0 / benchmark_odd
            divergence = abs(prob_candidate - prob_benchmark)
            if divergence > 0.15:
                return True, f"Divergencia crítica ({divergence*100:.1f}%) frente a Pinnacle. Cuota anómala."

        return False, "Cuota validada dentro de márgenes normales."

    @staticmethod
    def is_circuit_breaker_active(daily_pnl_usd: float, initial_bankroll: float, max_drawdown_pct: float = 3.0) -> Tuple[bool, str]:
        """Verifica si la pérdida acumulada diaria excede el umbral de seguridad."""
        if daily_pnl_usd < 0:
            loss_pct = (-daily_pnl_usd / initial_bankroll) * 100.0
            if loss_pct >= max_drawdown_pct:
                return True, f"Circuit Breaker activado: Pérdida diaria de {loss_pct:.2f}% excede el límite permitido ({max_drawdown_pct}%)."
        return False, "Bankroll dentro de márgenes seguros."

    # Compatibilidad de interfaz
    detect_palpable_error = is_palpable_error
    check_circuit_breaker = is_circuit_breaker_active

# Alias para compatibilidad hacia atrás
SafetyGuardrails = GuardrailsDomain

