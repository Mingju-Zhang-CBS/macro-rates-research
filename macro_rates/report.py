from pathlib import Path
import hashlib
import json
import io
import platform
from importlib.resources import files
from dataclasses import asdict
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .curves import PARAMS, TENORS, zero_yield, curve_study
from .policy import monthly_price, month_path, calendar_ledger, Funding, MULTIPLIER

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False,
                    "axes.spines.right": False, "axes.labelcolor": "#101928",
                    "text.color": "#101928", "figure.facecolor": "#FAF9F5",
                    "axes.facecolor": "#FAF9F5", "axes.prop_cycle": plt.cycler(color=["#36B3A8", "#101928", "#B86E45"])})


def curve_report(frame, output, input_sha="synthetic", window=252):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    rows, factors = curve_study(frame, window)
    rows = rows.loc[pd.to_datetime(rows.date).between("2010-01-01", "2025-12-31")].copy()
    if rows.empty:
        raise ValueError("No observations in frozen reporting period")
    rows.to_csv(out/"daily_risk.csv", index=False)
    factors.to_csv(out/"pca.csv", index=False)
    summary = []
    for name, g in rows.groupby("portfolio"):
        rng=np.random.default_rng(20261030)
        observed=g.full_pnl.to_numpy()
        sampled=[]
        for _ in range(1000):
            starts=rng.integers(0,len(observed)-20+1,size=int(np.ceil(len(observed)/20)))
            indices=(starts[:,None]+np.arange(20)).ravel()[:len(observed)]
            sampled.append(observed[indices].mean())
        lower,upper=np.quantile(sampled,[.025,.975])
        summary.append({"portfolio": name, "days": len(g), "mean_model_pnl_usd": g.full_pnl.mean(),
                        "mean_block95_low":lower,"mean_block95_high":upper,
                        "daily_pnl_sd_usd": g.full_pnl.std(), "worst_day_usd": g.full_pnl.min(),
                        "mean_abs_taylor_residual_usd": g.taylor_residual.abs().mean(),
                        "mean_abs_pca_residual_usd": g.pca_residual.abs().mean(),
                        "max_abs_net_dv01_usd_bp": g.net_dv01.abs().max()})
    summary = pd.DataFrame(summary)
    summary.to_csv(out/"summary.csv", index=False)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for name, g in rows.groupby("portfolio"):
        axes[0].plot(pd.to_datetime(g.date), g.full_pnl.rolling(63).std(), label=name)
    axes[0].set(title="Risk changes even when positions are hedged", ylabel="63-observation P&L SD (USD)")
    axes[0].legend()
    valid = factors.loc[factors.status == "estimated"]
    axes[1].plot(pd.to_datetime(valid.date), valid.explained3*100)
    axes[1].set(ylabel="Variance explained by 3 PCs (%)", xlabel="Observation date",
                title="Prior 252-observation covariance PCA; current-vintage GSW curves")
    fig.savefig(out/"curve_risk.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for name, g in rows.groupby("portfolio"):
        axes[0].hist(g.full_pnl, bins=70, alpha=.55, label=name)
        worst = g.nsmallest(1, "full_pnl").iloc[0]
        axes[1].bar([f"{name}\nroll", f"{name}\nduration", f"{name}\nconvexity", f"{name}\nresidual"],
                    [worst.roll_carry, worst.duration_pnl, worst.convexity_pnl, worst.taylor_residual])
    axes[0].set(xlabel="Daily model P&L (USD)", ylabel="Observations", title="Fixed USD 1m gross each observation")
    axes[0].legend()
    axes[1].set(title="Worst day for each model portfolio", ylabel="USD")
    axes[1].tick_params(axis="x", labelsize=7)
    fig.savefig(out/"attribution.png", dpi=160)
    plt.close(fig)
    text = "# Treasury Curve Risk: Results\n\n"
    text += "Current-vintage Federal Reserve GSW staff research curves; hypothetical zero-coupon positions. "
    text += "This is retrospective risk attribution, not an investable return backtest.\n\n"
    text += "```csv\n"+summary.round(3).to_csv(index=False)+"```\n"
    text += "\n![Risk](curve_risk.png)\n\n![Attribution](attribution.png)\n\n"
    text += "## Reading the result\n\nThe two-leg portfolio offsets parallel dollar duration at inception. "
    text += "The three-leg portfolio offsets the first two prior-window PCA exposures; those components do not have fixed economic meanings. "
    text += "Neither construction removes convexity, changing factor loadings or residual curve risk. "
    text += "The P&L distribution includes unfavorable days. Mean intervals use 1,000 moving-block resamples of 20 observations, seed 20261030. "
    text += "These describe this model experiment, not a funded strategy or selection-adjusted trading edge. Higher mean model P&L does not establish alpha.\n\n"
    text += "## Accounting and limitations\n\nEach observation resets gross model market value to USD 1m. "
    text += "Positions age by actual elapsed calendar days / 365.25, then reprice on the next curve. "
    text += "No cumulative account NAV, executable bond price, financing or transaction-cost claim is made. "
    text += "PCA uses the prior 252 changes ending before the observation date. GSW observations are revised and published with delay; "
    text += "lagged fitting alone does not make this historical snapshot point-in-time.\n\n"
    text += "Source: [Federal Reserve GSW](https://www.federalreserve.gov/data/nominal-yield-curve.htm). "
    text += "Zero yields are continuously compounded; par yields are not used as zero rates.\n"
    (out/"REPORT.md").write_text(text, encoding="utf-8")
    receipt = {"generated_utc": datetime.now(timezone.utc).isoformat(), "input_sha256": input_sha,
               "first_model_date": str(rows.date.min().date()), "last_model_date": str(rows.date.max().date()),
               "runtime_seconds": time.perf_counter()-start, "machine": platform.platform(),
               "python": platform.python_version(), "window": window, "data_kind": "synthetic" if input_sha == "synthetic" else "public-real-current-vintage",
               "source_sha256": {n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                 for n in ['policy.py','curves.py','report.py','__main__.py']},
               "protocol_sha256": hashlib.sha256(files('macro_rates').joinpath('data/protocol.json').read_bytes()).hexdigest()}
    (out/"run.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return summary


def read_gsw(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig")
    offset = text.index("Date,BETA0,")
    full = pd.read_csv(io.StringIO(text[offset:]), na_values=["NA"])
    full["Date"] = pd.to_datetime(full["Date"])
    selected = full.loc[full.Date.between("2008-01-01", "2025-12-31"), ["Date"]+PARAMS]
    rejected = selected.loc[selected[PARAMS].isna().any(axis=1)]
    return selected.dropna().reset_index(drop=True), rejected, hashlib.sha256(raw).hexdigest()


def demo(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for change in [0, 25, 50, -25]:
        price = monthly_price("2027-05", 4.0, [("2027-03-18", change)])
        scenarios.append({"change_bp": change, "may_price": price,
                          "six_pair_pnl_before_cost": 6*MULTIPLIER*(price-96.0)})
    pd.DataFrame(scenarios).to_csv(out/"scenarios.csv", index=False)
    days = pd.bdate_range("2027-01-04", periods=20)
    marks = pd.DataFrame({"date": days, "near": 96., "far": np.linspace(95.8, 95.5, len(days)),
                          "margin_per_contract": np.r_[np.repeat(2000., 10), np.repeat(9000., 10)]})
    ledger = calendar_ledger(marks)
    ledger.to_csv(out/"funding_stress.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    a = pd.DataFrame(scenarios)
    axes[0].bar(a.change_bp.astype(str), a.six_pair_pnl_before_cost)
    axes[0].set(title="Declared policy scenarios", xlabel="Additional effective change (bp)", ylabel="6-pair model P&L before costs (USD)")
    axes[1].plot(days, ledger.cash, label="Cash")
    axes[1].plot(days, ledger.margin_reserved, label="Reserved margin")
    axes[1].legend()
    axes[1].set(title="Adverse prices + reserve increase", ylabel="USD")
    axes[1].tick_params(axis="x", rotation=30, labelsize=7)
    fig.savefig(out/"policy_and_cash.png", dpi=160)
    plt.close(fig)
    (out/"REPORT.md").write_text("# Offline Policy and Funding Demonstration\n\n"
        "![Policy and cash](policy_and_cash.png)\n\nAll marks and reserve changes here are synthetic. "
        "Six pairs have USD 250.02 of relative monthly-rate bp exposure. The reserve jump can force an exit even with positive cash. "
        "The ledger distinguishes reserved collateral from an expense, and reconciles variation, interest and execution costs. "
        "A modeled forced exit does not guarantee that an actual market provides a fill.\n", encoding="utf-8")
    (out/'run.json').write_text(json.dumps({'generated_utc':datetime.now(timezone.utc).isoformat(),
        'data_kind':'synthetic','funding':asdict(Funding()),'scenario_changes_bp':[0,25,50,-25],
        'initial_rate_percent':4.,'comparison_reference_price':96.,
        'protocol_sha256':hashlib.sha256(files('macro_rates').joinpath('data/protocol.json').read_bytes()).hexdigest(),
        'source_sha256':{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                         for n in ['policy.py','report.py','__main__.py']}},indent=2))
    return ledger
