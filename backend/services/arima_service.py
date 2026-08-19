"""ARIMA/ARMA ligero sin statsmodels: estimacion por minimos cuadrados condicionales.

- ARIMA(p,1,q) sobre el precio: pronostico a H dias con bandas de confianza (Monte Carlo).
- ARMA(p,0,q) sobre los rendimientos diarios: senal estadistica compra/venta/neutral.
"""

import numpy as np

_HORIZONTE = 5
_MAX_P = 2
_MAX_Q = 2
_UMBRAL_REND = 0.0012


def _diff(x, d=1):
    y = np.asarray(x, dtype=float)
    for _ in range(d):
        y = y[1:] - y[:-1]
    return y


def _fit_arma(y, p, q, iters=5):
    """ARMA(p,q) por minimos cuadrados condicionales (OLS iterado sobre innovaciones)."""
    n = len(y)
    lag_max = max(p, q)
    if n <= lag_max + 2:
        return None
    cols = [np.ones(n - lag_max)]
    for i in range(p):
        cols.append(y[lag_max - 1 - i:n - 1 - i])
    resid_ult = np.zeros(n)
    coef = None
    for _ in range(iters):
        X = np.column_stack(cols + [resid_ult[lag_max - 1 - j:n - 1 - j] for j in range(q)] if q else cols)
        try:
            coef, *_ = np.linalg.lstsq(X, y[lag_max:], rcond=None)
        except np.linalg.LinAlgError:
            return None
        resid = y[lag_max:] - X @ coef
        resid_ult = np.zeros(n)
        resid_ult[lag_max:] = resid
    if coef is None:
        return None
    return {
        "c": float(coef[0]),
        "phi": coef[1:1 + p],
        "theta": coef[1 + p:] if q > 0 else np.zeros(q),
        "sigma2": float(np.mean(resid ** 2)),
        "y": y,
        "lag_max": lag_max,
    }


def _aic_val(y, p, q):
    fit = _fit_arma(y, p, q)
    if fit is None or fit["sigma2"] <= 0:
        return None
    n = len(y)
    k = 1 + p + q
    return n * np.log(fit["sigma2"]) + 2 * k


def _mejor_orden(y, max_p, max_q):
    mejor = None
    mejor_aic = None
    for p in range(max_p + 1):
        for q in range(max_q + 1):
            if p == 0 and q == 0:
                continue
            a = _aic_val(y, p, q)
            if a is None:
                continue
            if mejor_aic is None or a < mejor_aic:
                mejor_aic = a
                mejor = (p, q)
    return mejor or (1, 0)


def _forecast_arima_fit(fit, pasos, n_sims=400):
    """Pronostica `pasos` con simulaciones Monte Carlo del proceso ajustado."""
    if fit is None:
        return None
    y = fit["y"]
    phi = np.asarray(fit["phi"], dtype=float)
    theta = np.asarray(fit["theta"], dtype=float)
    sigma = float(np.sqrt(fit["sigma2"]))
    p, q = len(phi), len(theta)
    n = len(y)
    ultimos_y = list(y[max(0, n - max(p, 1)):])
    paths = np.zeros((n_sims, pasos))
    for s in range(n_sims):
        serie = list(ultimos_y)
        errs = []
        for h in range(pasos):
            pred = fit["c"]
            for i in range(p):
                if len(serie) >= i + 1:
                    pred += float(phi[i]) * serie[-i - 1]
            for j in range(q):
                if len(errs) >= j + 1:
                    pred += float(theta[j]) * errs[-j - 1]
            e = np.random.normal(0, sigma)
            serie.append(pred + e)
            errs.append(e)
        paths[s] = np.asarray(serie[-pasos:])
    media = paths.mean(axis=0)
    inferior = np.percentile(paths, 5, axis=0)
    superior = np.percentile(paths, 95, axis=0)
    return media, inferior, superior


def senal_arma_desde_precios(valores):
    """Atajo: calcula rendimientos diarios a partir de precios y aplica senal_arma."""
    v = np.asarray([float(x) for x in valores if x is not None and np.isfinite(x)], dtype=float)
    if v.size < 30:
        return None
    rends = (v[1:] - v[:-1]) / v[:-1]
    return senal_arma(list(rends))


def pronostico_arima(valores, horizonte=_HORIZONTE):
    """Pronostico ARIMA(p,1,q) sobre precios. Devuelve dict o None."""
    v = np.asarray([float(x) for x in valores if x is not None and np.isfinite(x)], dtype=float)
    if v.size < 30:
        return None
    zd = _diff(v, 1)
    p, q = _mejor_orden(zd, _MAX_P, _MAX_Q)
    fit = _fit_arma(zd, p, q)
    if fit is None or fit["sigma2"] <= 0:
        return None
    res = _forecast_arima_fit(fit, horizonte)
    if res is None:
        return None
    media_z, inf_z, sup_z = res
    media = v[-1] + np.cumsum(media_z)
    inferior = v[-1] + np.cumsum(inf_z)
    superior = v[-1] + np.cumsum(sup_z)
    return {
        "modelo": f"ARIMA({p},1,{q})",
        "ultimo_precio": float(v[-1]),
        "pronostico": [round(float(x), 6) for x in media],
        "inferior": [round(float(x), 6) for x in inferior],
        "superior": [round(float(x), 6) for x in superior],
        "cambio_pct": round((float(media[-1]) - float(v[-1])) / float(v[-1]) * 100, 2),
    }


def senal_arma(rendimientos):
    """ARMA(p,0,q) sobre rendimientos diarios: etiqueta compra/venta/neutral."""
    r = np.asarray([float(x) for x in rendimientos if x is not None and np.isfinite(x)], dtype=float)
    if r.size < 30:
        return None
    p, q = _mejor_orden(r, _MAX_P, _MAX_Q)
    fit = _fit_arma(r, p, q)
    if fit is None or fit["sigma2"] <= 0:
        return None
    res = _forecast_arima_fit(fit, 1, 600)
    if res is None:
        return None
    media, inferior, superior = res
    pred = float(media[0])
    sigma = float(np.sqrt(fit["sigma2"]))
    if pred >= _UMBRAL_REND:
        etiqueta = "COMPRA"
    elif pred <= -_UMBRAL_REND:
        etiqueta = "VENTA"
    else:
        etiqueta = "NEUTRAL"
    confianza = float(min(0.9, max(0.15, abs(pred) / max(2.5 * sigma, 1e-9))))
    return {
        "modelo": f"ARMA({p},0,{q})",
        "etiqueta": etiqueta,
        "prediccion_pct": round(pred * 100, 3),
        "rango_inferior_pct": round(float(inferior[0]) * 100, 3),
        "rango_superior_pct": round(float(superior[0]) * 100, 3),
        "confianza": round(confianza, 2),
    }