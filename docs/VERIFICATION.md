# Verification record — 30 October 2026

The packaged project was installed in a new Python 3.12 environment, outside its source directory, using `requirements.lock.txt`. Dependency checks and **10 tests** passed. The offline policy demo and the actual GSW curve report both ran successfully. Regenerated curve results matched the preceding isolated run within numerical tolerance.

Tests cover monthly calendar-day weights, effective dates, realized-information cutoffs, quote-grid rounding, bp-to-dollar conversion, paired variation accounting, reserve pressure, DV01 and full repricing, prior-window PCA and invariance to future observations. These checks validate specified mechanics; they do not prove a trading edge or historical data availability.

The source check is deliberately retained: 11 of 22,510 finite published-yield comparisons exceed nominal four-decimal rounding tolerance; the maximum difference is 0.0301 bp. Five published comparison values are missing. See [the exact check](../reports/curve/source_check.json). The research uses the declared Svensson parameters rather than silently replacing those values.

[Run fingerprint](../reports/curve/run.json) · [Annual model diagnostics](../reports/curve/annual.csv) · [Tests](../tests/test_rates.py) · [Current CI](https://github.com/Mingju-Zhang-CBS/macro-rates-research/actions)

Licensed contract histories remain private and exploratory because composite-unit documentation, publication timing and output rights are unresolved. No licensed trading result is certified by the public-data curve checks.
