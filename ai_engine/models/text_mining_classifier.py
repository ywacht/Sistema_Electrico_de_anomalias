"""
EcoGrid AI - Minería de Texto para Reportes de Fallas y Bitácoras Eléctricas
Asignatura: Minería de Texto (IA)
Universidad Tecnológica de Calvillo (UTC)

Clasificación de incidentes no estructurados en 4 niveles de severidad:
- Baja: Mantenimientos rutinarios, inspecciones preventivas, ajustes menores.
- Media: Variaciones intermitentes, vibraciones leves, ruido eléctrico, armónicos moderados.
- Alta: Sobrecalentamiento significativo, fallas de relés de protección, desbalances severos.
- Crítica: Arcos eléctricos, conatos de incendio, cortocircuitos trifásicos, explosiones.

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
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score


SEVERITY_LEVELS = ["Baja", "Media", "Alta", "Crítica"]

# Base enriquecida de incidentes para entrenamiento robusto
BASE_INCIDENTS = {
    "Baja": [
        "Inspección visual periódica de barrajes y limpieza de polvo en tablero principal sin novedades.",
        "Reemplazo programado de fusibles de maniobra y ajuste preventivo de tornillería en bornera.",
        "Monitoreo rutinario de banco de baterías para UPS, niveles de electrolito correctos.",
        "Revisión semestral de puesta a tierra, resistencia medida en 4.2 ohms dentro de norma oficial.",
        "Mantenimiento preventivo ordinario en tablero secundario de iluminación y contactos.",
        "Limpieza de filtros de aire y verificación de ventilación en gabinete de control.",
        "Lectura rutinaria mensual de medidores fiscales de energía sin registrar desviaciones.",
        "Cambio de focos piloto indicadores de presencia de fase en panel de distribución.",
        "Ajuste de par de apriete en zapatas de acometida según manual de fabricante.",
        "Etiquetado y peinado de cableado de control en canaleta de tablero de transferencia.",
        "Inspección periódica del aislamiento externo de transformador tipo pedestal.",
        "Prueba preventiva sin carga de la planta de emergencia a diésel por 15 minutos.",
        "Reemplazo de cubiertas acrílicas de protección contra contacto accidental en tablero.",
        "Verificación de señalización de seguridad y señalética de peligro alta tensión.",
        "Registro de lecturas de tensión y corriente en bitácora de turno matutino.",
    ],
    "Media": [
        "Zumbido anormal y vibración moderada en contactor electromagnético del compresor 3.",
        "Fluctuación intermitente de tensión de 120V a 108V al arrancar molino principal.",
        "Lectura de armónicos THD en corriente del 14% en variador de velocidad tablero 4.",
        "Disparo esporádico del guardamotor por descalibración del dial térmico durante turno nocturno.",
        "Falso contacto intermitente en borna de neutro causando parpadeo en luminarias industriales.",
        "Elevación moderada de temperatura en borne de interruptor termomagnético marcado a 48°C.",
        "Desgaste incipiente de escobillas en motor sincrónico de ventilación auxiliar.",
        "Presión diferencial baja en sistema de enfriamiento de transformador seco de 75kVA.",
        "Disparo por sobrecorriente transitoria al conectar banco de condensadores desintonizado.",
        "Humedad detectada en canalización subterránea de alimentación a caseta de bombeo.",
        "Desviación menor del factor de potencia cayendo a 0.82 durante arranque de enfriadores.",
        "Oscilación periódica de frecuencia entre 59.6 y 60.3 Hz en barra secundaria.",
        "Fuga leve de grasa en chumaceras del motor de trituración secundaria.",
        "Alarma de advertencia por sobrecarga leve del 108% en alimentador B2.",
        "Ruido de conmutación en tiristores del banco de compensación estática de reactivos.",
    ],
    "Alta": [
        "Termografía revela punto caliente crítico a 92°C en empalme de fase C del alimentador principal.",
        "Falla de disparo en relé de sobrecorriente 50/51, línea de producción operando sin protección.",
        "Desbalance severo de fases mayor al 35% con recalentamiento en devanados del motor de 150HP.",
        "Pérdida de aislamiento dieléctrico en cable de media tensión 13.8kV, resistencia en 15 megaohms.",
        "Sobrecorriente continua del 140% por atasco mecánico, disparo demorado de la protección principal.",
        "Fuga a tierra de 8.5 amperios detectada en barraje de distribución general de planta.",
        "Goteo de aceite dieléctrico en empaque de transformador principal de potencia de 500kVA.",
        "Bloqueo del actuador mecánico del disyuntor en vacío, incapacidad de corte remoto.",
        "Falla en el regulador automático de voltaje (AVR) provocando sobretensión sostenida de 145V.",
        "Disparo por falla a tierra intermitente con olor a baquelita quemada en CCM 2.",
        "Calentamiento excesivo a 105°C en cuchillas desconectadoras de subestación compacta.",
        "Disparo reiterado del interruptor de potencia por sobretemperatura en bobina de disparo.",
        "Falla en la protección diferencial de línea 87L detectada en prueba de inyección secundaria.",
        "Deterioro grave de terminales de potencia por corrosión galvánica severa en cuarto húmedo.",
        "Sobrecarga prolongada al 125% con humo ligero saliendo de la ventilación del transformador.",
    ],
    "Crítica": [
        "Explosión por arco eléctrico en celda de media tensión con expulsión de gases y humo denso.",
        "Cortocircuito trifásico franco en barraje principal, disyuntor general abierto por disparo instantáneo.",
        "Conato de incendio activo en banco de condensadores con derretimiento de aisladores.",
        "Disparo total de subestación por falla catastrófica de transformador con derrame de aceite caliente.",
        "Contacto accidental con barra energizada de 480V con quemaduras y apertura de seccionadores de emergencia.",
        "Ruptura dieléctrica violenta en boquilla de alta tensión con caída de fases a tierra.",
        "Incendio en canalización principal de cables con emisión de vapores tóxicos en cuarto de control.",
        "Falla simultánea de protecciones diferenciales y disparo general por cortocircuito no despejado.",
        "Explosión de celda de seccionamiento por descarga atmosférica sin supresor TVSS operativo.",
        "Colapso total de acometida por caída de poste y corte transversal de cables conductores vivos.",
        "Arco eléctrico masivo en barra colectora principal causando apagón total en planta industrial.",
        "Explosión violenta de transformador de potencial TP de 23kV con proyección de fragmentos.",
        "Incendio descontrolado en cuarto de interruptores de potencia por sobrecalentamiento extremo.",
        "Flashover en aisladores de entrada de subestación provocando caída del suministro general.",
        "Cortocircuito bifásico franco con fusión de conductores de cobre en acometida de fuerza.",
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
        """Genera dataset expandido con variantes semánticas y de orden."""
        texts = []
        labels = []

        for severity, sentences in BASE_INCIDENTS.items():
            for s in sentences:
                cleaned = clean_spanish_text(s)
                texts.append(cleaned)
                labels.append(severity)
                texts.append(clean_spanish_text(f"Reporte de turno: {s}"))
                labels.append(severity)
                texts.append(clean_spanish_text(f"Atención en línea: {s}"))
                labels.append(severity)
                texts.append(clean_spanish_text(f"Incidente registrado en subestación: {s}"))
                labels.append(severity)

        return texts, labels

    def train_and_evaluate(self, test_size=0.25, random_state=42):
        """Entrena el clasificador y calcula exactitud y F1-score."""
        texts, labels = self.build_dataset()
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=test_size, random_state=random_state, stratify=labels
        )

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
            "Baja": "Continuar con el programa preventivo habitual. No requiere interrupción del suministro.",
            "Media": "Programar inspección en el próximo cambio de turno. Monitorear vibración y temperatura.",
            "Alta": "Alerta operativa. Coordinar mantenimiento correctivo prioritario y redistribuir carga.",
            "Crítica": "ACCIÓN DE EMERGENCIA. Ejecutar desconexión inmediata de cargas y aislar sector afectado.",
        }

        return {
            "input_text": text,
            "cleaned_text": cleaned,
            "predicted_severity": predicted_severity,
            "confidence": prob_dict.get(predicted_severity, 0.95),
            "class_probabilities": prob_dict,
            "keywords": keywords,
            "recommended_action": recommendations.get(predicted_severity, ""),
            "requires_shutdown": predicted_severity in ["Alta", "Crítica"],
        }
