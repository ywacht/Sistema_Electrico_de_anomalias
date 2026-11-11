"""
EcoGrid AI - Servicio de Inferencia de Inteligencia Artificial
Asignatura: Fundamentos de IA & Minería de Texto
Universidad Tecnológica de Calvillo (UTC)
"""

import os
import sys

# Asegurar importación de ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_engine.models.consumption_classifier import EcoGridConsumptionPredictor
from ai_engine.models.text_mining_classifier import IncidentTextMiningClassifier


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

    def evaluate_telemetry(self, voltage, current, active_power, reactive_power, power_factor, frequency, thd, temp, model_name="neural_network"):
        """
        Clasifica una lectura eléctrica instantánea y determina si procede corte automático.
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

    def classify_maintenance_text(self, text):
        """Clasifica severidad de reporte de falla o bitácora técnica."""
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
