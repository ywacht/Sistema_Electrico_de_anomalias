"""
EcoGrid AI - Servicio de Inferencia de Inteligencia Artificial
Asignatura: Fundamentos de IA & Minería de Texto
Universidad Tecnológica de Calvillo (UTC)

MODIFICADO: se agrega la integración de los modelos exportados desde Colab
(modelos_exportados/ecogrid_ai.py) para la arquitectura de un solo ESP32
(solo corriente). Los modelos viejos (consumption_classifier / text_mining_classifier)
se conservan para la parte académica de Fundamentos de IA / Minería de Texto,
pero la decisión real de desconexión ahora también considera el pipeline nuevo.
"""

import os
import sys
from collections import deque

# Asegurar importación de ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_engine.models.consumption_classifier import EcoGridConsumptionPredictor
from ai_engine.models.text_mining_classifier import IncidentTextMiningClassifier

# --- NUEVO: modelos exportados desde Colab (ecogrid_ai.py) ---
EXPORTED_MODELS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "ai_engine", "models", "exported")
)

# Los .joblib del Modelo 1/2 se exportaron desde Colab con una versión de
# scikit-learn donde las clases internas de pérdida (Cython) se pickled con
# __module__ == "_loss" a secas. En instalaciones más nuevas esa ruta ya no
# resuelve sola, así que registramos el alias ANTES de importar/cargar nada.
try:
    from sklearn._loss import _loss as _sklearn_loss_internal
    sys.modules.setdefault("_loss", _sklearn_loss_internal)
except ImportError:
    pass  # si no existe en esta versión de sklearn, simplemente no aplica

try:
    sys.path.append(EXPORTED_MODELS_DIR)
    from ecogrid_ai import cargar_modelos, pipeline_analizar
    ECOGRID_AI_IMPORT_OK = True
except ImportError as exc:
    ECOGRID_AI_IMPORT_OK = False
    print(f"[AI_SERVICE] ADVERTENCIA: no se pudo importar ecogrid_ai.py ({exc}). "
          f"El pipeline de corriente única quedará deshabilitado.")

# Tamaño de la ventana de corriente que se le pasa al pipeline (en lecturas, no segundos)
BUFFER_WINDOW = 60


class AIService:
    """
    Fachada para inferencia en tiempo real de los modelos de IA.
    """

    def __init__(self):
        models_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "ai_engine", "models", "saved")
        )
        self.consumption_predictor = EcoGridConsumptionPredictor(models_dir=models_dir)
        self.text_mining_classifier = IncidentTextMiningClassifier(models_dir=models_dir)

        # Cargar pesos persistidos
        self.consumption_loaded = self.consumption_predictor.load()
        self.text_mining_loaded = self.text_mining_classifier.load()

        if self.consumption_loaded:
            print("[AI_SERVICE] Modelos de patrones de consumo cargados exitosamente.")
        else:
            print("[AI_SERVICE] ADVERTENCIA: Modelos de consumo no encontrados en disco. Ejecute train_models.py.")

        if self.text_mining_loaded:
            print("[AI_SERVICE] Modelo de minería de texto cargado exitosamente.")
        else:
            print("[AI_SERVICE] ADVERTENCIA: Modelo de texto no encontrado. Ejecute train_models.py.")

        # --- NUEVO: carga de los 3 modelos exportados (completador / picos+anomalías / bitácora) ---
        self.ecogrid_ai = None
        self.ecogrid_ai_loaded = False
        if ECOGRID_AI_IMPORT_OK:
            try:
                self.ecogrid_ai = cargar_modelos(EXPORTED_MODELS_DIR)
                self.ecogrid_ai_loaded = True
                print("[AI_SERVICE] Modelos exportados (ecogrid_ai) cargados exitosamente.")
            except Exception as exc:
                print(f"[AI_SERVICE] ADVERTENCIA: no se pudieron cargar los modelos exportados ({exc}).")

        # Buffer de corriente en memoria por dispositivo (requerido por pipeline_analizar)
        self._buffers = {}

    def evaluate_telemetry(self, voltage, current, active_power, reactive_power, power_factor, frequency, thd, temp, model_name="neural_network"):
        """
        Clasifica una lectura eléctrica instantánea (vector completo de 8 variables)
        y determina si procede corte automático. Se conserva para la parte académica
        de Fundamentos de IA (KNN/SVM/Red Neuronal sobre datos sintéticos enriquecidos).
        """
        if not self.consumption_loaded:
            # Reglas heurísticas de respaldo
            is_overload = current > 32.0 or thd > 15.0 or temp > 70.0
            is_peak = current > 18.0 and not is_overload
            pattern = "Sobrecarga / Anomalía" if is_overload else ("Pico de Demanda" if is_peak else "Normal")
            return {
                "model_used": "heuristic_fallback",
                "class_id": 2 if is_overload else (1 if is_peak else 0),
                "class_name": pattern,
                "is_anomaly": is_overload or is_peak,
                "should_disconnect": is_overload,
                "action": "AUTOMATIC_DISCONNECT" if is_overload else "NORMAL_OPERATION",
                "probabilities": {},
            }

        features = [voltage, current, active_power, reactive_power, power_factor, frequency, thd, temp]
        return self.consumption_predictor.predict(features, model_name=model_name)

    # --- NUEVO ---
    def evaluate_current_pipeline(self, device_id, timestamp_iso, current):
        """
        Pipeline nuevo basado únicamente en la corriente del ESP32 real (ACS712).
        Mantiene un buffer por dispositivo y llama a pipeline_analizar() de
        ecogrid_ai.py (modelo 1: completa huecos, modelo 2: picos/anomalías,
        modelo 3: bitácora -> severidad).

        Retorna None si los modelos exportados no están disponibles, para que
        quien llame pueda decidir si usa solo el pipeline viejo como respaldo.
        """
        if not self.ecogrid_ai_loaded:
            return None

        buf = self._buffers.setdefault(device_id, {"timestamps": deque(maxlen=BUFFER_WINDOW), "corrientes": deque(maxlen=BUFFER_WINDOW)})
        buf["timestamps"].append(timestamp_iso)
        buf["corrientes"].append(current)

        try:
            resultado = pipeline_analizar(
                self.ecogrid_ai,
                list(buf["timestamps"]),
                list(buf["corrientes"]),
                timestamp_iso,
            )
            return resultado
        except Exception as exc:
            print(f"[AI_SERVICE] ERROR en pipeline_analizar: {exc}")
            return None

    def classify_maintenance_text(self, text):
        """Clasifica severidad de reporte de falla o bitácora técnica (texto libre, ruta manual)."""
        if not self.text_mining_loaded:
            return {
                "input_text": text,
                "predicted_severity": "Moderado",
                "confidence": 0.70,
                "recommended_action": "Modelo no cargado. Revisión técnica manual recomendada.",
                "requires_shutdown": False,
            }
        return self.text_mining_classifier.classify_log(text)

    def get_text_mining_metrics(self):
        """Retorna las métricas académicas (Accuracy, F1-Score)."""
        return self.text_mining_classifier.metrics


# Instancia singleton del servicio de IA
ai_service = AIService()