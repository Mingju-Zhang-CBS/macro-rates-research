# Data, Rights and Attribution

| Input | Evidence | Public treatment |
|---|---|---|
| Federal Reserve GSW | Official staff research CSV, current historical vintage; continuous zero-yield and Svensson parameter definitions | Download URL, source hash, model outputs and figures; no original-release/PIT claim |
| NY Fed EFFR | Official current historical reference-rate observations | Used as ex-post labels; trade-date observation and publication date remain different |
| WRDS/LSEG Fed Funds | Licensed individual-contract records and current contract metadata | Raw data, contract-level diagnostics, agreement tables and actual historical results private |
| IBKR | Permissioned instrument resolution and recent indicative histories | No quote dump, account details, live orders or redistribution assumption |
| Offline policy scenario | Original synthetic prices and reserve paths | Clearly labeled, fully reproducible |

The original code license does not license third-party data. Vendor composite-series unit fields are incomplete; cross-source agreement supports a price-convention diagnostic but does not substitute for the missing original unit documentation. Historical margin and executable liquidity are not verified. A source may be accessible through a subscription without allowing public redistribution of its outputs.

Public methods were written independently for this repository. Coursework provided questions and context, not code or figures for redistribution. Research direction and project selection: Mingju Zhang. Code, tests, figures and documentation were developed with AI assistance; automated verification does not establish an independent human replication or mastery claim. No employer's system or internal result is represented here.

## Primary references

- [CME 30-Day Federal Funds contract specifications](https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund/specs)
- [Federal Reserve nominal curve definitions, revision and update policy](https://www.federalreserve.gov/data/nominal-yield-curve.htm)
- [GSW paper and data](https://www.federalreserve.gov/pubs/feds/2006/200628/200628abs.html)
- [NY Fed EFFR publication](https://www.newyorkfed.org/markets/reference-rates/effr)
- [ALFRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
- [IBKR historical data limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations)

Macro releases and revised series are not currently fitted into a predictive model in this first version. Consensus-surprise data are not fabricated from changes versus the prior observation. Prospective research begins after the frozen protocol and requires separate recorded observations.
