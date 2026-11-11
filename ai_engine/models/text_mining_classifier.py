"""
EcoGrid AI - Minería de Texto para Reportes de Fallas y Bitácoras Eléctricas
Asignatura: Minería de Texto (IA)
Universidad Tecnológica de Calvillo (UTC)

Clasificación de incidentes no estructurados en 3 niveles de severidad
(mismo esquema acordado para el resto del proyecto: contratos JSON y notebook):
- Crítico: arcos eléctricos, explosiones, incendios, cortocircuitos severos, fallas totales.
- Moderado: fluctuaciones de voltaje, sobrecalentamiento moderado, ruido o vibración anómala.
- Leve: mantenimientos preventivos, inspecciones de rutina, hallazgos sin relevancia.

Reporta métricas de exactitud (Accuracy) y F1-Score.
"""

import os
import re
import json
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score


SEVERITY_LEVELS = ["Crítico", "Moderado", "Leve"]

# Base de incidentes (mismo corpus/vocabulario usado en el notebook de Minería de Texto)
BASE_INCIDENTS = {
    "Crítico": [
        "Explosión parcial en el transformador de la subestación norte, personal evacuado de inmediato por seguridad.",
        "Se detectó arco eléctrico visible en la batería de respaldo, requiere desconexión inmediata.",
        "Explosión parcial en el sistema de puesta a tierra, personal evacuado de inmediato por seguridad.",
        "Se detecta fuga de aceite dieléctrico junto con sobrecalentamiento extremo en el regulador de voltaje, posible explosión inminente.",
        "Se reporta el generador de respaldo con sobrecalentamiento extremo y olor a quemado de forma intermitente desde ayer, riesgo inminente de incendio.",
        "Se detectó arco eléctrico visible en el aislador de la línea aérea, requiere desconexión inmediata.",
        "Se reporta el sistema de puesta a tierra con sobrecalentamiento extremo y olor a quemado de forma intermitente desde ayer, riesgo inminente de incendio.",
        "El regulador de voltaje sufrió daño estructural grave tras descarga eléctrica, riesgo para el personal.",
        "Sobrecarga crítica en el motor del compresor de la planta dejó sin energía a más de 500 usuarios por 45 minutos.",
        "Se reporta el medidor inteligente del sector residencial con sobrecalentamiento extremo y olor a quemado en las últimas 24 horas, riesgo inminente de incendio.",
        "El interruptor automático de línea 3 presenta humo visible y chispas, se activó protocolo de emergencia.",
        "Se detectó arco eléctrico visible en la torre de alta tensión sector sur, requiere desconexión inmediata.",
        "Explosión parcial en el relé de protección, personal evacuado de inmediato por seguridad.",
        "El banco de capacitores presenta humo visible y chispas, se activó protocolo de emergencia.",
        "Falla total en el transformador de distribución zona industrial: sin suministro eléctrico en toda la zona durante el turno nocturno.",
    ],
    "Moderado": [
        "La línea de transmisión 1 tuvo una caída de voltaje momentánea en las últimas 24 horas, se restableció sin intervención.",
        "Se registran fluctuaciones de voltaje en el sistema de puesta a tierra, consumo elevado respecto al promedio.",
        "Temperatura por encima de lo normal en el banco de capacitores, sin señales de daño estructural aún.",
        "El generador de respaldo muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "El cableado subterráneo de la zona comercial muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "La línea de transmisión 1 muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "Consumo elevado y sostenido en la subestación eléctrica central desde hace 6 horas, fuera del rango esperado.",
        "Ruido anómalo (zumbido fuerte) detectado en el banco de capacitores durante la inspección rutinaria.",
        "El interruptor automático de línea 3 muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "Temperatura por encima de lo normal en el medidor inteligente del sector residencial, sin señales de daño estructural aún.",
        "El medidor inteligente del sector residencial muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "Corrosión visible en las conexiones de el interruptor automático de línea 3, funcionamiento aún estable.",
        "La torre de alta tensión sector sur muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "El transformador de distribución zona industrial muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
        "El motor del compresor de la planta muestra desgaste visible en los contactos, aún operativo pero requiere revisión pronto.",
    ],
    "Leve": [
        "Lectura ligeramente fuera de rango en el tablero de distribución del edificio B, dentro de tolerancia aceptable.",
        "Pequeña acumulación de polvo en la línea de transmisión 2, se realizó limpieza sin incidentes.",
        "Se ajustó un tornillo flojo en la batería de respaldo durante inspección programada.",
        "El interruptor automático de línea 3 registra variación mínima de voltaje, considerada normal para la operación.",
        "Inspección visual de el motor del compresor de la planta no encontró anomalías, se continúa con calendario normal.",
        "Se reemplazó un fusible preventivo en la batería de respaldo, sin incidencia en el servicio.",
        "El tablero de distribución del edificio B registra variación mínima de voltaje, considerada normal para la operación.",
        "Mantenimiento preventivo realizado en la línea de transmisión 1 sin hallazgos relevantes.",
        "Se ajustó un tornillo flojo en el regulador de voltaje durante inspección programada.",
        "Limpieza de rutina en el relé de protección, polvo acumulado, sin afectación al funcionamiento.",
        "Chequeo de rutina en la subestación eléctrica central: todos los parámetros dentro de lo esperado.",
        "Revisión rutinaria de el sistema de puesta a tierra sin hallazgos graves, equipo en condiciones normales.",
        "Limpieza de rutina en el sistema de puesta a tierra, polvo acumulado, sin afectación al funcionamiento.",
        "Se reemplazó un fusible preventivo en la línea de transmisión 1, sin incidencia en el servicio.",
        "Inspección visual de el medidor inteligente del sector residencial no encontró anomalías, se continúa con calendario normal.",
    ],
}


