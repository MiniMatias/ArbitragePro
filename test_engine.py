"""
ArbitragePro NextGen - Automated Test Suite
Verificación rigurosa de motores cuantitativos, filtros anti-catástrofe y aprendizaje bayesiano.
"""

import unittest
import os
from database import init_db, seed_default_teams, get_connection
from engine_arbitrage import ArbitrageEngine
from guardrails import SafetyGuardrails
from ml_engine import DixonColesEngine, BayesianContinuousLearner

class TestArbitrageProNextGen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_default_teams()

    def test_01_arbitrage_math_and_anti_ban(self):
        """Verifica el cálculo de margen L y la distribución entera Anti-Ban."""
        # Cuotas con Surebet clara: 2.15 (Ecuabet), 3.60 (Bet365), 3.45 (1xBet)
        odds = [3.20, 3.80, 2.90]
        sum_l, roi, is_surebet = ArbitrageEngine.calculate_margin(odds)

        self.assertTrue(is_surebet, "Debe detectar una Surebet válida")
        self.assertLess(sum_l, 1.0, "La suma de probabilidades inversas debe ser menor a 1.0")
        self.assertGreater(roi, 0.0, "El ROI debe ser estrictamente positivo")

        # Probar cálculo de stakes con Anti-Ban
        total_inv = 100.0
        stakes_res = ArbitrageEngine.calculate_stakes(odds, total_inv, anti_ban=True)

        self.assertEqual(sum(stakes_res["stakes"]), 100, "La suma de stakes redondeados debe ser exactamente igual a la inversión")
        for stake in stakes_res["stakes"]:
            self.assertEqual(stake, int(stake), "Cada stake debe ser un número entero (Anti-Ban)")

        self.assertGreater(stakes_res["min_guaranteed_profit"], 0.0, "El beneficio mínimo garantizado debe ser positivo")

    def test_02_palpable_error_rejection(self):
        """Verifica que cuotas aberrantes (riesgo de anulación por la casa) sean bloqueadas."""
        # Caso 1: ROI absurdo del 35%
        is_palp, msg = SafetyGuardrails.detect_palpable_error(
            candidate_odd=5.50, benchmark_odd=1.85, roi_percent=35.0
        )
        self.assertTrue(is_palp, "Debe bloquear cuotas con ROI anómalo")

        # Caso 2: Divergencia crítica contra Pinnacle
        # Pinnacle tiene cuota 1.25 (prob 80%), casa ofrece 2.50 (prob 40%) -> divergencia 40%
        is_palp_div, msg_div = SafetyGuardrails.detect_palpable_error(
            candidate_odd=2.50, benchmark_odd=1.25, roi_percent=5.0
        )
        self.assertTrue(is_palp_div, "Debe bloquear cuotas que diverjan drásticamente del benchmark")

    def test_03_circuit_breaker(self):
        """Verifica el paro de emergencia por pérdida diaria máxima."""
        is_triggered, msg = SafetyGuardrails.check_circuit_breaker(
            daily_pnl_usd=-35.0, initial_bankroll=1000.0
        )
        self.assertTrue(is_triggered, "Debe activar el Circuit Breaker al perder más del 3% diario")

    def test_04_dixon_coles_probability_coherence(self):
        """Verifica coherencia matemática del modelo predictivo de goles."""
        probs = DixonColesEngine.compute_match_probabilities(
            attack_h=1.45, defense_h=0.85, attack_a=1.35, defense_a=0.90
        )

        sum_probs = probs["prob_home"] + probs["prob_draw"] + probs["prob_away"]
        self.assertAlmostEqual(sum_probs, 1.0, places=2, msg="La suma de probabilidades 1X2 debe ser 1.0")
        self.assertGreater(probs["prob_home"], 0.0)
        self.assertGreater(probs["prob_draw"], 0.0)
        self.assertGreater(probs["prob_away"], 0.0)

    def test_05_bayesian_continuous_learning_and_brier_score(self):
        """Verifica que el modelo aprenda de los resultados y actualice ratings."""
        home = "Real Madrid"
        away = "Manchester City"
        
        initial_rating = BayesianContinuousLearner.get_team_rating(home)
        init_att = initial_rating["attack"]
        init_unc = initial_rating["uncertainty"]

        # Simular partido donde el local golea (3-0)
        pred_probs = {
            "lambda_home_xg": 1.4,
            "mu_away_xg": 1.2,
            "prob_home": 0.45,
            "prob_draw": 0.28,
            "prob_away": 0.27
        }

        settlement = BayesianContinuousLearner.settle_match_and_learn(
            event_id="test_settle_01",
            home_team=home,
            away_team=away,
            home_score=3,
            away_score=0,
            predicted_probs=pred_probs
        )

        self.assertIn("brier_score", settlement)
        self.assertLessEqual(settlement["brier_score"], 2.0)

        # Verificar que el ataque del Real Madrid aumentó tras superar el xG esperado (3 > 1.4)
        updated_rating = BayesianContinuousLearner.get_team_rating(home)
        self.assertGreaterEqual(updated_rating["attack"], init_att, "El ataque debe ajustarse positivamente tras una goleada")
        self.assertLess(updated_rating["uncertainty"], init_unc, "La incertidumbre del modelo debe reducirse tras observar el partido")

    def test_06_backtest_simulation_coherence(self):
        """Verifica que la simulación histórica walk-forward genere métricas estadísticas válidas."""
        from backtesting.backtest_engine import BacktestEngine
        engine = BacktestEngine(initial_bankroll=1000.0)
        report = engine.run_backtest()

        self.assertGreater(report["matches_evaluated"], 0)
        self.assertIn("roi_percent", report)
        self.assertIn("max_drawdown_percent", report)
        self.assertIn("equity_curve", report)
        self.assertGreaterEqual(report["final_bankroll_usd"], 0.0)

if __name__ == "__main__":
    unittest.main()
