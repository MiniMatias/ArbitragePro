import time
import threading
import os
import sys
from typing import Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from infrastructure.database.repositories import MatchRepository
from backtesting.train_catboost import train_and_export_catboost_model

class RetrainingDaemon:
    """Demonio de monitoreo continuo de precisión y orquestación de reentrenamientos."""

    _lock = threading.Lock()
    _running = False
    _thread: threading.Thread | None = None
    _last_retrain_timestamp: float = time.time()
    _retrain_count: int = 0
    _last_status: str = "IDLE"
    _last_error: str | None = None

    DRIFT_BRIER_THRESHOLD = 0.28  # Umbral de Brier score que indica degradación
    RETRAIN_INTERVAL_MATCHES = 20  # Reentrenar cada 20 partidos liquidados
    CHECK_INTERVAL_SECONDS = 30.0  # Frecuencia de escaneo del demonio

    @classmethod
    def start(cls):
        """Inicia el demonio en un hilo secundario protegido."""
        with cls._lock:
            if cls._running:
                return
            cls._running = True
            cls._thread = threading.Thread(target=cls._loop, daemon=True, name="RetrainingDaemon")
            cls._thread.start()
            print("[RETRAINING DAEMON] Demonio de reentrenamiento autónomo iniciado.")

    @classmethod
    def stop(cls):
        """Detiene el demonio."""
        with cls._lock:
            cls._running = False

    @classmethod
    def _loop(cls):
        """Bucle de detección de deriva con tolerancia a fallos."""
        while cls._running:
            try:
                time.sleep(cls.CHECK_INTERVAL_SECONDS)
                cls._evaluate_and_retrain_if_needed()
            except Exception as e:
                with cls._lock:
                    cls._last_error = str(e)
                time.sleep(5.0)

    @classmethod
    def _evaluate_and_retrain_if_needed(cls):
        """Verifica métricas recientes en la base de datos y decide si reentrenar."""
        summary = MatchRepository.get_metrics_summary()
        avg_bs = summary.get("average_brier_score", 0.0)
        total_settled = summary.get("settled_matches_count", 0)

        should_retrain = False
        reason = ""

        with cls._lock:
            matches_since = total_settled - (cls._retrain_count * cls.RETRAIN_INTERVAL_MATCHES)

            if matches_since >= cls.RETRAIN_INTERVAL_MATCHES:
                should_retrain = True
                reason = f"Umbral de volumen alcanzado ({matches_since} partidos nuevos)"
            elif avg_bs > cls.DRIFT_BRIER_THRESHOLD and total_settled >= 5:
                should_retrain = True
                reason = f"Deriva de calibración detectada (Brier Score {avg_bs:.4f} > {cls.DRIFT_BRIER_THRESHOLD})"

        if should_retrain:
            cls.trigger_retrain(reason)

    @classmethod
    def trigger_retrain(cls, trigger_reason: str = "MANUAL_TRIGGER") -> Dict[str, Any]:
        """Ejecuta el pipeline de reentrenamiento con protección atómica."""
        with cls._lock:
            cls._last_status = "RECALIBRATING"

        print(f"[RETRAINING DAEMON] Disparando reentrenamiento: {trigger_reason}...")
        t0 = time.time()
        result = train_and_export_catboost_model()
        elapsed = round(time.time() - t0, 2)

        with cls._lock:
            cls._retrain_count += 1
            cls._last_retrain_timestamp = time.time()
            cls._last_status = result.get("status", "SUCCESS")
            cls._last_error = result.get("reason") if result.get("status") == "FALLBACK_ACTIVE" else None

        return {
            "status": cls._last_status,
            "trigger_reason": trigger_reason,
            "elapsed_seconds": elapsed,
            "retrain_count": cls._retrain_count,
            "result_details": result
        }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Retorna el estado operativo del demonio para APIs y dashboard."""
        summary = MatchRepository.get_metrics_summary()
        avg_bs = summary.get("average_brier_score", 0.0)
        total_settled = summary.get("settled_matches_count", 0)

        with cls._lock:
            return {
                "daemon_running": cls._running,
                "current_status": cls._last_status,
                "total_settled_matches": total_settled,
                "average_brier_score": avg_bs,
                "calibration_health": "WARNING_DRIFT" if avg_bs > cls.DRIFT_BRIER_THRESHOLD else "OPTIMAL",
                "retrain_count": cls._retrain_count,
                "last_retrain_timestamp": cls._last_retrain_timestamp,
                "last_retrain_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cls._last_retrain_timestamp)),
                "last_error": cls._last_error
            }

if __name__ == "__main__":
    print("Probando estado del demonio...")
    print(RetrainingDaemon.get_status())
    print("Probando reentrenamiento puntual...")
    res = RetrainingDaemon.trigger_retrain("CLI_TEST")
    print("Resultado:", res)
