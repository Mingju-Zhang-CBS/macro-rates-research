"""Continuous zero rates, model zero-coupon positions and prior-window PCA."""
import numpy as np
import pandas as pd

TENORS = np.array([2., 5., 10., 20., 30.])
PARAMS = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]


def zero_yield(tenors, parameters):
    b0, b1, b2, b3, tau1, tau2 = parameters
    t = np.asarray(tenors, dtype=float)
    if np.any(t <= 0) or min(tau1, tau2) <= 0 or not np.isfinite(parameters).all():
        raise ValueError("Positive maturities and taus, finite NSS parameters required")
    a, b = t/tau1, t/tau2
    a1, a2 = -np.expm1(-a)/a, -np.expm1(-b)/b
    return b0 + b1*a1 + b2*(a1-np.exp(-a)) + b3*(a2-np.exp(-b))


def discount(tenors, parameters):
    return np.exp(-zero_yield(tenors, parameters)*np.asarray(tenors)/100)


def prior_pca(changes):
    """Input is the caller's training slice in bp; PCA uses covariance, not correlation."""
    x = np.asarray(changes, dtype=float)
    if x.ndim != 2 or len(x) < 3 or not np.isfinite(x).all():
        raise ValueError("Finite training matrix required")
    cov = np.cov(x, rowvar=False)
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    for i in range(vectors.shape[1]):
        k = np.argmax(abs(vectors[:, i]))
        if vectors[k, i] < 0:
            vectors[:, i] *= -1
    return values, vectors


def curve_study(frame, window=252, gross=1000000.):
    x = frame.copy()
    x["Date"] = pd.to_datetime(x["Date"])
    if (len(x) <= window+2 or x.Date.duplicated().any() or not x.Date.is_monotonic_increasing
            or not np.isfinite(x[PARAMS]).all().all() or (x[["TAU1", "TAU2"]] <= 0).any().any()):
        raise ValueError("Complete chronological NSS rows and sufficient history required")
    parameters = x[PARAMS].to_numpy()
    yields = np.array([zero_yield(TENORS, p) for p in parameters])
    dy = np.diff(yields, axis=0)*100  # percent to bp
    rows, factors = [], []
    previous_vectors = None
    for i in range(window+1, len(x)-1):
        # Last input change ends on i-1. Neither i nor i+1 enters risk estimation.
        values, vectors = prior_pca(dy[i-window-1:i-1])
        previous = parameters[i]
        elapsed = (x.Date.iloc[i+1]-x.Date.iloc[i]).days/365.25
        aged = TENORS-elapsed
        p0 = discount(TENORS, previous)
        p_aged = discount(aged, previous)
        p1 = discount(aged, parameters[i+1])
        moves = (zero_yield(aged, parameters[i+1])-zero_yield(aged, previous))/100
        weights = np.array([10/12, 0, -2/12, 0, 0.])
        # Null of the first two PRIOR PCA dollar-risk exposures in 2/5/10y.
        loading = vectors[:3, :2].T*TENORS[:3]
        butterfly = np.cross(loading[0], loading[1])
        if np.linalg.norm(butterfly) < 1e-10:
            factors.append({"date": x.Date.iloc[i], "status": "singular_butterfly"})
            portfolios = [("2s10s", weights)]
        else:
            butterfly *= 1 if butterfly[1] >= 0 else -1
            butterfly /= abs(butterfly).sum()
            portfolios = [("2s10s", weights), ("2s5s10s", np.r_[butterfly, 0, 0])]
        for name, w in portfolios:
            market_value = gross*w
            face = market_value/p0
            carry = float(face @ (p_aged-p0))
            market = float(face @ (p1-p_aged))
            delta = float(-(market_value*aged) @ moves)
            convexity = float(.5*(market_value*aged**2) @ (moves**2))
            pv_risk_bp = market_value*aged*1e-4
            scores = vectors.T @ (moves*10000)
            pca_pnl = -(pv_risk_bp @ vectors[:, :3]) @ scores[:3]
            rows.append({"date": x.Date.iloc[i], "next_date": x.Date.iloc[i+1], "portfolio": name,
                         "gross_model_value": gross, "full_pnl": carry+market, "roll_carry": carry,
                         "market_revaluation": market, "duration_pnl": delta, "convexity_pnl": convexity,
                         "taylor_residual": market-delta-convexity, "pca3_market_pnl": pca_pnl,
                         "pca_residual": market-pca_pnl, "net_dv01": float(w @ TENORS*gross*1e-4),
                         "pc1_exposure_usd_bp": float((w*TENORS*gross*1e-4) @ vectors[:,0]),
                         "pc2_exposure_usd_bp": float((w*TENORS*gross*1e-4) @ vectors[:,1]),
                         "training_end": x.Date.iloc[i-1]})
        factors.append({"date": x.Date.iloc[i], "status": "estimated", "explained3": float(values[:3].sum()/values.sum()),
                        "pc1_gap": float((values[0]-values[1])/values[0]),
                        "pc1_overlap": float(abs(vectors[:,0] @ previous_vectors[:,0])) if previous_vectors is not None else np.nan,
                        "pc12_subspace_overlap": float(np.linalg.norm(vectors[:,:2].T @ previous_vectors[:,:2])**2/2) if previous_vectors is not None else np.nan,
                        **{f"pc{k+1}_{int(t)}y": vectors[j,k] for j,t in enumerate(TENORS) for k in range(3)}})
        previous_vectors = vectors
    return pd.DataFrame(rows), pd.DataFrame(factors)
