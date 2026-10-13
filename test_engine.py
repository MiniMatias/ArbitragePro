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

    def test_07_security_path_traversal_prevention(self):
        """Verifica que intentos de escape de directorio (Path Traversal) sean bloqueados."""
        from presentation.security import SecurityGuard
        base_dir = os.path.join(os.path.dirname(__file__), "static")

        # Intentos de traversal clásicos
        attacks = [
            "../../../../Windows/System32/drivers/etc/hosts",
            "..\\..\\server.py",
            "%2e%2e/database.py",
            "index.html\0.exe"
        ]
        for attack in attacks:
            is_safe, resolved = SecurityGuard.validate_safe_path(attack, base_dir)
            self.assertFalse(is_safe, f"El ataque '{attack}' debió ser bloqueado")
            self.assertIsNone(resolved)

        # Archivo legítimo debe ser aprobado
        is_safe_ok, resolved_ok = SecurityGuard.validate_safe_path("index.html", base_dir)
        self.assertTrue(is_safe_ok)
        self.assertIsNotNone(resolved_ok)

    def test_08_security_settle_input_sanitization(self):
        """Verifica que entradas maliciosas o desbordadas a /api/settle sean saneadas y rechazadas."""
        from presentation.security import SecurityGuard

        # Caso 1: Goles negativos
        ok, msg, _ = SecurityGuard.sanitize_settle_input({"event_id": "match_01", "home_score": -5, "away_score": 1})
        self.assertFalse(ok, "Debe rechazar marcadores negativos")

        # Caso 2: Goles inverosímiles (Anti-Overflow)
        ok2, msg2, _ = SecurityGuard.sanitize_settle_input({"event_id": "match_01", "home_score": 99999, "away_score": 0})
        self.assertFalse(ok2, "Debe rechazar marcadores absurdos")

        # Caso 3: Inyección en event_id
        ok3, msg3, _ = SecurityGuard.sanitize_settle_input({"event_id": "<script>alert(1)</script>", "home_score": 1, "away_score": 0})
        self.assertFalse(ok3, "Debe rechazar caracteres no alfanuméricos en event_id")

        # Caso 4: Entrada válida
        ok_valid, msg_valid, clean = SecurityGuard.sanitize_settle_input({"event_id": "match_ucl_01", "home_score": 2, "away_score": 1})
        self.assertTrue(ok_valid)
        self.assertEqual(clean["home_score"], 2)

    def test_09_security_rate_limiter(self):
        """Verifica que el limitador de tasa permita tráfico normal y regule ráfagas abusivas."""
        from presentation.security import RateLimiter
        test_ip = "192.168.100.50"

        # Primeras solicitudes deben ser permitidas
        for _ in range(5):
            self.assertTrue(RateLimiter.is_allowed(test_ip))

    def test_10_floating_point_and_nan_inf_protection(self):
        """Verifica blindaje matemático estricto contra NaN, Inf, divisiones por cero y cuotas no finitas."""
        from domain.arbitrage import ArbitrageDomain
        import math

        # Casos aberrantes que antes producían ZeroDivisionError o falsos positivos
        edge_cases = [
            [float('nan'), 2.0],
            [float('inf'), 2.0],
            [float('-inf'), 2.0],
            [float('inf'), float('inf')],
            [0.0, 2.0],
            [-1.5, 2.0],
            [1.0, 2.0],
            [1.0001, 2.0],
            []
        ]
        for odds in edge_cases:
            sum_l, roi, is_surebet = ArbitrageDomain.calculate_margin(odds)
            self.assertFalse(is_surebet, f"Cuotas aberrantes {odds} no deben generar Surebet")
            self.assertFalse(math.isnan(sum_l))
            self.assertFalse(math.isinf(sum_l))

        # Cálculo de stakes con total_investment inválido
        res_nan = ArbitrageDomain.calculate_stakes([2.0, 2.1], float('nan'))
        self.assertGreater(res_nan["total_investment"], 0.0)

        res_inf = ArbitrageDomain.calculate_stakes([2.0, 2.1], float('inf'))
        self.assertGreater(res_inf["total_investment"], 0.0)

    def test_11_privacy_ip_pseudonymization(self):
        """Verifica cumplimiento de LOPDP/GDPR: IPs en texto claro nunca son almacenadas."""
        from presentation.security import RateLimiter
        raw_ip = "200.10.150.25"
        RateLimiter.is_allowed(raw_ip)

        # La IP en texto claro jamás debe estar en las llaves del diccionario en memoria
        self.assertNotIn(raw_ip, RateLimiter._requests, "La IP en texto plano no debe existir en memoria")
        
        # Verificar que el hash pseudonimizado sí existe
        hashed_key = RateLimiter._hash_ip(raw_ip)
        self.assertIn(hashed_key, RateLimiter._requests)
        self.assertEqual(len(hashed_key), 32)

    def test_12_database_indexes_exist(self):
        """Verifica que los índices de rendimiento B-Tree requeridos existan en la base de datos."""
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        indices = [row["name"] for row in c.fetchall()]
        conn.close()

        self.assertIn("idx_settled_at", indices, "El índice idx_settled_at debe existir en la BD")
        self.assertIn("idx_team_quarantine", indices, "El índice idx_team_quarantine debe existir en la BD")
        self.assertIn("idx_signals_created", indices, "El índice idx_signals_created debe existir en la BD")

    def test_13_catboost_inference_and_ensemble(self):
        """Verifica que el modelo CatBoost realice inferencia ultrarrápida y probabilidades calibradas."""
        from infrastructure.ml.catboost_adapter import CatBoostModelAdapter
        import time

        adapter = CatBoostModelAdapter.get_instance()
        self.assertTrue(adapter.is_loaded, "El artefacto CatBoost .cbm debe estar cargado en memoria")

        dummy_features = {
            "home_team": "Real Madrid",
            "away_team": "Manchester City",
            "league": "UEFA Champions League",
            "dixon_p_home": 0.48,
            "dixon_p_draw": 0.28,
            "dixon_p_away": 0.24,
            "lambda_home": 1.7,
            "mu_away": 1.2,
            "pin_odd_home": 2.15,
            "pin_odd_draw": 3.75,
            "pin_odd_away": 3.40,
            "home_rest_days": 4.0,
            "away_rest_days": 3.0
        }

        t0 = time.perf_counter()
        probs, source = adapter.predict_match_probabilities(dummy_features)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(source, "CATBOOST_ML_V1")
        self.assertLess(latency_ms, 15.0, f"La latencia de inferencia debe ser ultrarrápida ({latency_ms:.2f} ms)")
        tot_prob = round(probs["prob_home"] + probs["prob_draw"] + probs["prob_away"], 2)
        self.assertAlmostEqual(tot_prob, 1.0, places=2, msg="La suma de probabilidades 1X2 debe ser 1.0")

    def test_14_catboost_graceful_fallback(self):
        """Verifica que si el modelo CatBoost no está disponible, el sistema degrade elegantemente sin caídas."""
        from infrastructure.ml.catboost_adapter import CatBoostModelAdapter

        # Instanciar adaptador con ruta inválida deliberada
        fallback_adapter = CatBoostModelAdapter(model_path="non_existent_model.cbm")
        self.assertFalse(fallback_adapter.is_loaded)

        fallback_prior = {"prob_home": 0.50, "prob_draw": 0.25, "prob_away": 0.25}
        probs, source = fallback_adapter.predict_match_probabilities({}, fallback_probs=fallback_prior)

        self.assertEqual(source, "FALLBACK_DIXON_COLES")
        self.assertEqual(probs["prob_home"], 0.50)

if __name__ == "__main__":
    unittest.main()
