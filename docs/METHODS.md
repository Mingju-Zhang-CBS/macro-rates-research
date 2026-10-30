# Methods: From a View to Measurable Risk

## 1. Monthly-rate contracts

Rates are entered in percent; policy changes in basis points. A date in a scenario is the **effective date**, not automatically the meeting date. For D calendar days, the modeled futures quote is `100 - sum(r_d)/D`. Weekends and holidays inherit the appropriate effective overnight setting; realized calendar values must be supplied explicitly through a declared cutoff. Later realized values cannot overwrite the forecast portion.

A 25bp move effective halfway through a month changes that month's average by roughly half as much; a contract wholly after the change receives its full effect. Six matched long-far/short-near pairs have `6 × 4167 × .01 = $250.02` per bp of relative monthly-rate exposure. Equal shifts in both monthly averages cancel in this linear model. They do not cancel all basis, timing or liquidity risks.

The grid helper rounds purchases up and sales down. For a two-leg executable spread, entry uses the far ask minus the near bid and liquidation the far bid minus the near ask. Quoted spread costs must not be charged a second time. The synthetic ledger instead starts with settlement marks and an explicitly modeled full spread; it does not claim actual fills.

## 2. Funding is part of the hypothesis

Cash evolves as prior cash + variation margin + cash interest - modeled execution costs. Reserved initial margin is collateral, not an expense. Both legs enter and exit together in the model, without assumed spread offsets. A dated reserve increase can force a marked exit even when cash is positive. Negative cash, missing marks and entry refusal remain visible. The model does not guarantee execution during stress.

The frozen historical controls choose delivery months +2 and +5 for each observation month, report both trade directions and reset USD 100k independently for each monthly account. There is no winner selection, return-driven sizing or stitched cumulative NAV. The composite source is not silently spliced with the shorter electronic source. Unrelated fields in a vendor-wide view can multiply rows: only identical consumed observations are collapsed, and conflicting contract-day marks are rejected.

## 3. Treasury zero curves and aging

The Svensson function returns continuous zero yields in percent. Discount factors are `exp(-y(T) × T/100)`. Par yields cannot be substituted here. At inception each model portfolio has USD 1m gross market value. Signed face amounts are held until the next observed curve, aging by elapsed calendar days/365.25, then fully repriced at remaining maturity. A fresh model position is formed for the next observation; this is a risk experiment, not a self-financing strategy account.

Full P&L separates into aging on the old curve plus market revaluation. Market revaluation is compared with duration and convexity approximations, retaining the residual. Negative yields are permitted.

## 4. Prior-window PCA

Use 252 prior changes in 2/5/10/20/30y zero yields, in bp, ending before the position observation. Estimate a centered covariance matrix without whole-sample standardization. The two-leg weights offset parallel dollar duration. The three-leg 2/5/10y weights lie in the null space of the first two prior PCA dollar exposures, with positive belly orientation and unit gross. Singular solutions are retained as failures. Eigenvectors are orthogonal; their signs are oriented deterministically, and eigenvalue separation is reported.

A component can rotate or exchange rank. Components are therefore called PC1/PC2/PC3, not unconditionally level/slope/curvature. The residual includes omitted components, nonlinear pricing and model changes. These risk hedges provide no alpha claim.

## 5. Validation and interpretation

Tests cover calendar weighting, leap years, known-realized cutoffs, quote-grid direction, marked cash conservation, reserve increases, DV01 finite differences, PCA reconstruction, full attribution and future-data perturbations. Real records add source-agreement and exclusion outputs. All results remain retrospective: GSW is revised and usually published weekly; vendor metadata lack a full original-release archive. Neither prior-window fitting nor a download date establishes complete point-in-time data.

The frozen [protocol](PROTOCOL.json) predates outcome inspection. Raw licensed data and their derived real reports remain private. Public curve outputs are generated from the final code, with source hashes in [run.json](../reports/curve/run.json). Full [daily risk](../reports/curve/daily_risk.csv.gz) and [PCA](../reports/curve/pca.csv.gz) model outputs are compressed for download; [annual slices](../reports/curve/annual.csv) are readable directly.

## Source-column cross-check

Across the warm-up and study source, 22,510 finite published-yield comparisons include 11 values beyond nominal four-decimal rounding. Maximum discrepancy is 0.030075 bp; five published tenor values are absent while parameters are available. The parameter-based model remains unchanged, and these source differences are retained in [source_check.json](../reports/curve/source_check.json). Their cause has not been independently established. This check is not reported as exact equality.
