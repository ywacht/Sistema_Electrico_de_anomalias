"""
ECOGRID AI - Modelos de IA (versión DC: ESP32 + ACS712 + carga controlada)
==========================================================================
Solo se mide CORRIENTE. De ahí se derivan potencia y energía y se evalúa el riesgo.

  Modelo 1  ModeloCompletador        Completa huecos de corriente (interpolación + corrección ML) y
                                     calcula potencia/energía coherentes (P = V_BUS * I).
  Modelo 2  ModeloPicosAnomalias     Predice picos (regresión + clasificador de probabilidad) y detecta
                                     anomalías (Isolation Forest).
  Modelo 3  ModeloBitacora           Minería de texto: redacta la bitácora, la lee con TF-IDF + Regresión
                                     Logística y asigna severidad 1..3 (3 = desconectar módulo).
  EcoGridAI                          Orquesta los 3 modelos. API estable para Flask:
                                         IA = EcoGridAI().entrenar();  IA.analizar(ts, vals, ts_texto, gracia)
"""
import re
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (HistGradientBoostingRegressor, HistGradientBoostingClassifier, IsolationForest)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix

# ================================ CONFIGURACIÓN ===================================
CFG = dict(
    V_BUS=12.0,       # Voltaje DC de la carga (V)                      <-- AJUSTA
    DT=2.2,           # segundos típicos entre telemetrías
    I_NOM=0.60,       # corriente normal máxima de la carga (A)         <-- AJUSTA
    I_ALERTA=0.90,    # potencia elevada (A)
    I_CRITICA=1.30,   # peligrosa (A). Debe ser < umbral local del ESP32
    HORIZONTE=15,     # pasos a futuro para predecir picos
)
NOMBRES = {1: "NIVEL 1 - INFORMATIVO", 2: "NIVEL 2 - ALERTA", 3: "NIVEL 3 - CRITICO"}

# Mapeo nivel numérico -> severidad en texto (compatible con ai_service.py / telemetry.py / Mongo)
NIVEL_A_SEVERIDAD = {
    1: "Leve",
    2: "Moderado",
    3: "Crítico",
}


