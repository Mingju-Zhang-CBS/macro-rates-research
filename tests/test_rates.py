import numpy as np
import pandas as pd
import pytest
from macro_rates.policy import monthly_price, month_path, tick_price, calendar_ledger, Funding, MULTIPLIER
from macro_rates.curves import discount, prior_pca, curve_study, PARAMS


def test_calendar_effective_date_and_leap_year():
    path = month_path("2024-02", 5., [("2024-02-16", -25)])
    assert len(path) == 29
    assert monthly_price("2024-02", 5., [("2024-02-16", -25)]) == pytest.approx(100-(15*5+14*4.75)/29)


def test_realized_cutoff_does_not_use_future():
    known = pd.Series([4., 4.], index=pd.to_datetime(["2027-02-01", "2027-02-02"]))
    a = monthly_price("2027-02", 5., realized=known, known_through="2027-02-02")
    known.loc[pd.Timestamp("2027-02-28")] = 99.
    assert a == monthly_price("2027-02", 5., realized=known, known_through="2027-02-02")
    with pytest.raises(ValueError):
        monthly_price("2027-02", 5., realized=known.iloc[1:], known_through="2027-02-02")


def test_missing_realized_values_and_missing_information_cutoff_are_rejected():
    actual=pd.Series([np.nan],index=pd.to_datetime(['2027-02-01']))
    with pytest.raises(ValueError):monthly_price('2027-02',4.,realized=actual,known_through='2027-02-01')
    actual.iloc[0]=4.
    with pytest.raises(ValueError):monthly_price('2027-02',4.,realized=actual)


@pytest.mark.parametrize("side,expected", [(1, 95.665), (-1, 95.660)])
def test_grid(side, expected):
    assert tick_price(95.662, side=side) == pytest.approx(expected)


def test_ledger_known_pnl_and_collateral_not_expense():
    x = pd.DataFrame({"date": pd.date_range("2027-01-01", periods=3), "near": [96.,96.,96.], "far": [95.8,95.9,96.]})
    f = Funding(full_spread_points=0)
    a = calendar_ledger(x, funding=f)
    assert a.cash.iloc[-1] == pytest.approx(100000+6*MULTIPLIER*.2-4*6*4)
    assert a.margin_reserved.iloc[0] == 24000
    assert a.reconciliation_error.abs().max() < 1e-8


def test_margin_rejection_and_dated_raise():
    x = pd.DataFrame({"date": pd.date_range("2027-01-01", periods=3), "near": [96.]*3, "far": [96.]*3,
                      "margin_per_contract": [2000., 9000., 9000.]})
    a = calendar_ledger(x)
    assert a.status.iloc[1] == "margin_exit_mark_proxy"
    assert a.pairs.iloc[1] == 0
    b = calendar_ledger(x, funding=Funding(initial_cash=10))
    assert b.status.iloc[0] == "entry_rejected_margin"
    assert b.execution_cost.sum() == 0


def test_zero_discount_finite_difference_duration():
    p = np.array([4., 0., 0., 0., 2., 5.])
    q = p.copy(); q[0] += .01
    dv01 = discount([2,10], p)-discount([2,10], q)
    expected = discount([2,10], p)*np.array([2,10])*1e-4
    assert np.allclose(dv01, expected, rtol=.0006)


def test_pca_covariance_and_orthogonality():
    x = np.random.default_rng(3).normal(size=(100,5))
    values, vectors = prior_pca(x)
    assert np.allclose(vectors.T@vectors, np.eye(5))
    assert np.allclose(vectors@np.diag(values)@vectors.T, np.cov(x,rowvar=False))


def test_future_perturbation_and_attribution():
    rng = np.random.default_rng(5)
    x = pd.DataFrame(np.tile([4.,-1.,.5,.2,2.,5.], (80,1)), columns=PARAMS)
    x["BETA0"] += rng.normal(0,.01,80).cumsum()
    x["Date"] = pd.bdate_range("2020-01-01", periods=80)
    a, _ = curve_study(x, window=20)
    changed=x.copy(); changed.loc[60:,"BETA0"] += 5
    b, _ = curve_study(changed, window=20)
    pd.testing.assert_frame_equal(a.loc[a.next_date < x.Date.iloc[60]].reset_index(drop=True),
                                  b.loc[b.next_date < x.Date.iloc[60]].reset_index(drop=True))
    assert np.allclose(a.full_pnl, a.roll_carry+a.duration_pnl+a.convexity_pnl+a.taylor_residual)
    assert (pd.to_datetime(a.training_end) < pd.to_datetime(a.date)).all()
    assert a.loc[a.portfolio=='2s10s','net_dv01'].abs().max() < 1e-8
    assert a.loc[a.portfolio=='2s5s10s',['pc1_exposure_usd_bp','pc2_exposure_usd_bp']].abs().to_numpy().max() < 1e-8
