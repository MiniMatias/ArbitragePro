"""
ArbitragePro NextGen - Trading Application Service
Coordina la detección de oportunidades, auditoría de seguridad y cálculo de stakes institucionales.
"""

from typing import List, Dict, Any, Tuple
from domain.models import SurebetOpportunity, SurebetSelection, ValueBetSignal
from domain.arbitrage import ArbitrageDomain
from domain.guardrails import GuardrailsDomain
from domain.ml_models import DixonColesDomain
from infrastructure.database.repositories import TeamRepository
from config import BENCHMARK_BOOKMAKER, INITIAL_BANKROLL, FRACTIONAL_KELLY

from infrastructure.ml.catboost_adapter import CatBoostModelAdapter
from backtesting.feature_engineering import SportsFeaturePipeline

class TradingService:
    """Caso de uso: Escaneo y validación de oportunidades de mercado con Ensemble CatBoost."""

    @staticmethod
    def evaluate_surebet(event: Dict[str, Any]) -> SurebetOpportunity | None:
        """Extrae las mejores cuotas de un evento, calcula arbitraje y aplica guardrails."""
        market = event.get("odds", {}).get("1X2", {})
        if not market:
            return None

        best_odds = {}
        for sel in ["1", "X", "2"]:
            best_o = 0.0
            best_bm = None
            for bm, odds_d in market.items():
                val = odds_d.get(sel, 0.0)
                if val > best_o:
                    best_o = val
                    best_bm = bm
            if best_o > 1.0:
                best_odds[sel] = (best_o, best_bm)

        if len(best_odds) < 3:
            return None

        odds_list = [best_odds["1"][0], best_odds["X"][0], best_odds["2"][0]]
        sum_l, roi, is_surebet = ArbitrageDomain.calculate_margin(odds_list)

        if not is_surebet:
            return None

        stakes_calc = ArbitrageDomain.calculate_stakes(odds_list, 100.0, anti_ban=True)
        selections = [
            SurebetSelection(selection="1 (Local)", bookmaker=best_odds["1"][1], odd=odds_list[0], stake=stakes_calc["stakes"][0], raw_stake=stakes_calc["raw_stakes"][0]),
            SurebetSelection(selection="X (Empate)", bookmaker=best_odds["X"][1], odd=odds_list[1], stake=stakes_calc["stakes"][1], raw_stake=stakes_calc["raw_stakes"][1]),
            SurebetSelection(selection="2 (Visita)", bookmaker=best_odds["2"][1], odd=odds_list[2], stake=stakes_calc["stakes"][2], raw_stake=stakes_calc["raw_stakes"][2])
        ]

        # Auditoría de Guardrails (Palpable Error)
        pinnacle_odds = market.get(BENCHMARK_BOOKMAKER, {})
        is_safe = True
        audit_msg = "Aprobado sin anomalías"
        risk_score = 0.05

        for sel_key, (odd_val, _) in best_odds.items():
            bench_odd = pinnacle_odds.get(sel_key)
            is_palp, reason = GuardrailsDomain.is_palpable_error(odd_val, bench_odd, roi)
            if is_palp:
                is_safe = False
                audit_msg = reason
                risk_score = 0.95
                break

        if stakes_calc["min_guaranteed_profit"] <= 0:
            is_safe = False
            audit_msg = "Redondeo generó escenario negativo"
            risk_score = 0.60

        return SurebetOpportunity(
            event_id=event.get("event_id", ""),
            event_name=f"{event.get('home_team')} vs {event.get('away_team')}",
            league=event.get("league", ""),
            selections=selections,
            roi_percent=roi,
            sum_inverse_l=sum_l,
            total_investment=stakes_calc["total_investment"],
            min_guaranteed_profit=stakes_calc["min_guaranteed_profit"],
            is_safe=is_safe,
            audit_message=audit_msg,
            risk_score=risk_score
        )

    @staticmethod
    def evaluate_value_bets(event: Dict[str, Any]) -> List[ValueBetSignal]:
        """Calcula probabilidades Dixon-Coles y filtra señales con Edge positivo."""
        home = event.get("home_team", "")
        away = event.get("away_team", "")

        r_h = TeamRepository.get_by_name(home)
        r_a = TeamRepository.get_by_name(away)
        if not r_h or not r_a:
            return []

        # Regla de seguridad: Si un equipo está en cuarentena, no emitir señales
        if r_h.is_quarantined or r_a.is_quarantined:
            return []

        # 1. Probabilidades base físicas Dixon-Coles
        dc_probs = DixonColesDomain.compute_match_probabilities(r_h.attack, r_h.defense, r_a.attack, r_a.defense)

        # 2. Inferencia Híbrida con CatBoost (Ensemble 70% CatBoost + 30% Dixon-Coles)
        feats = SportsFeaturePipeline.extract_features_for_match(event)
        cb_adapter = CatBoostModelAdapter.get_instance()
        cb_probs, model_source = cb_adapter.predict_match_probabilities(feats, fallback_probs=dc_probs)

        if model_source == "CATBOOST_ML_V1":
            p_home = round(0.70 * cb_probs["prob_home"] + 0.30 * dc_probs["prob_home"], 4)
            p_draw = round(0.70 * cb_probs["prob_draw"] + 0.30 * dc_probs["prob_draw"], 4)
            p_away = round(1.0 - (p_home + p_draw), 4)
        else:
            p_home = dc_probs["prob_home"]
            p_draw = dc_probs["prob_draw"]
            p_away = dc_probs["prob_away"]

        fair_odd_h = round(1.0 / p_home, 2) if p_home > 0 else 99.0
        fair_odd_x = round(1.0 / p_draw, 2) if p_draw > 0 else 99.0
        fair_odd_a = round(1.0 / p_away, 2) if p_away > 0 else 99.0

        market_1x2 = event.get("odds", {}).get("1X2", {})

        signals = []
        sel_tuples = [
            ("1", p_home, fair_odd_h, home),
            ("X", p_draw, fair_odd_x, "Empate"),
            ("2", p_away, fair_odd_a, away)
        ]

        for sel, p_model, fair_o, sel_label in sel_tuples:
            best_o, best_bm = 0.0, None
            for bm, odds_d in market_1x2.items():
                v = odds_d.get(sel, 0.0)
                if v > best_o:
                    best_o, best_bm = v, bm

            if best_o > fair_o:
                edge = round(((p_model * best_o) - 1.0) * 100.0, 2)
                if edge >= 3.0:
                    # Filtro Anti-Palpable Error institucional para Value Bets:
                    # Rechazar señales si divergen críticamente frente al benchmark eficiente (Pinnacle)
                    pin_odd = market_1x2.get(BENCHMARK_BOOKMAKER, {}).get(sel)
                    is_palp, _ = GuardrailsDomain.is_palpable_error(best_o, pin_odd, edge)
                    if is_palp:
                        continue

                    b = best_o - 1.0
                    if b <= 0:
                        continue

                    kelly = ((p_model * b - (1.0 - p_model)) / b) * FRACTIONAL_KELLY
                    if kelly <= 0:
                        continue

                    # Gestión de Riesgo Institucional: Techo de exposición máxima de 4.0% de bankroll por posición
                    max_single_bet = round(INITIAL_BANKROLL * 0.04, 2)
                    rec_stake = min(max_single_bet, max(5.0, round(INITIAL_BANKROLL * kelly, 2)))

                    signals.append(ValueBetSignal(
                        event_id=event.get("event_id", ""),
                        match=f"{home} vs {away}",
                        league=event.get("league", ""),
                        minute=event.get("minute", 0),
                        score=f"{event.get('score', {}).get('home', 0)}-{event.get('score', {}).get('away', 0)}",
                        selection=f"{sel} ({sel_label})",
                        bookmaker=best_bm or "N/A",
                        market_odd=best_o,
                        fair_model_odd=fair_o,
                        model_probability=round(p_model * 100.0, 1),
                        edge_percent=edge,
                        recommended_stake_usd=rec_stake,
                        brier_confidence=round(1.0 - r_h.uncertainty * 0.3, 2)
                    ))

        return signals