# ================================ DATOS SINTÉTICOS ================================
def generar_serie(n=20000, seed=0):
    """Serie sintética de una carga DC (ventilador): normal + obstrucciones + picos + ruido anómalo.
    Devuelve (corriente, etiqueta_anomalia). Reemplazar por grabaciones reales cuando existan."""
    r = np.random.default_rng(seed)
    t = np.arange(n)
    i = 0.42 + 0.03 * np.sin(2 * np.pi * t / 400) + r.normal(0, 0.015, n)
    anom = np.zeros(n, int)
    def posiciones(k): return r.choice(np.arange(100, n - 100), k, replace=False)
    for s in posiciones(max(n // 650, 3)):                      # obstrucción parcial
        L = r.integers(20, 60); i[s:s + L] += r.uniform(0.10, 0.35)
    for s in posiciones(max(n // 600, 3)):                      # picos (atasco / rotor frenado)
        L = r.integers(6, 20); i[s:s + L] += r.uniform(0.5, 1.1) * np.hanning(L)
    for s in posiciones(max(n // 1000, 3)):                     # anomalías (oscilación irregular)
        L = r.integers(10, 30); i[s:s + L] += r.normal(0, 0.10, L); anom[s:s + L] = 1
    return pd.Series(np.clip(i, 0, None)), anom


def meter_huecos(i, n_huecos=25, seed=1, largo=(3, 40)):
    """Simula pérdidas de WiFi/HTTP: devuelve (serie con NaN, máscara de huecos)."""
    r = np.random.default_rng(seed)
    obs = i.copy().astype(float); mask = np.zeros(len(i), bool)
    for _ in range(n_huecos):
        L = int(r.integers(*largo)); a = int(r.integers(15, len(i) - L - 15))
        obs.iloc[a:a + L] = np.nan; mask[a:a + L] = True
    return obs, mask


def feats(i):
    """Características usando solo el PASADO (sirven en tiempo real)."""
    f = pd.DataFrame({"i": i})
    f["d1"] = i.diff().fillna(0)
    f["d3"] = i.diff(3).fillna(0)
    f["m6"] = i.rolling(6, min_periods=1).mean()
    f["m30"] = i.rolling(30, min_periods=1).mean()
    f["s6"] = i.rolling(6, min_periods=1).std().fillna(0)
    f["s30"] = i.rolling(30, min_periods=1).std().fillna(0)
    f["max10"] = i.rolling(10, min_periods=1).max()
    f["a6"] = f["d1"].abs().rolling(6, min_periods=1).mean()     # rugosidad: detecta oscilación irregular
    return f


def reconstruir_serie(ts, vals, dt_nom):
    """Inserta NaN donde faltan muestras según los timestamps (huecos de red)."""
    out = []
    for k, v in enumerate(vals):
        if k > 0:
            gap = ts[k] - ts[k - 1]
            if gap > 1.8 * dt_nom:
                out.extend([np.nan] * (int(round(gap / dt_nom)) - 1))
        out.append(v)
    return pd.Series(out, dtype=float)


# ================================ MODELO 1 ========================================
class ModeloCompletador:
    """Completa huecos de corriente. Huecos de >= min_ml muestras: interpolación lineal + corrección
    aprendida (Gradient Boosting sobre el residuo) usando el contexto a ambos lados del hueco."""
    CTX = 10

    def __init__(self, min_ml=3):
        self.min_ml, self.m, self.usar_ml, self.val = min_ml, None, False, {}

    @staticmethod
    def _runs(mask):
        runs, k, n = [], 0, len(mask)
        while k < n:
            if mask[k]:
                j = k
                while j < n and mask[j]: j += 1
                runs.append((k, j)); k = j
            else:
                k += 1
        return runs

    @staticmethod
    def _lineal(seg):
        idx = np.arange(len(seg)); ok = ~np.isnan(seg)
        return np.interp(idx, idx[ok], seg[ok])

    def _feat_run(self, lin, a, b):
        L, R = lin[max(0, a - self.CTX):a], lin[b:b + self.CTX]
        n = b - a; pos = (np.arange(n) + 1) / (n + 1)
        base = [n, L[-1], R[0], L[-5:].mean(), R[:5].mean(), L.std(), R.std(), L[-1] - L[-5:].mean(), R[0] - R[:5].mean()]
        return np.column_stack([pos, lin[a:b], np.tile(base, (n, 1))])

    def _muestras(self, v, r, k, lo, hi):
        X, y, lins = [], [], []
        for _ in range(k):
            L = int(r.integers(self.min_ml, 45)); a = int(r.integers(lo + 15, hi - L - 15)); b = a + L
            seg = v[a - 12:b + 12].copy(); seg[12:12 + L] = np.nan
            lin = self._lineal(seg)
            X.append(self._feat_run(lin, 12, 12 + L)); y.append(v[a:b] - lin[12:12 + L])
        return np.vstack(X), np.concatenate(y)

    def fit(self, i_limpia, n_huecos=4000, seed=0):
        """Entrena la corrección ML y la ACTIVA solo si mejora a la interpolación en datos de validación."""
        r = np.random.default_rng(seed); v = i_limpia.values.astype(float); corte = int(len(v) * .7)
        X, y = self._muestras(v, r, n_huecos, 0, corte)
        Xv, yv = self._muestras(v, r, 1500, corte, len(v))
        m = HistGradientBoostingRegressor(max_iter=150, learning_rate=.08, random_state=0).fit(X, y)
        mae_lin, mae_ml = float(np.abs(yv).mean()), float(np.abs(yv - m.predict(Xv)).mean())
        self.usar_ml = mae_ml < 0.98 * mae_lin                    # exige >=2% de mejora para justificar el modelo
        self.val = dict(mae_lineal=mae_lin, mae_ml=mae_ml, usar_ml=self.usar_ml)
        self.m = HistGradientBoostingRegressor(max_iter=150, learning_rate=.08, random_state=0).fit(
            *self._muestras(v, r, n_huecos, 0, len(v))) if self.usar_ml else None
        return self

    def completar(self, s):
        """s: Serie con NaN. Devuelve (serie completa, bandera de imputado 0/1)."""
        v = s.values.astype(float); n = len(v); falt = np.isnan(v)
        if falt.all(): return s.fillna(0.0), falt.astype(int)
        out = self._lineal(v)                                    # interpolación (bordes: valor más cercano)
        if self.m is not None:
            for a, b in self._runs(falt):
                if b - a >= self.min_ml and a >= 1 and b < n:
                    s0, s1 = max(0, a - 12), min(n, b + 12)
                    seg = v[s0:s1]; lin = self._lineal(seg)
                    out[a:b] = np.clip(lin[a - s0:b - s0] + self.m.predict(self._feat_run(lin, a - s0, b - s0)), 0, None)
        return pd.Series(out, index=s.index), pd.Series(falt.astype(int), index=s.index)

    @staticmethod
    def potencia_w(i):
        return CFG["V_BUS"] * i                                   # DC: P = V * I (sin factor de potencia)

    @staticmethod
    def energia_kwh(i, dt=None):
        dt = dt or CFG["DT"]; v = np.asarray(i, float)
        return float(CFG["V_BUS"] * (v.sum() - (v[0] + v[-1]) / 2) * dt / 3.6e6)


# ================================ MODELO 2 ========================================
class ModeloPicosAnomalias:
    COLS_ANOM = ["i", "d1", "d3", "s6", "a6"]

    def fit(self, i):
        H, A = CFG["HORIZONTE"], CFG["I_ALERTA"]
        X = feats(i); n = len(i); corte = int(n * .7)
        fut = i[::-1].rolling(H, min_periods=1).max()[::-1].shift(-1).ffill()
        ratio = (fut / X["m6"].clip(lower=.05)).clip(1, 4); y = (fut >= A).astype(int)
        self.reg = HistGradientBoostingRegressor(max_iter=250, learning_rate=.07, random_state=0).fit(X, ratio)
        # umbral de probabilidad calibrado en validación (maximiza F1 en muestras aún por debajo de la alerta)
        c = HistGradientBoostingClassifier(max_iter=200, learning_rate=.07, random_state=0).fit(X.iloc[:corte], y.iloc[:corte])
        pv, yv, pre = c.predict_proba(X.iloc[corte:])[:, 1], y.iloc[corte:].values, (i.iloc[corte:] < A).values
        mejor, self.umbral_prob = -1, .5
        for u in np.arange(.2, .91, .05):
            a = (pv >= u) & pre; tp = (a & (yv == 1)).sum(); fp = (a & (yv == 0)).sum(); fn = ((~a) & (yv == 1) & pre).sum()
            f1 = 2 * tp / max(2 * tp + fp + fn, 1)
            if f1 > mejor: mejor, self.umbral_prob = f1, float(u)
        self.clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=.07, random_state=0).fit(X, y)
        self.iso = IsolationForest(n_estimators=200, contamination=.03, random_state=0).fit(X[self.COLS_ANOM])
        self.umbral_anom = float(np.quantile(-self.iso.score_samples(X[self.COLS_ANOM]), .97))
        return self

    def predecir(self, i):
        """Para cada muestra: i_futura_max, prob_pico, alerta_pico, score_anom, anomalia."""
        X = feats(i); I = i.values
        ratio = np.clip(self.reg.predict(X), 1, 4)
        prob = self.clf.predict_proba(X)[:, 1]; alerta = prob >= self.umbral_prob
        fut = np.maximum(I, ratio * X["m6"].values)
        fut = np.where(alerta, np.maximum(fut, CFG["I_ALERTA"]), fut)          # el clasificador eleva a alerta
        score = -self.iso.score_samples(X[self.COLS_ANOM])
        return pd.DataFrame({"i_futura_max": fut, "prob_pico": prob, "alerta_pico": alerta.astype(int),
                             "score_anom": score, "anomalia": (score > self.umbral_anom).astype(int)}, index=i.index)


# ================================ MODELO 3 ========================================
P = dict(  # frases canónicas (se usan al redactar) y sus paráfrasis (para robustecer el clasificador)
    crit="sobrecorriente peligrosa por encima del límite crítico",
    sobre="sobrecarga moderada sobre el valor nominal",
    norm="dentro del rango normal",
    riesgo="riesgo inminente de corriente peligrosa",
    elev="potencia elevada",
    osc="oscilación irregular de corriente",
    est="Sin eventos. Operación estable.",
    falt="Dato faltante reconstruido por el modelo, lectura con menor confiabilidad.",
)
PARAFRASIS = {
    P["crit"]: ["corriente excesiva y peligrosa, límite crítico superado", "nivel de corriente crítico, riesgo para el módulo"],
    P["sobre"]: ["carga elevada por encima de lo nominal", "consumo mayor al nominal"],
    P["norm"]: ["en valores normales", "consumo normal"],
    P["riesgo"]: ["se espera corriente peligrosa", "probable sobrecorriente crítica"],
    P["elev"]: ["consumo alto previsto", "carga alta esperada"],
    P["osc"]: ["fluctuaciones raras en la corriente", "comportamiento errático"],
    P["est"]: ["Todo estable, sin novedades.", "Operación normal sin incidentes."],
    P["falt"]: ["Muestra perdida y reconstruida, menor confianza.", "Lectura reconstruida, confiabilidad reducida."],
}


def redactar_bitacora(fila, ts):
    I, N, A, C = fila["corriente"], CFG["I_NOM"], CFG["I_ALERTA"], CFG["I_CRITICA"]
    pct = 100 * I / N
    p = [f"[{ts}] Corriente {I:.2f} A, potencia estimada {fila['potencia']:.1f} W."]
    if I >= C:   p.append(f"Corriente {pct:.0f}% de la nominal, {P['crit']}.")
    elif I >= N: p.append(f"Corriente {pct:.0f}% de la nominal, {P['sobre']}.")
    else:        p.append(f"Corriente {pct:.0f}% de la nominal, {P['norm']}.")
    F = fila["i_futura_max"]
    if F >= C:   p.append(f"Modelo predice pico de {F:.2f} A en los próximos segundos, {P['riesgo']}.")
    elif F >= A: p.append(f"Modelo predice posible pico de {F:.2f} A en los próximos segundos, {P['elev']}.")
    if fila["anomalia"]: p.append(f"Comportamiento anómalo detectado (score {fila['score_anom']:.2f}), {P['osc']}.")
    if fila["imputado"]: p.append(P["falt"])
    if not (fila["anomalia"] or fila["imputado"] or F >= A or I >= N): p.append(P["est"])
    return " ".join(p)


def _limpiar(t):
    return re.sub(r"\[.*?\]|\d+(\.\d+)?", " ", t.lower())


class ModeloBitacora:
    def _corpus(self, n=2500, seed=3):
        r = np.random.default_rng(seed); N, A, C = CFG["I_NOM"], CFG["I_ALERTA"], CFG["I_CRITICA"]
        X, y = [], []
        for _ in range(n):
            nivel = int(r.choice([1, 2, 3], p=[.5, .3, .2]))
            if nivel == 1:
                i = r.uniform(.05, N * .95); fut = min(i * r.uniform(1, 1.3), A * .9)
                f = dict(corriente=i, i_futura_max=fut, anomalia=0, score_anom=r.uniform(.3, .5), imputado=int(r.random() < .1))
            elif nivel == 2:
                tipo = r.choice(["sobrecarga", "pico", "anom"])
                i = r.uniform(N, C * .9) if tipo == "sobrecarga" else r.uniform(.1, N * .95)
                fut = r.uniform(A, C * .95) if tipo == "pico" else max(i, min(i * 1.1, A * .9))
                f = dict(corriente=i, i_futura_max=max(fut, i), anomalia=int(tipo == "anom"), score_anom=r.uniform(.55, .7), imputado=int(r.random() < .15))
            else:
                tipo = r.choice(["corriente", "pico", "mixto"])
                i = r.uniform(C, C * 1.6) if tipo != "pico" else r.uniform(.2, C * .95)
                f = dict(corriente=i, i_futura_max=r.uniform(C, C * 1.5), anomalia=int(tipo == "mixto" or r.random() < .4),
                         score_anom=r.uniform(.6, .9), imputado=int(r.random() < .1))
            f["potencia"] = CFG["V_BUS"] * f["corriente"]
            t = redactar_bitacora(f, "2026-01-01 00:00:00")
            for canon, alts in PARAFRASIS.items():          # aumento de datos: paráfrasis aleatorias
                if canon in t and r.random() < .5: t = t.replace(canon, str(r.choice(alts)))
            X.append(t); y.append(nivel)
        return X, y

    def fit(self):
        X, y = self._corpus()
        self.pipe = make_pipeline(TfidfVectorizer(preprocessor=_limpiar, ngram_range=(1, 2), min_df=2),
                                  LogisticRegression(max_iter=1000, class_weight="balanced")).fit(X, y)
        return self

    def severidad(self, textos):
        """Lee texto de bitácora (canónico o escrito a mano) -> (niveles, confianza)."""
        textos = list(textos)
        return self.pipe.predict(textos).astype(int), self.pipe.predict_proba(textos).max(axis=1)


# ================================ ORQUESTADOR =====================================
class EcoGridAI:
    def entrenar(self, serie_real=None):
        i = serie_real if serie_real is not None else generar_serie(20000, 0)[0]
        self.completador = ModeloCompletador().fit(i)
        self.m2 = ModeloPicosAnomalias().fit(i)
        self.bitacora = ModeloBitacora().fit()
        return self

    # ---- análisis en lote (notebook / reentrenamiento / evaluación) ----
    def analizar_serie(self, i, imputado=None, ts0="2026-01-01 00:00:00"):
        d = self.m2.predecir(i)
        d.insert(0, "corriente", i.values)
        d.insert(1, "potencia", ModeloCompletador.potencia_w(i.values))
        d["imputado"] = 0 if imputado is None else np.asarray(imputado).astype(int)
        textos = [redactar_bitacora(r, ts0) for r in d.to_dict("records")]
        niv_ia, conf = self.bitacora.severidad(textos)
        d["texto"], d["nivel_ia"], d["confianza"] = textos, niv_ia, conf
        d["nivel"] = np.where(d["corriente"] >= CFG["I_CRITICA"], 3, niv_ia)          # regla dura de seguridad
        d["predicted_severity"] = d["nivel"].map(NIVEL_A_SEVERIDAD)                   # "Leve" | "Moderado" | "Crítico"
        return d

    # ---- análisis en tiempo real (lo usa Flask) ----
    def analizar(self, ts, vals, ts_texto, gracia=False):
        dt = float(np.clip(np.median(np.diff(ts)) if len(ts) > 4 else CFG["DT"], 1.0, 5.0))
        serie = reconstruir_serie(ts, vals, dt)
        i, imp = self.completador.completar(serie)
        I = float(i.iloc[-1])
        if gracia:                                           # tras reconectar: evita falsos positivos de arranque
            fila = dict(corriente=I, potencia=I * CFG["V_BUS"], i_futura_max=I, anomalia=0, score_anom=0.0,
                        imputado=int(imp.iloc[-5:].sum() > 0), prob_pico=0.0)
        else:
            m2 = self.m2.predecir(i).iloc[-1]
            fila = dict(corriente=I, potencia=I * CFG["V_BUS"], i_futura_max=float(m2.i_futura_max),
                        anomalia=int(m2.anomalia), score_anom=float(m2.score_anom),
                        imputado=int(imp.iloc[-5:].sum() > 0), prob_pico=float(m2.prob_pico))
        texto = redactar_bitacora(fila, ts_texto)
        niv, conf = self.bitacora.severidad([texto])
        nivel, duro = int(niv[0]), False
        if I >= CFG["I_CRITICA"]: nivel, duro = 3, True
        severidad = NIVEL_A_SEVERIDAD[nivel]                                          # string para el backend
        return dict(fila, texto=texto, nivel=nivel, predicted_severity=severidad, nivel_ia=int(niv[0]),
                    confianza=round(float(conf[0]), 2), regla_dura=duro, n_reconstruidos=int(imp.sum()), nombre=NOMBRES[nivel],
                    energia_ventana_kwh=ModeloCompletador.energia_kwh(i, dt))

    # ---- evaluación completa (alimenta el reporte) ----
    def evaluar(self, seed=123, n=10000):
        H, A, C, N = CFG["HORIZONTE"], CFG["I_ALERTA"], CFG["I_CRITICA"], CFG["I_NOM"]
        i, anom = generar_serie(n, seed); res = {}
        # ---- Modelo 1
        obs, mask = meter_huecos(i, 25, seed)
        lin = pd.Series(np.interp(np.arange(n), np.where(~obs.isna())[0], obs.dropna().values))
        ml, _ = self.completador.completar(obs)
        e_real = ModeloCompletador.energia_kwh(i)
        e_naive = CFG["V_BUS"] * obs.dropna().sum() * CFG["DT"] / 3.6e6       # ignorar muestras faltantes
        res["m1"] = dict(huecos=int(mask.sum()), mae_lineal=float(np.abs(lin[mask] - i[mask]).mean()),
                         mae_ml=float(np.abs(ml[mask] - i[mask]).mean()),
                         e_real=e_real, e_naive=float(e_naive), e_lineal=ModeloCompletador.energia_kwh(lin),
                         e_ml=ModeloCompletador.energia_kwh(ml))
        # ---- Modelo 2
        d = self.m2.predecir(i); fut = i[::-1].rolling(H, min_periods=1).max()[::-1].shift(-1).ffill()
        pre = (i < A).values; y = (fut >= A).values; alerta = (d.alerta_pico == 1).values & pre
        tp = int((alerta & y).sum()); fp = int((alerta & ~y).sum()); fn = int((~alerta & y & pre).sum())
        starts = [k for k in range(1, n) if i[k] >= A and i[k - 1] < A]; det, leads = 0, []
        for s_ in starts:
            w = np.where(alerta[max(0, s_ - H):s_])[0]
            if len(w): det += 1; leads.append(s_ - (max(0, s_ - H) + w[0]))
        idx = np.where(alerta)[0]; eps = [idx[0]] if len(idx) else []
        for a_, b_ in zip(idx[:-1], idx[1:]):
            if b_ - a_ > H: eps.append(b_)
        eps_falsos = sum(1 for e in eps if not y[e])
        seg = np.diff(np.r_[0, anom, 0]); ini, fin = np.where(seg == 1)[0], np.where(seg == -1)[0]
        seg_det = sum(1 for a_, b_ in zip(ini, fin) if d.anomalia.values[a_:b_].any())
        flag = d.anomalia.values == 1
        res["m2"] = dict(umbral_prob=self.m2.umbral_prob, precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1),
                         eventos=len(starts), detectados=det, lead_medio_pasos=float(np.mean(leads)) if leads else 0.0,
                         episodios_alerta=len(eps), episodios_falsos=int(eps_falsos),
                         anom_segmentos=len(ini), anom_segmentos_detectados=int(seg_det),
                         anom_precision=float((flag & (anom == 1)).sum() / max(flag.sum(), 1)),
                         anom_recall=float((flag & (anom == 1)).sum() / max((anom == 1).sum(), 1)))
        # ---- Modelo 3 + sistema completo vs criterio experto
        df = self.analizar_serie(i)
        verdad = np.where((i >= C) | (fut >= C), 3, np.where((i >= N) | (fut >= A) | (anom == 1), 2, 1))
        pred = df.nivel.values
        res["m3"] = dict(acc=float(accuracy_score(verdad, pred)), f1_macro=float(f1_score(verdad, pred, average="macro")),
                         cm=confusion_matrix(verdad, pred, labels=[1, 2, 3]).tolist(),
                         desconexiones_falsas=int(((pred == 3) & (verdad < 3)).sum()),
                         criticos_no_detectados=int(((pred < 3) & (i.values >= C)).sum()))
        return res

    def guardar(self, ruta="modelos_ecogrid.joblib"): joblib.dump(self, ruta); return ruta

    @staticmethod
    def cargar(ruta="modelos_ecogrid.joblib"): return joblib.load(ruta)


# ============================ USO POR SEPARADO (JSON-friendly) =====================
# Cada modelo exportado se puede usar solo, con entradas/salidas simples (listas y diccionarios JSON).
def a_json(x):
    """Convierte numpy/pandas a tipos nativos para json.dumps."""
    if isinstance(x, dict):        return {k: a_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [a_json(v) for v in x]
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.floating, float)): return None if np.isnan(x) else round(float(x), 6)
    if isinstance(x, (np.bool_,)):   return bool(x)
    if isinstance(x, np.ndarray):    return a_json(x.tolist())
    if isinstance(x, pd.Series):     return a_json(x.tolist())
    return x


def modelo1_completar(m1, corrientes_A, dt_s=None):
    """MODELO 1. Entrada: lista de corrientes (A) con None/NaN donde faltó el dato. Salida: serie completa + energía."""
    s = pd.Series([np.nan if v is None else float(v) for v in corrientes_A], dtype=float)
    completa, flag = m1.completar(s)
    dt = dt_s or CFG["DT"]
    return a_json(dict(corrientes_completas_A=completa, imputado=flag, potencia_W=ModeloCompletador.potencia_w(completa),
                       energia_kWh=ModeloCompletador.energia_kwh(completa, dt), dt_s=dt))


def modelo2_predecir(m2, corrientes_A):
    """MODELO 2. Entrada: lista de corrientes (A) SIN huecos (recientes, >=30 muestras ideal). Salida: predicción de la última muestra."""
    d = m2.predecir(pd.Series([float(v) for v in corrientes_A])).iloc[-1]
    return a_json(dict(i_futura_max_A=d.i_futura_max, prob_pico=d.prob_pico, alerta_pico=int(d.alerta_pico),
                       score_anomalia=d.score_anom, anomalia=int(d.anomalia)))


def modelo3_clasificar(m3, textos):
    """MODELO 3. Entrada: lista de textos de bitácora. Salida: severidad por texto."""
    niv, conf = m3.severidad(textos)
    return [dict(texto=t, nivel=int(n), predicted_severity=NIVEL_A_SEVERIDAD[int(n)], confianza=round(float(c), 3))
            for t, n, c in zip(textos, niv, conf)]


def pipeline_analizar(IA, timestamps_s, corrientes_A, ts_texto, gracia=False):
    """PIPELINE completo (modelos 1+2+3 + regla dura). Es lo que consume el backend."""
    r = IA.analizar(list(timestamps_s), [float(v) for v in corrientes_A], ts_texto, gracia=gracia)
    return a_json(r)


# ============================ EXPORTAR / CARGAR POR SEPARADO =======================
CONTRATO_CAMPOS = {
    "modelo1_completar": {
        "entrada": {"corrientes_A": "list[float|null]  null = dato faltante", "dt_s": "float opcional, segundos entre muestras"},
        "salida": {"corrientes_completas_A": "list[float]", "imputado": "list[0|1]  1 = reconstruido",
                   "potencia_W": "list[float]  P=V_BUS*I (DC)", "energia_kWh": "float", "dt_s": "float"}},
    "modelo2_predecir": {
        "entrada": {"corrientes_A": "list[float] sin huecos, recientes"},
        "salida": {"i_futura_max_A": "float, máx. esperada en ~HORIZONTE pasos", "prob_pico": "float 0-1",
                   "alerta_pico": "0|1", "score_anomalia": "float", "anomalia": "0|1"}},
    "modelo3_clasificar": {
        "entrada": {"textos": "list[str] bitácora (generada o escrita a mano)"},
        "salida": "list[{texto, nivel 1-3, predicted_severity 'Leve'|'Moderado'|'Crítico', confianza 0-1}]"},
    "pipeline_analizar": {
        "entrada": {"timestamps_s": "list[float] epoch", "corrientes_A": "list[float] mismo largo", "ts_texto": "str",
                    "gracia": "bool, true justo tras reconectar la carga"},
        "salida": {"predicted_severity": "'Leve'|'Moderado'|'Crítico'  <- campo para el backend", "nivel": "1|2|3",
                   "nombre": "str", "corriente": "A", "potencia": "W", "i_futura_max": "A", "prob_pico": "0-1",
                   "anomalia": "0|1", "imputado": "0|1", "n_reconstruidos": "int", "confianza": "0-1",
                   "regla_dura": "bool (true = corriente >= I_CRITICA, corte inmediato)", "texto": "bitácora",
                   "energia_ventana_kwh": "float"}},
}


def _ejemplos(IA):
    rng = np.random.default_rng(0)
    base = [round(float(0.43 + rng.normal(0, .012)), 3) for _ in range(40)]
    con_huecos = base[:15] + [None] * 5 + base[20:30]
    rampa = base[:34] + [0.50, 0.72, 0.96, 1.12, 1.28, 1.41]
    t0 = 1_800_000_000.0; ts = [t0 + 2.2 * k for k in range(len(rampa))]
    textos = ["Corriente 0.43 A, dentro del rango normal. Operación estable, sin eventos.",
              "Carga alta esperada. Se detectaron fluctuaciones raras en la corriente.",
              "Corriente excesiva y peligrosa, límite crítico superado. Se espera corriente peligrosa."]
    ent = {"modelo1_completar": {"corrientes_A": con_huecos, "dt_s": 2.2},
           "modelo2_predecir": {"corrientes_A": rampa},
           "modelo3_clasificar": {"textos": textos},
           "pipeline_analizar": {"timestamps_s": ts, "corrientes_A": rampa, "ts_texto": "2026-11-24 10:00:00", "gracia": False}}
    sal = {"modelo1_completar": modelo1_completar(IA.completador, **ent["modelo1_completar"]),
           "modelo2_predecir": modelo2_predecir(IA.m2, **ent["modelo2_predecir"]),
           "modelo3_clasificar": modelo3_clasificar(IA.bitacora, **ent["modelo3_clasificar"]),
           "pipeline_analizar": pipeline_analizar(IA, **ent["pipeline_analizar"])}
    return ent, sal


def exportar_modelos(IA, carpeta="modelos_exportados"):
    """Guarda CADA modelo por separado + config + contrato de entrada/salida (para humanos y otras IAs)."""
    import os, json, sys, platform, datetime, sklearn
    os.makedirs(carpeta, exist_ok=True)
    joblib.dump(IA.completador, f"{carpeta}/modelo1_completador.joblib")
    joblib.dump(IA.m2,          f"{carpeta}/modelo2_picos_anomalias.joblib")
    joblib.dump(IA.bitacora,    f"{carpeta}/modelo3_bitacora.joblib")
    cfg = dict(CFG=CFG, NOMBRES={str(k): v for k, v in NOMBRES.items()},
               NIVEL_A_SEVERIDAD={str(k): v for k, v in NIVEL_A_SEVERIDAD.items()},
               modelo1_usar_ml=IA.completador.usar_ml, modelo2_umbral_prob=IA.m2.umbral_prob,
               versiones=dict(python=platform.python_version(), scikit_learn=sklearn.__version__,
                              numpy=np.__version__, pandas=pd.__version__, joblib=joblib.__version__),
               exportado=datetime.datetime.now().isoformat(timespec="seconds"))
    json.dump(cfg, open(f"{carpeta}/config.json", "w"), ensure_ascii=False, indent=2)
    ent, sal = _ejemplos(IA)
    contrato = dict(descripcion="Contrato de E/S de los modelos EcoGrid AI (corriente DC -> picos, anomalías, bitácora y severidad).",
                    archivos=dict(modelo1="modelo1_completador.joblib", modelo2="modelo2_picos_anomalias.joblib",
                                  modelo3="modelo3_bitacora.joblib", codigo="ecogrid_ai.py (debe estar importable)"),
                    campos=CONTRATO_CAMPOS, ejemplo_entrada=ent, ejemplo_salida=sal)
    json.dump(a_json(contrato), open(f"{carpeta}/contrato_io.json", "w"), ensure_ascii=False, indent=2)
    open(f"{carpeta}/README_IA.md", "w", encoding="utf-8").write(_readme(cfg))
    return carpeta


def cargar_modelos(carpeta="modelos_exportados"):
    """Reconstruye EcoGridAI desde los 3 archivos separados (y restaura la configuración de umbrales)."""
    import json
    cfg = json.load(open(f"{carpeta}/config.json", encoding="utf-8"))
    CFG.update(cfg["CFG"])
    IA = EcoGridAI.__new__(EcoGridAI)
    IA.completador = joblib.load(f"{carpeta}/modelo1_completador.joblib")
    IA.m2 = joblib.load(f"{carpeta}/modelo2_picos_anomalias.joblib")
    IA.bitacora = joblib.load(f"{carpeta}/modelo3_bitacora.joblib")
    return IA


def _readme(cfg):
    v = cfg["versiones"]
    return f"""# EcoGrid AI - modelos exportados (guía para otra IA / desarrollador)

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
- Compatibilidad: exportado con Python {v['python']}, scikit-learn {v['scikit_learn']}, numpy {v['numpy']}, pandas {v['pandas']}.
  Si la versión de scikit-learn difiere, vuelve a entrenar y exportar en tu entorno.
"""
