"""
EcoGrid AI - Modelos de Clasificación de Patrones de Consumo Eléctrico
Asignatura: Fundamentos de IA
Universidad Tecnológica de Calvillo (UTC)

Modelos implementados:
- Supervisados: Redes Neuronales (MLP), K-Nearest Neighbors (KNN), Support Vector Machine (SVM)
- No Supervisados: K-Means, Self-Organizing Maps (SOM / Kohonen)
- Optimizados mediante Algoritmos Genéticos
"""

import numpy as np
import joblib
import os
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score


class SimpleSOM:
    """
    Implementación en NumPy de un Mapa Autoorganizado de Kohonen (Self-Organizing Map - SOM)
    para el agrupamiento no supervisado de patrones de consumo eléctrico en una rejilla 2D.
    """

    def __init__(self, x_dim=5, y_dim=5, input_dim=8, lr=0.5, sigma=1.5, n_epochs=100, random_state=42):
        self.x_dim = x_dim
        self.y_dim = y_dim
        self.input_dim = input_dim
        self.lr_initial = lr
        self.sigma_initial = sigma
        self.n_epochs = n_epochs
        self.random_state = random_state
        
        np.random.seed(random_state)
        # Inicialización de pesos de la cuadrícula SOM (x_dim, y_dim, input_dim)
        self.weights = np.random.uniform(-1.0, 1.0, (x_dim, y_dim, input_dim))
        
        # Coordenadas de las neuronas en la rejilla
        self.grid_coords = np.array([[[i, j] for j in range(y_dim)] for i in range(x_dim)])

    def _get_bmu(self, x):
        """Best Matching Unit: encuentra la neurona más cercana al vector x."""
        diff = self.weights - x
        dist_sq = np.sum(diff ** 2, axis=2)
        bmu_idx = np.unravel_index(np.argmin(dist_sq), (self.x_dim, self.y_dim))
        return bmu_idx

    def fit(self, X):
        """Entrena la red SOM actualizando los pesos de la neurona ganadora y sus vecinas."""
        n_samples = len(X)
        for epoch in range(self.n_epochs):
            # Decaimiento exponencial de la tasa de aprendizaje y el radio de vecindad
            lr = self.lr_initial * np.exp(-epoch / self.n_epochs)
            sigma = self.sigma_initial * np.exp(-epoch / self.n_epochs)
            sigma_sq_2 = 2 * (sigma ** 2)

            # Barajar muestras en cada época
            indices = np.random.permutation(n_samples)
            for idx in indices:
                x = X[idx]
                bmu = self._get_bmu(x)

                # Calcular distancias en la rejilla hacia la BMU
                dist_to_bmu = np.sum((self.grid_coords - bmu) ** 2, axis=2)
                # Función de vecindad gaussiana
                neighborhood = np.exp(-dist_to_bmu / (sigma_sq_2 + 1e-9))

                # Actualización de pesos: W = W + lr * h * (x - W)
                delta = x - self.weights
                self.weights += lr * neighborhood[:, :, np.newaxis] * delta

        return self

    def predict(self, X):
        """Asigna a cada muestra un identificador de cluster basado en la neurona BMU."""
        clusters = []
        for x in X:
            bmu = self._get_bmu(x)
            # Mapear coordenada 2D a índice escalar
            cluster_id = bmu[0] * self.y_dim + bmu[1]
            clusters.append(cluster_id)
        return np.array(clusters)