def clean_spanish_text(text):
    """Preprocesamiento y normalización de texto técnico en español."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s\náéíóúüñ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class IncidentTextMiningClassifier:
    """
    Clasificador NLP para reportes y bitácoras de incidentes eléctricos.
    Utiliza Pipeline TF-IDF n-gramas + LinearSVC con calibración de confianza.
    """

    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(__file__), "saved")
        self.models_dir = models_dir
        self.pipeline = None
        self.metrics = {}

    def build_dataset(self):
        """
        Genera dataset expandido con variantes semánticas y de orden.

        Cada bitácora base se acompaña de un `group_id`: las 4 variantes que
        se generan a partir de ella (original + 3 prefijos) comparten ese id.
        Esto permite separar train/test por GRUPO en vez de por fila suelta,
        para que variantes casi idénticas de una misma bitácora nunca queden
        repartidas entre entrenamiento y prueba (lo que antes inflaba la
        exactitud de forma artificial).
        """
        texts = []
        labels = []
        groups = []

        group_id = 0
        for severity, sentences in BASE_INCIDENTS.items():
            for s in sentences:
                variantes = [
                    s,
                    f"Reporte de turno: {s}",
                    f"Atención en línea: {s}",
                    f"Incidente registrado en subestación: {s}",
                ]
                for variante in variantes:
                    texts.append(clean_spanish_text(variante))
                    labels.append(severity)
                    groups.append(group_id)
                group_id += 1

        return texts, labels, groups

    def train_and_evaluate(self, test_size=0.25, random_state=42):
        """Entrena el clasificador y calcula exactitud y F1-score."""
        texts, labels, groups = self.build_dataset()

        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
        train_idx, test_idx = next(splitter.split(texts, labels, groups=groups))

        X_train = [texts[i] for i in train_idx]
        X_test = [texts[i] for i in test_idx]
        y_train = [labels[i] for i in train_idx]
        y_test = [labels[i] for i in test_idx]

        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=2500,
                norm="l2",
            )),
            ("classifier", LinearSVC(
                C=1.2,
                class_weight="balanced",
                random_state=random_state,
                dual="auto",
            )),
        ])

        self.pipeline.fit(X_train, y_train)
        y_pred = self.pipeline.predict(X_test)

        acc = float(accuracy_score(y_test, y_pred))
        f1_macro = float(f1_score(y_test, y_pred, average="macro"))
        f1_weighted = float(f1_score(y_test, y_pred, average="weighted"))
        report_dict = classification_report(y_test, y_pred, target_names=SEVERITY_LEVELS, output_dict=True)
        cm = confusion_matrix(y_test, y_pred, labels=SEVERITY_LEVELS).tolist()

        self.metrics = {
            "accuracy": round(acc, 4),
            "f1_score_macro": round(f1_macro, 4),
            "f1_score_weighted": round(f1_weighted, 4),
            "classification_report": report_dict,
            "confusion_matrix": cm,
            "total_samples": len(texts),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "split_strategy": "GroupShuffleSplit por bitácora base (evita fuga entre variantes)",
        }

        return self.metrics

    def save(self):
        """Persiste el modelo y las métricas en disco."""
        os.makedirs(self.models_dir, exist_ok=True)
        model_path = os.path.join(self.models_dir, "text_mining_pipeline.joblib")
        metrics_path = os.path.join(self.models_dir, "text_mining_metrics.json")
        joblib.dump(self.pipeline, model_path)
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)

    def load(self):
        """Carga el modelo y las métricas desde disco."""
        model_path = os.path.join(self.models_dir, "text_mining_pipeline.joblib")
        metrics_path = os.path.join(self.models_dir, "text_mining_metrics.json")
        if not os.path.exists(model_path):
            return False
        self.pipeline = joblib.load(model_path)
        if os.path.exists(metrics_path):
            with open(metrics_path, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)
        return True

    def classify_log(self, text):
        """
        Clasifica una bitácora técnica no estructurada.
        Retorna la severidad predicha, puntuación de decisión, términos clave y acción recomendada.
        """
        if self.pipeline is None:
            raise RuntimeError("El modelo de minería de texto no ha sido inicializado o cargado.")

        cleaned = clean_spanish_text(text)
        predicted_severity = self.pipeline.predict([cleaned])[0]

        clf = self.pipeline.named_steps["classifier"]
        tfidf = self.pipeline.named_steps["tfidf"]
        vec = tfidf.transform([cleaned])
        decision_scores = clf.decision_function(vec)[0]
        exp_scores = np.exp(decision_scores - np.max(decision_scores))
        probs = exp_scores / np.sum(exp_scores)
        prob_dict = {cls: round(float(p), 4) for cls, p in zip(clf.classes_, probs)}

        words = cleaned.split()
        keywords = [w for w in words if len(w) > 4][:6]

        recommendations = {
            "Crítico": "ACCIÓN DE EMERGENCIA. Ejecutar desconexión inmediata de cargas y aislar sector afectado.",
            "Moderado": "Programar inspección en el próximo cambio de turno. Monitorear vibración y temperatura.",
            "Leve": "Continuar con el programa preventivo habitual. No requiere interrupción del suministro.",
        }

        return {
            "input_text": text,
            "cleaned_text": cleaned,
            "predicted_severity": predicted_severity,
            "confidence": prob_dict.get(predicted_severity, 0.95),
            "class_probabilities": prob_dict,
            "keywords": keywords,
            "recommended_action": recommendations.get(predicted_severity, ""),
            "requires_shutdown": predicted_severity == "Crítico",
        }