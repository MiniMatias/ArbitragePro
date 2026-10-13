"""
ArbitragePro NextGen - Machine Learning Infrastructure Layer
Adaptador desacoplado para modelos CatBoost con degradación elegante (Graceful Fallback).
"""

import os
import threading
from typing import Dict, Any, Optional, Tuple

# Detección segura de CatBoost en tiempo de importación
try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    cb = None
    CATBOOST_AVAILABLE = False

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "catboost_v1.cbm")

class CatBoostModelAdapter:
    """
    Adaptador de inferencia thread-safe para CatBoost.
    Asegura que si el modelo no existe o la librería no está instalada,
    el sistema continúe operando con Dixon-Coles de forma transparente.
    """
    _instance: Optional["CatBoostModelAdapter"] = None
    _lock = threading.Lock()

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        self._load_lock = threading.Lock()
        self._try_load_model()

    @classmethod
    def get_instance(cls) -> "CatBoostModelAdapter":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _try_load_model(self) -> bool:
        """Intenta cargar el artefacto .cbm desde el disco."""
        if not CATBOOST_AVAILABLE:
            return False

        if not os.path.exists(self.model_path):
            return False

        try:
            with self._load_lock:
                model = cb.CatBoostClassifier()
                model.load_model(self.model_path)
                self.model = model
                self.is_loaded = True
                return True
        except Exception:
            self.is_loaded = False
            return False

    def predict_match_probabilities(
        self,
        features: Dict[str, Any],
        fallback_probs: Optional[Dict[str, float]] = None
    ) -> Tuple[Dict[str, float], str]:
        """
        Calcula probabilidades 1X2 calibradas a partir de las features del partido.
        Retorna (probabilidades, origen_prediccion).
        """
        # Si no hay CatBoost o el artefacto no existe, usar fallback (Dixon-Coles)
        if not CATBOOST_AVAILABLE or not self.is_loaded or self.model is None:
            if fallback_probs:
                return fallback_probs, "FALLBACK_DIXON_COLES"
            return {"prob_home": 0.45, "prob_draw": 0.28, "prob_away": 0.27}, "DEFAULT_PRIOR"

        try:
            # Orden de features esperado por el modelo
            feature_names = [
                "home_team", "away_team", "league",
                "dixon_p_home", "dixon_p_draw", "dixon_p_away",
                "lambda_home", "mu_away",
                "pin_odd_home", "pin_odd_draw", "pin_odd_away",
                "home_rest_days", "away_rest_days"
            ]
            row = [features.get(f, 0.0) for f in feature_names]

            # Inferencia de probabilidades (predict_proba retorna vector [P(1), P(X), P(2)])
            probs = self.model.predict_proba([row])[0]

            # Normalización y formateo
            p_home = round(float(probs[0]), 4)
            p_draw = round(float(probs[1]), 4)
            p_away = round(float(probs[2]), 4)
            tot = p_home + p_draw + p_away

            if tot > 0:
                p_home = round(p_home / tot, 4)
                p_draw = round(p_draw / tot, 4)
                p_away = round(1.0 - (p_home + p_draw), 4)

            return {
                "prob_home": p_home,
                "prob_draw": p_draw,
                "prob_away": p_away
            }, "CATBOOST_ML_V1"

        except Exception:
            # Salvaguarda: ante cualquier excepción de inferencia, retornar fallback sin crashear
            if fallback_probs:
                return fallback_probs, "FALLBACK_DIXON_COLES"
            return {"prob_home": 0.45, "prob_draw": 0.28, "prob_away": 0.27}, "DEFAULT_PRIOR"
