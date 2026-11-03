"""
EcoGrid AI - Genetic Algorithm Optimizer
Optimización de hiperparámetros para modelos supervisados (KNN, SVM, Red Neuronal)
Asignatura: Fundamentos de IA
Universidad Tecnológica de Calvillo (UTC)
"""

import random
import numpy as np
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier


class GeneticHyperparameterOptimizer:
    """
    Algoritmo Genético para optimizar hiperparámetros de modelos de clasificación
    de patrones de consumo eléctrico.
    
    Implementa:
    - Inicialización aleatoria de población
    - Función de aptitud (Fitness) basada en Cross-Validation (F1-macro o Accuracy)
    - Selección por Ruleta / Torneo
    - Cruzamiento (Crossover)
    - Mutación adaptativa
    - Elitismo (conserva los mejores individuos)
    """

    def __init__(
        self,
        model_type="knn",
        population_size=16,
        generations=10,
        mutation_rate=0.15,
        crossover_rate=0.8,
        cv_folds=3,
        random_state=42,
    ):
        self.model_type = model_type.lower()
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.best_individual = None
        self.best_score = -1.0
        self.history = []

        # Espacios de búsqueda de hiperparámetros según el modelo
        self.param_grid = {
            "knn": {
                "n_neighbors": list(range(1, 25)),
                "weights": ["uniform", "distance"],
                "metric": ["euclidean", "manhattan", "minkowski"],
                "p": [1, 2],
            },
            "svm": {
                "C": [0.01, 0.1, 1.0, 5.0, 10.0, 50.0, 100.0],
                "kernel": ["linear", "rbf", "poly", "sigmoid"],
                "gamma": ["scale", "auto", 0.001, 0.01, 0.1, 1.0],
            },
            "neural_network": {
                "hidden_layer_sizes": [
                    (16,),
                    (32,),
                    (64,),
                    (32, 16),
                    (64, 32),
                    (128, 64),
                ],
                "activation": ["relu", "tanh"],
                "alpha": [0.0001, 0.001, 0.01, 0.1],
                "learning_rate_init": [0.001, 0.005, 0.01],
                "max_iter": [300],
            },
        }

    def _random_chromosome(self):
        """Genera un cromosoma aleatorio según el tipo de modelo."""
        specs = self.param_grid[self.model_type]
        chromosome = {}
        for param, values in specs.items():
            chromosome[param] = random.choice(values)
        return chromosome

    def _create_model(self, chromosome):
        """Instancia el estimador correspondiente con los hiperparámetros del cromosoma."""
        if self.model_type == "knn":
            p = chromosome.get("p", 2)
            if chromosome["metric"] != "minkowski":
                p = 2
            return KNeighborsClassifier(
                n_neighbors=chromosome["n_neighbors"],
                weights=chromosome["weights"],
                metric=chromosome["metric"],
                p=p,
            )
        elif self.model_type == "svm":
            return SVC(
                C=chromosome["C"],
                kernel=chromosome["kernel"],
                gamma=chromosome["gamma"],
                random_state=self.random_state,
            )
        elif self.model_type == "neural_network":
            return MLPClassifier(
                hidden_layer_sizes=chromosome["hidden_layer_sizes"],
                activation=chromosome["activation"],
                alpha=chromosome["alpha"],
                learning_rate_init=chromosome["learning_rate_init"],
                max_iter=chromosome.get("max_iter", 300),
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Modelo desconocido: {self.model_type}")

    def _fitness(self, chromosome, X, y):
        """Evalúa el desempeño del individuo mediante validación cruzada."""
        try:
            model = self._create_model(chromosome)
            scores = cross_val_score(model, X, y, cv=self.cv_folds, scoring="accuracy")
            return float(np.mean(scores))
        except Exception:
            return 0.0

    def _crossover(self, parent1, parent2):
        """Cruzamiento uniforme entre dos cromosomas."""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        child1 = {}
        child2 = {}
        for key in parent1:
            if random.random() < 0.5:
                child1[key] = parent1[key]
                child2[key] = parent2[key]
            else:
                child1[key] = parent2[key]
                child2[key] = parent1[key]
        return child1, child2

    def _mutate(self, chromosome):
        """Mutación aleatoria sobre los genes del individuo."""
        mutated = chromosome.copy()
        specs = self.param_grid[self.model_type]
        for key, values in specs.items():
            if random.random() < self.mutation_rate:
                mutated[key] = random.choice(values)
        return mutated

    def _tournament_selection(self, population, fitnesses, k=3):
        """Selección por torneo."""
        selected_indices = random.sample(range(len(population)), min(k, len(population)))
        best_idx = max(selected_indices, key=lambda idx: fitnesses[idx])
        return population[best_idx]

    def optimize(self, X, y, verbose=True):
        """
        Ejecuta el ciclo generacional del Algoritmo Genético.
        Retorna:
            best_params: dict con los mejores hiperparámetros encontrados
            best_score: mejor puntaje de exactitud obtenido
        """
        random.seed(self.random_state)
        np.random.seed(self.random_state)

        # 1. Población inicial
        population = [self._random_chromosome() for _ in range(self.population_size)]
        self.history = []

        for gen in range(self.generations):
            fitnesses = [self._fitness(ind, X, y) for ind in population]

            # Encontrar el mejor de la generación
            gen_best_idx = int(np.argmax(fitnesses))
            gen_best_score = fitnesses[gen_best_idx]
            gen_best_ind = population[gen_best_idx]

            if gen_best_score > self.best_score:
                self.best_score = gen_best_score
                self.best_individual = gen_best_ind.copy()

            avg_fitness = float(np.mean(fitnesses))
            self.history.append({
                "generation": gen + 1,
                "best_fitness": gen_best_score,
                "avg_fitness": avg_fitness,
                "best_params": gen_best_ind,
            })

            if verbose:
                print(
                    f"[{self.model_type.upper()}] Generación {gen + 1}/{self.generations} "
                    f"- Mejor Score: {gen_best_score:.4f} - Promedio: {avg_fitness:.4f}"
                )

            # 2. Elitismo: conservar los mejores 2 individuos
            sorted_indices = np.argsort(fitnesses)[::-1]
            next_population = [
                population[sorted_indices[0]].copy(),
                population[sorted_indices[1]].copy(),
            ]

            # 3. Reproducción: Selección, Cruzamiento y Mutación
            while len(next_population) < self.population_size:
                parent1 = self._tournament_selection(population, fitnesses)
                parent2 = self._tournament_selection(population, fitnesses)
                child1, child2 = self._crossover(parent1, parent2)
                next_population.append(self._mutate(child1))
                if len(next_population) < self.population_size:
                    next_population.append(self._mutate(child2))

            population = next_population

        if verbose:
            print(f"\n[GA FINAL - {self.model_type.upper()}] Mejor Score Global: {self.best_score:.4f}")
            print(f"Mejores Hiperparámetros: {self.best_individual}\n")

        return self.best_individual, self.best_score
