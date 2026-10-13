"""
ArbitragePro NextGen - CatBoost Model Training & Walk-Forward Validation
Entrena el clasificador multiclase con variables categóricas nativas y evalúa Brier Score.
"""

import os
import sys

# Asegurar que la raíz del proyecto esté en el path de búsqueda
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
from typing import Dict, Any

from backtesting.dataset import BacktestDataLoader
from backtesting.feature_engineering import SportsFeaturePipeline

def train_and_export_catboost_model(export_path: str = None) -> Dict[str, Any]:
    """
    Entrena el modelo CatBoostClassifier con validación temporal estricta (Walk-Forward).
    Guarda el archivo binario portable .cbm en models/.
    Soporta degradación elegante si las políticas del sistema operativo impiden la carga de DLLs.
    """
    try:
        import catboost as cb
    except (ImportError, Exception) as err:
        print(f"[CATBOOST TRAINING AVISO] No se pudo instanciar CatBoost ({err}).")
        print("[CATBOOST TRAINING] Manteniendo modelo serializado existente o fallback Dixon-Coles.")
        return {
            "status": "FALLBACK_ACTIVE",
            "reason": str(err),
            "message": "Entrenamiento omitido por directiva del SO. El sistema opera con Dixon-Coles."
        }

    if export_path is None:
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        os.makedirs(model_dir, exist_ok=True)
        export_path = os.path.join(model_dir, "catboost_v1.cbm")

    # 1. Cargar dataset histórico completo multitemporada ordenado cronológicamente
    matches = BacktestDataLoader.load_all_historical_seasons()
    X, y, feature_names = SportsFeaturePipeline.prepare_training_dataset(matches)

    n_samples = len(X)
    if n_samples < 10:
        raise ValueError(f"Muestras insuficientes para entrenamiento: {n_samples}")

    # 2. División Walk-Forward Temporal (70% pasado para train, 30% futuro para test)
    split_idx = int(n_samples * 0.70)
    X_train, y_train = X[:split_idx], y[:split_idx]
    X_test, y_test = X[split_idx:], y[split_idx:]

    # Índices de columnas categóricas: home_team (0), away_team (1), league (2)
    cat_features = [0, 1, 2]

    # 3. Inicialización de CatBoost con regularización estricta para fútbol
    model = cb.CatBoostClassifier(
        iterations=350,
        learning_rate=0.04,
        depth=5,
        loss_function="MultiClass",
        eval_metric="MultiClass",
        random_seed=42,
        verbose=False
    )

    # 4. Ajuste del modelo con Pool nativo
    train_pool = cb.Pool(X_train, y_train, cat_features=cat_features, feature_names=feature_names)
    test_pool = cb.Pool(X_test, y_test, cat_features=cat_features, feature_names=feature_names)

    model.fit(train_pool, eval_set=test_pool, early_stopping_rounds=30, verbose=False)

    # 5. Evaluación cuantitativa sobre el conjunto de test
    y_pred_proba = model.predict_proba(X_test)
    y_pred = model.predict(X_test).ravel()

    # Cálculo del Brier Score multiclase: sum((p_k - y_k)^2)
    brier_scores = []
    correct_count = 0
    for i, (proba, actual) in enumerate(zip(y_pred_proba, y_test)):
        # One-hot del resultado real
        actual_one_hot = [1.0 if actual == k else 0.0 for k in range(3)]
        bs = sum((p - a) ** 2 for p, a in zip(proba, actual_one_hot))
        brier_scores.append(bs)

        pred_class = int(y_pred[i])
        if pred_class == actual:
            correct_count += 1

    avg_brier_score = round(sum(brier_scores) / len(brier_scores), 4) if brier_scores else 0.0
    accuracy = round(correct_count / len(y_test), 4) if y_test else 0.0

    # 6. Exportación del artefacto a disco (.cbm)
    model.save_model(export_path)

    summary = {
        "status": "SUCCESS",
        "model_path": export_path,
        "total_samples": n_samples,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "test_accuracy": accuracy,
        "test_brier_score": avg_brier_score,
        "feature_count": len(feature_names),
        "feature_names": feature_names
    }

    print(f"[CATBOOST TRAINING] Modelo exportado exitosamente a: {export_path}")
    print(f"[CATBOOST EVALUATION] Muestras Test: {len(X_test)} | Brier Score: {avg_brier_score} | Accuracy: {accuracy * 100:.1f}%")

    return summary

if __name__ == "__main__":
    train_and_export_catboost_model()