def generate_synthetic_electrical_data(n_samples=2000, random_state=42):
    """
    Genera un conjunto de datos realista de telemetría eléctrica para monitoreo residencial/industrial.
    
    Características (8 variables continuas):
    1. voltage_rms (V)       [110V - 130V / 210V - 230V]
    2. current_rms (A)       [0.5A - 40A]
    3. active_power (W)      [V * I * fp]
    4. reactive_power (VAR)  [V * I * sin(acos(fp))]
    5. power_factor          [0.60 - 0.99]
    6. frequency (Hz)        [59.5 - 60.5]
    7. thd_current (%)       [Total Harmonic Distortion 1% - 30%]
    8. temp_celsius (°C)     [25°C - 85°C]

    Clases objetivo (4 patrones de consumo):
    0: 'Normal' (Consumo dentro de parámetros operativos)
    1: 'Pico de Demanda' (Alta corriente y potencia activa en horario pico)
    2: 'Sobrecarga / Anomalía' (Corriente excesiva, disparo térmico o THD elevada -> activa desconexión)
    3: 'Fuga / Parásito' (Baja corriente continua con factor de potencia deficiente fuera de horario)
    """
    np.random.seed(random_state)
    n_per_class = n_samples // 4

    # Clase 0: Normal
    v_norm = np.random.normal(120.0, 2.5, n_per_class)
    i_norm = np.random.uniform(2.0, 10.0, n_per_class)
    pf_norm = np.random.uniform(0.90, 0.98, n_per_class)
    f_norm = np.random.normal(60.0, 0.1, n_per_class)
    thd_norm = np.random.uniform(2.0, 5.0, n_per_class)
    temp_norm = np.random.normal(32.0, 3.0, n_per_class)

    # Clase 1: Pico de Demanda
    v_pico = np.random.normal(118.0, 3.0, n_per_class)
    i_pico = np.random.uniform(18.0, 28.0, n_per_class)
    pf_pico = np.random.uniform(0.85, 0.95, n_per_class)
    f_pico = np.random.normal(59.9, 0.2, n_per_class)
    thd_pico = np.random.uniform(4.0, 9.0, n_per_class)
    temp_pico = np.random.normal(48.0, 4.0, n_per_class)

    # Clase 2: Sobrecarga / Anomalía (Riesgo inminente -> Desconexión de cargas)
    v_over = np.random.normal(112.0, 6.0, n_per_class)
    i_over = np.random.uniform(32.0, 55.0, n_per_class)
    pf_over = np.random.uniform(0.65, 0.85, n_per_class)
    f_over = np.random.normal(59.4, 0.4, n_per_class)
    thd_over = np.random.uniform(12.0, 28.0, n_per_class)
    temp_over = np.random.normal(72.0, 6.0, n_per_class)

    # Clase 3: Fuga / Pérdida Parásita
    v_leak = np.random.normal(121.0, 2.0, n_per_class)
    i_leak = np.random.uniform(0.8, 3.5, n_per_class)
    pf_leak = np.random.uniform(0.50, 0.75, n_per_class)
    f_leak = np.random.normal(60.0, 0.1, n_per_class)
    thd_leak = np.random.uniform(8.0, 18.0, n_per_class)
    temp_leak = np.random.normal(30.0, 2.0, n_per_class)

    V = np.concatenate([v_norm, v_pico, v_over, v_leak])
    I = np.concatenate([i_norm, i_pico, i_over, i_leak])
    PF = np.concatenate([pf_norm, pf_pico, pf_over, pf_leak])
    F = np.concatenate([f_norm, f_pico, f_over, f_leak])
    THD = np.concatenate([thd_norm, thd_pico, thd_over, thd_leak])
    TEMP = np.concatenate([temp_norm, temp_pico, temp_over, temp_leak])

    P_active = V * I * PF
    P_reactive = V * I * np.sqrt(np.clip(1.0 - PF ** 2, 0.0, 1.0))

    X = np.column_stack([V, I, P_active, P_reactive, PF, F, THD, TEMP])
    y = np.concatenate([
        np.zeros(n_per_class, dtype=int),
        np.ones(n_per_class, dtype=int),
        np.full(n_per_class, 2, dtype=int),
        np.full(n_per_class, 3, dtype=int),
    ])

    return X, y


CLASS_NAMES = {
    0: "Normal",
    1: "Pico de Demanda",
    2: "Sobrecarga / Anomalía",
    3: "Fuga / Consumo Parásito",
}


