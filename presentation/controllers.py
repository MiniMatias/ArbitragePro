"""
ArbitragePro NextGen - Presentation Controllers
Controladores REST desacoplados que delegan en la Capa de Servicios y Dominio.
"""

from typing import Dict, Any, List
import time
from services.trading_service import TradingService
from services.learning_service import LearningService
from infrastructure.database.repositories import TeamRepository, MatchRepository
from backtesting.backtest_engine import BacktestEngine
from config import INITIAL_BANKROLL, FRACTIONAL_KELLY

class MarketController:
    """Controlador de eventos, Surebets y Value Bets."""

    @staticmethod
    def get_live_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"events": events, "count": len(events)}

    @staticmethod
    def get_surebets(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        approved = []
        rejected = []
        for ev in events:
            opp = TradingService.evaluate_surebet(ev)
            if opp:
                opp_dict = {
                    "event_id": opp.event_id,
                    "event_name": opp.event_name,
                    "league": opp.league,
                    "roi_percent": opp.roi_percent,
                    "sum_l": opp.sum_inverse_l,
                    "total_investment": opp.total_investment,
                    "min_guaranteed_profit": opp.min_guaranteed_profit,
                    "safety_status": "APPROVED" if opp.is_safe else "REJECTED",
                    "audit_message": opp.audit_message,
                    "risk_score": opp.risk_score,
                    "selections": [
                        {"selection": s.selection, "bookmaker": s.bookmaker, "odd": s.odd, "stake": s.stake}
                        for s in opp.selections
                    ]
                }
                if opp.is_safe:
                    approved.append(opp_dict)
                else:
                    rejected.append(opp_dict)

        return {
            "approved_surebets": approved,
            "rejected_alerts": rejected,
            "total_detected": len(approved) + len(rejected)
        }

    @staticmethod
    def get_value_bets(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_signals = []
        for ev in events:
            signals = TradingService.evaluate_value_bets(ev)
            for s in signals:
                all_signals.append({
                    "event_id": s.event_id,
                    "match": s.match,
                    "league": s.league,
                    "minute": s.minute,
                    "score": s.score,
                    "selection": s.selection,
                    "bookmaker": s.bookmaker,
                    "market_odd": s.market_odd,
                    "fair_model_odd": s.fair_model_odd,
                    "model_probability": s.model_probability,
                    "edge_percent": s.edge_percent,
                    "recommended_stake_usd": s.recommended_stake_usd,
                    "brier_score_confidence": s.brier_confidence,
                    "model_source": s.model_source
                })
        return {"value_signals": all_signals, "count": len(all_signals)}


class CalibrationController:
    """Controlador de calibración, Brier score y liquidación bayesiana."""

    @staticmethod
    def get_calibration_summary() -> Dict[str, Any]:
        metrics = MatchRepository.get_metrics_summary()
        recent = MatchRepository.get_recent(limit=10)
        teams = TeamRepository.list_all()

        avg_bs = metrics["average_brier_score"]
        status = "EXCELENTE" if avg_bs < 0.190 else ("BUENA" if avg_bs < 0.220 else "EN CALIBRACION")

        return {
            "metrics": {
                "average_brier_score": avg_bs,
                "calibration_status": status,
                "settled_matches_count": metrics["settled_matches_count"],
                "quarantined_teams_count": metrics["quarantined_teams_count"],
                "bias_reduction_active": True
            },
            "recent_settled_matches": recent,
            "teams_state": teams
        }

    @staticmethod
    def settle_match(sanitized_data: Dict[str, Any], streamer_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_id = sanitized_data["event_id"]
        score_h = sanitized_data["home_score"]
        score_a = sanitized_data["away_score"]

        # Buscar nombres de equipos del evento
        home_team = "Real Madrid"
        away_team = "Manchester City"
        for ev in streamer_events:
            if ev.get("event_id") == event_id:
                home_team = ev.get("home_team", home_team)
                away_team = ev.get("away_team", away_team)
                break

        res = LearningService.settle_match(event_id, home_team, away_team, score_h, score_a)
        return {"settlement_result": res}


class BacktestController:
    """Controlador de simulaciones históricas walk-forward."""

    @staticmethod
    def run_backtest() -> Dict[str, Any]:
        engine = BacktestEngine(initial_bankroll=INITIAL_BANKROLL)
        return engine.run_backtest()
