"""
EcoGrid AI - Script Principal de Entrenamiento de Modelos
Ejecuta la optimización con Algoritmos Genéticos y entrena:
1. Clasificadores de patrones de consumo (KNN, SVM, Red Neuronal, K-Means, SOM)
2. Modelo de Minería de Texto sobre bitácoras de incidentes eléctricos

Asignaturas: Fundamentos de IA & Minería de Texto
Universidad Tecnológica de Calvillo (UTC)
"""

import sys
import os
import json
import numpy as np
from sklearn.model_selection import train_test_split

# Añadir ruta raíz al path de importación
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_engine.genetic.genetic_optimizer import GeneticHyperparameterOptimizer
from ai_engine.models.consumption_classifier import (
    EcoGridConsumptionPredictor,
    generate_synthetic_electrical_data,
)
from ai_engine.models.text_mining_classifier import IncidentTextMiningClassifier


def main():
    print("=" * 75)
    print("    ECOGRID AI - ENTRENAMIENTO DE MODELOS DE INTELIGENCIA ARTIFICIAL")
    print("    Universidad Tecnológica de Calvillo (UTC) - 7mo Cuatrimestre")
    print("=" * 75)

    saved_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "saved"))
    os.makedirs(saved_dir, exist_ok=True)

    # -------------------------------------------------------------
    # 1. GENERACIÓN DE DATOS DE TELEMETRÍA ELÉCTRICA
    # -------------------------------------------------------------
    print("\n[1/4] Generando conjunto de datos de consumo eléctrico...")
    X, y = generate_synthetic_electrical_data(n_samples=2400, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"      Total de muestras: {len(X)} (Train: {len(X_train)}, Test: {len(X_test)})")
    print(f"      Variables por muestra: {X.shape[1]} (V, I, P_act, P_react, FP, Freq, THD, Temp)")

    # -------------------------------------------------------------
    # 2. OPTIMIZACIÓN MEDIANTE ALGORITMOS GENÉTICOS
    # -------------------------------------------------------------
    print("\n[2/4] Ejecutando Algoritmo Genético para optimizar hiperparámetros...")
    ga_params = {}

    for model_name in ["knn", "svm", "neural_network"]:
        print(f"\n      --- Optimizando {model_name.upper()} con Algoritmo Genético ---")
        ga = GeneticHyperparameterOptimizer(
            model_type=model_name,
            population_size=10,
            generations=6,
            mutation_rate=0.2,
            crossover_rate=0.8,
            cv_folds=3,
            random_state=42,
        )
        best_p, best_s = ga.optimize(X_train, y_train, verbose=True)
        ga_params[model_name] = best_p
        print(f"      -> {model_name.upper()} Óptimo: Score = {best_s:.4f} | Parámetros: {best_p}")

    # Guardar hiperparámetros óptimos en JSON
    ga_results_file = os.path.join(saved_dir, "ga_optimized_hyperparameters.json")
    with open(ga_results_file, "w", encoding="utf-8") as f:
        json.dump(ga_params, f, indent=2)
    print(f"\n      Hiperparámetros guardados en: {ga_results_file}")

    # -------------------------------------------------------------
    # 3. ENTRENAMIENTO DE MODELOS DE CONSUMO (SUPERVISADO + NO SUPERVISADO)
    # -------------------------------------------------------------
    print("\n[3/4] Entrenando modelos de consumo (KNN, SVM, MLP, KMeans, SOM)...")
    consumption_predictor = EcoGridConsumptionPredictor(models_dir=saved_dir)
    results = consumption_predictor.fit_and_evaluate(
        X_train, y_train, X_test, y_test, ga_params=ga_params
    )
    consumption_predictor.save()

    print("\n      Resultados de Evaluación en Conjunto de Prueba:")
    for model_name, metrics in results.items():
        print(f"      - {model_name.upper():16} | Exactitud: {metrics['accuracy'] * 100:.2f}% | F1-Score: {metrics['f1_score']:.4f}")

    eval_file = os.path.join(saved_dir, "consumption_models_evaluation.json")
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # -------------------------------------------------------------
    # 4. ENTRENAMIENTO DE MINERÍA DE TEXTO (BITÁCORAS DE FALLAS)
    # -------------------------------------------------------------
    print("\n[4/4] Entrenando modelo de Minería de Texto sobre reportes de incidentes...")
    text_classifier = IncidentTextMiningClassifier(models_dir=saved_dir)
    text_metrics = text_classifier.train_and_evaluate(test_size=0.25, random_state=42)
    text_classifier.save()

    print(f"      - Exactitud (Accuracy):  {text_metrics['accuracy'] * 100:.2f}%")
    print(f"      - F1-Score (Macro):      {text_metrics['f1_score_macro']:.4f}")
    print(f"      - F1-Score (Ponderado):  {text_metrics['f1_score_weighted']:.4f}")

    print("\n" + "=" * 75)
    print("    ¡ENTRENAMIENTO COMPLETADO EXITOSAMENTE!")
    print(f"    Todos los artefactos y modelos se almacenaron en: {saved_dir}")
    print("=" * 75)


if __name__ == "__main__":
    main()
