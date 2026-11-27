# EcoGrid AI - modelos exportados (guía para otra IA / desarrollador)

**Qué hace:** a partir de la CORRIENTE DC (A) de un ESP32+ACS712 completa datos faltantes, estima potencia/energía,
anticipa picos, detecta anomalías, escribe una bitácora y asigna severidad `Leve | Moderado | Crítico`.
`Crítico` => desconectar el módulo.

## Archivos
| Archivo | Contenido |
|---|---|
| `modelo1_completador.joblib` | Modelo 1: completa huecos de corriente + energía |
| `modelo2_picos_anomalias.joblib` | Modelo 2: predicción de picos y anomalías |
| `modelo3_bitacora.joblib` | Modelo 3: minería de texto -> severidad |
| `config.json` | Umbrales (V_BUS, I_NOM, I_ALERTA, I_CRITICA...), mapeo nivel->severidad, versiones |
| `contrato_io.json` | **Campos de entrada/salida + ejemplos reales de cada modelo** (léelo primero) |
| `ecogrid_ai.py` | Código de las clases (los .joblib lo necesitan importable) |

## Uso mínimo
```python
from ecogrid_ai import cargar_modelos, modelo1_completar, modelo2_predecir, modelo3_clasificar, pipeline_analizar
IA = cargar_modelos("modelos_exportados")                      # carga los 3 modelos y los umbrales
modelo1_completar(IA.completador, [0.43, None, None, 0.44])     # -> serie completa + energía
modelo2_predecir(IA.m2, lista_corrientes)                       # -> prob_pico, anomalia, i_futura_max_A
modelo3_clasificar(IA.bitacora, ["texto de bitácora"])          # -> nivel + predicted_severity
pipeline_analizar(IA, timestamps_s, corrientes_A, "2026-11-24 10:00:00")   # -> salida para el backend
```

## Reglas importantes
- `predicted_severity` es string (`Leve`/`Moderado`/`Crítico`); `nivel` es 1/2/3.
- `regla_dura=true` significa corriente >= I_CRITICA: se corta sin importar la IA.
- Tras reconectar la carga usar `gracia=true` ~5 s (corriente de arranque del motor).
- Los modelos se entrenaron con datos SINTÉTICOS: reentrenar con telemetría real (`EcoGridAI().entrenar(serie_real)` y `exportar_modelos`).
- Compatibilidad: exportado con Python 3.13.18, scikit-learn 1.6.1, numpy 2.4.6, pandas 2.2.3.
  Si la versión de scikit-learn difiere, vuelve a entrenar y exportar en tu entorno.
