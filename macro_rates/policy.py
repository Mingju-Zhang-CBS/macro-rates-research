"""Monthly-rate contracts. Rates are percent; changes are basis points."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

MULTIPLIER = 4167.0


def month_path(month, initial_rate, changes=(), realized=None, known_through=None):
    """Changes use effective dates, not announcement dates. Realized is calendar-daily."""
    start = pd.Timestamp(month).to_period("M").start_time
    days = pd.date_range(start, start + pd.offsets.MonthEnd(0), freq="D")
    changes = [(pd.Timestamp(d).normalize(), float(bp)) for d, bp in changes]
    if not np.isfinite(initial_rate) or any(not np.isfinite(bp) for _, bp in changes):
        raise ValueError("Finite percent rates and bp changes required")
    rates = pd.Series(float(initial_rate), index=days, name="rate_percent")
    for effective, bp in sorted(changes):
        rates.loc[rates.index >= effective] += bp / 100
    if realized is not None:
        if known_through is None:
            raise ValueError('Realized inputs require an explicit known-through date')
        values = realized.copy()
        values.index = pd.to_datetime(values.index).normalize()
        cutoff = pd.Timestamp(known_through).normalize()
        required = days[days <= cutoff]
        if (values.index.has_duplicates or not required.isin(values.index).all()
                or not np.isfinite(values.reindex(required)).all()):
            raise ValueError("Complete, unique realized calendar dates required through cutoff")
        rates.loc[required] = values.reindex(required).to_numpy()
    return rates


def monthly_price(month, initial_rate, changes=(), realized=None, known_through=None):
    return 100.0 - float(month_path(month, initial_rate, changes, realized, known_through).mean())


def tick_price(price, tick=0.005, side=1):
    """Conservative grid rounding: buy up; sell down."""
    if tick <= 0 or side not in (-1, 1) or not np.isfinite(price):
        raise ValueError("Positive tick, finite price, side +/-1 required")
    units = price / tick
    return float((np.ceil(units - 1e-10) if side == 1 else np.floor(units + 1e-10)) * tick)


@dataclass(frozen=True)
class Funding:
    pairs: int = 6
    initial_cash: float = 100000.0
    margin_per_contract: float = 2000.0
    fee_per_side: float = 4.0
    full_spread_points: float = 0.005
    cash_rate: float = 0.0


def calendar_ledger(marks, direction=1, funding=Funding()):
    """Long far/short near for +1. Settlement marks with modeled costs, not fills.

    Required columns date, near, far. Optional margin_per_contract is dated evidence
    or an explicitly named proxy. Missing marks are rejected, never forward filled.
    """
    x = marks.copy()
    x["date"] = pd.to_datetime(x["date"])
    numeric = ["near", "far"] + (["margin_per_contract"] if "margin_per_contract" in x else [])
    if (len(x) < 2 or x.date.duplicated().any() or not x.date.is_monotonic_increasing
            or not np.isfinite(x[numeric]).all().all() or direction not in (-1, 1)
            or funding.pairs < 1 or funding.initial_cash <= 0
            or min(funding.margin_per_contract, funding.fee_per_side, funding.full_spread_points) < 0
            or ("margin_per_contract" in x and (x.margin_per_contract < 0).any())):
        raise ValueError("Ordered complete marks and valid funding required")
    q = direction * funding.pairs
    cash, active, previous = funding.initial_cash, False, None
    rows = []
    side_cost = 2 * funding.pairs * (funding.fee_per_side + MULTIPLIER * funding.full_spread_points / 2)
    for i, row in enumerate(x.itertuples()):
        before = cash
        elapsed = 0 if i == 0 else (row.date - x.date.iloc[i-1]).days
        interest = max(cash, 0) * funding.cash_rate * elapsed / 365
        variation = 0.0 if not active else q * MULTIPLIER * ((row.far-row.near)-previous)
        cash += interest + variation
        margin = 2 * funding.pairs * getattr(row, "margin_per_contract", funding.margin_per_contract)
        fee, status = 0.0, "flat"
        if i == 0:
            if cash - side_cost >= margin:
                cash -= side_cost
                fee, active, status = side_cost, True, "entry_mark_proxy"
            else:
                status = "entry_rejected_margin"
        elif active:
            status = "held"
            if cash < margin or i == len(x)-1:
                status = "margin_exit_mark_proxy" if cash < margin else "scheduled_exit_mark_proxy"
                cash -= side_cost
                fee, active = side_cost, False
        previous = row.far-row.near
        rows.append({"date": row.date, "variation": variation, "interest": interest,
                     "execution_cost": fee, "cash": cash, "margin_reserved": margin if active else 0,
                     "free_cash": cash-(margin if active else 0), "cash_shortfall": max(-cash, 0),
                     "pairs": q if active else 0, "status": status,
                     "reconciliation_error": cash-before-variation-interest+fee})
    return pd.DataFrame(rows)