class EcoGridConsumptionPredictor:
    """
    Suite unificada de modelos supervisados y no supervisados para EcoGrid AI.
    Permite predecir patrones de consumo y emitir señales de corte automático de carga.
    """

    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(__file__), "saved")
        self.models_dir = models_dir
        self.scaler = None
        self.models = {}
        self.active_model_name = "neural_network"

    def fit_and_evaluate(self, X_train, y_train, X_test, y_test, ga_params=None):
        """Entrena y evalúa KNN, SVM, MLP, KMeans y SOM."""
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        if ga_params is None:
            ga_params = {}

        # 1. KNN
        knn_params = ga_params.get("knn", {"n_neighbors": 5, "weights": "distance"})
        knn = KNeighborsClassifier(**knn_params)
        knn.fit(X_train_scaled, y_train)
        self.models["knn"] = knn

        # 2. SVM
        svm_params = ga_params.get("svm", {"C": 10.0, "kernel": "rbf", "gamma": "scale"})
        svm = SVC(probability=True, random_state=42, **svm_params)
        svm.fit(X_train_scaled, y_train)
        self.models["svm"] = svm

        # 3. Red Neuronal (MLP)
        mlp_params = ga_params.get(
            "neural_network",
            {"hidden_layer_sizes": (64, 32), "activation": "relu", "max_iter": 400, "alpha": 0.001},
        )
        mlp = MLPClassifier(random_state=42, **mlp_params)
        mlp.fit(X_train_scaled, y_train)
        self.models["neural_network"] = mlp

        # 4. K-Means (No supervisado)
        kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        kmeans.fit(X_train_scaled)
        self.models["kmeans"] = kmeans

        # 5. SOM (No supervisado)
        som = SimpleSOM(x_dim=4, y_dim=4, input_dim=8, n_epochs=50, random_state=42)
        som.fit(X_train_scaled)
        self.models["som"] = som

        # Reporte de métricas
        results = {}
        for name in ["knn", "svm", "neural_network"]:
            clf = self.models[name]
            y_pred = clf.predict(X_test_scaled)
            acc = float(accuracy_score(y_test, y_pred))
            f1 = float(f1_score(y_test, y_pred, average="weighted"))
            results[name] = {
                "accuracy": acc,
                "f1_score": f1,
                "report": classification_report(y_test, y_pred, target_names=[CLASS_NAMES[i] for i in range(4)], output_dict=True),
                "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            }

        return results

    def save(self):
        """Persiste los modelos entrenados y el scaler a disco."""
        os.makedirs(self.models_dir, exist_ok=True)
        joblib.dump(self.scaler, os.path.join(self.models_dir, "consumption_scaler.joblib"))
        for name, model in self.models.items():
            joblib.dump(model, os.path.join(self.models_dir, f"{name}_model.joblib"))

    def load(self):
        """Carga los modelos entrenados desde disco."""
        scaler_path = os.path.join(self.models_dir, "consumption_scaler.joblib")
        if not os.path.exists(scaler_path):
            return False
        self.scaler = joblib.load(scaler_path)
        for name in ["knn", "svm", "neural_network", "kmeans", "som"]:
            path = os.path.join(self.models_dir, f"{name}_model.joblib")
            if os.path.exists(path):
                self.models[name] = joblib.load(path)
        return True

    def predict(self, feature_vector, model_name=None):
        """
        Clasifica un vector de telemetría de 8 valores:
        [voltage, current, active_power, reactive_power, power_factor, frequency, thd, temp]
        
        Retorna:
            dict con class_id, class_name, should_disconnect, probabilities
        """
        if model_name is None:
            model_name = self.active_model_name

        if self.scaler is None or model_name not in self.models:
            raise RuntimeError(f"El modelo '{model_name}' no se encuentra cargado.")

        vector = np.array(feature_vector, dtype=float).reshape(1, -1)
        scaled = self.scaler.transform(vector)
        model = self.models[model_name]

        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(scaled)[0].tolist()
        else:
            probs = []

        class_id = int(model.predict(scaled)[0])
        class_name = CLASS_NAMES.get(class_id, "Desconocido")

        # Política de desconexión automatizada de cargas:
        # Se activa corte si es 'Sobrecarga / Anomalía' (id 2) o si la corriente excede límite crítico
        current = float(feature_vector[1])
        should_disconnect = (class_id == 2) or (current > 35.0)

        return {
            "model_used": model_name,
            "class_id": class_id,
            "class_name": class_name,
            "is_anomaly": class_id in [1, 2],
            "should_disconnect": should_disconnect,
            "action": "AUTOMATIC_DISCONNECT" if should_disconnect else "NORMAL_OPERATION",
            "probabilities": {CLASS_NAMES[i]: round(probs[i], 4) for i in range(len(probs))} if probs else {},
        }
