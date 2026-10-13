"""
ArbitragePro NextGen - Configuration Module
Parámetros cuantitativos, umbrales de seguridad y configuración de modelos.
"""

import os

# Configuración de Servidor
PORT = int(os.getenv("PORT", 8080))
HOST = "127.0.0.1"

# Umbrales Anti-Catástrofe (Guardrails)
PALPABLE_ERROR_MAX_ROI = 0.12  # Si una Surebet supera el 12% bruto, se marca como error de cuota (Palpable Error)
BENCHMARK_BOOKMAKER = "pinnacle"  # Casa de apuestas de referencia para mercado eficiente
MAX_DIVERGENCE_Z_SCORE = 2.8   # Desvío máximo permitido frente a la cuota eficiente
MAX_QUOTE_AGE_SECONDS = 3.5    # Cuotas más viejas que 3.5s se consideran obsoletas (Riesgo de latencia)

# Criterio de Riesgo y Bankroll
INITIAL_BANKROLL = 1000.0      # USD
FRACTIONAL_KELLY = 0.25        # Quarter-Kelly (0.25) para máxima seguridad y mínima volatilidad
MAX_STAKE_PERCENT = 0.03       # Máximo 3% del bankroll en una sola operación
DAILY_LOSS_LIMIT_PERCENT = 0.03 # Circuit Breaker: si la pérdida diaria supera el 3%, congelar sistema

# Parámetros del Motor de Machine Learning (Dixon-Coles & Bayes)
HOME_ADVANTAGE_DEFAULT = 1.22  # Factor inicial de ventaja local
LEARNING_RATE_BAYES = 0.08     # Velocidad de ajuste bayesiano por partido finalizado
UNCERTAINTY_PRIOR = 1.0        # Incertidumbre inicial (σ)
BRIER_SCORE_TARGET = 0.190     # Umbral de calibración óptimo (menor a 0.190 es excelente)
MAX_CONSECUTIVE_ERRORS_TEAM = 2 # Cuarentena para equipos con 2 fallas consecutivas en señales

# Conectores de Datos
SIMULATION_MODE = True         # Por defecto en True para garantizar funcionamiento autónomo
SIMULATION_TICK_SECONDS = 2.0  # Frecuencia de actualización de partidos en vivo
THE_ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
