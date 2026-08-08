# Milestone 05: FRED-informed demand forecasting

## Status

Approved on 2026-08-07.

## Goal

Teach the difference between translating an already-known leading indicator
into demand and forecasting demand from a leading indicator whose future value
is still unknown.

## Approved forecast design

The backtest uses successive monthly FRED forecast origins from December 2019
through December 2024. At each origin, the `PERMIT` observation for that month
is treated as the latest available external value. The model evaluates demand
horizons 1 through 12 months ahead.

The approved demand relationship remains:

```text
demand month = FRED driver month + 3 months
```

Therefore:

- Demand horizons 1-3 use FRED observations dated at or before the forecast
  origin. Their driver status is `known`.
- Demand horizons 4-12 require FRED observations dated after the forecast
  origin. Their driver status is `forecasted`.

The forecast grain is monthly product demand across all customers, matching
Milestone 4. The default demand assumptions and dashboard sliders continue to
control company market share and product units per home.

## Approved FRED baseline

The first FRED method is a recursive previous-month naive forecast:

```text
forecasted FRED value at every future driver month
    = FRED value at the forecast origin
```

For example, if December 2019 is the forecast origin and its FRED value is
`1,000.0`, every FRED driver month after December 2019 uses `1,000.0` in that
origin's forecast. This establishes a transparent benchmark before more
complex FRED methods are considered.

## Manual example

Assume:

- Forecast origin: December 2019
- December 2019 FRED value: `1,000.0`
- Actual January 2020 FRED value: `1,100.0`
- Demand lag: three months
- Company market share: `0.10%`
- Small windows per home: `6`

For demand horizon 4, the target is April 2020 and the required driver is
January 2020. January was not known at the December origin, so the naive FRED
forecast uses `1,000.0`:

```text
forecast monthly pace = 1,000 x 1,000 / 12 = 83,333.3
forecast addressable homes = 83,333.3 x 0.10% = 83.3333
forecast small-window demand = round(83.3333 x 6) = 500
```

The actual January driver of `1,100.0` produces:

```text
actual monthly pace = 1,100 x 1,000 / 12 = 91,666.7
actual addressable homes = 91,666.7 x 0.10% = 91.6667
actual small-window demand = round(91.6667 x 6) = 550
error = actual - forecast = 550 - 500 = +50
```

A positive error means underforecasting, consistent with Milestone 4.

## Rolling-origin evaluation

Every forecast origin produces a complete 12-month demand outlook. With 61
origins, 12 horizons, and three products, the default backtest contains 2,196
records:

- 549 known-driver records at horizons 1-3
- 1,647 forecasted-driver records at horizons 4-12

MAE and bias are reported separately for known and forecasted drivers and for
each horizon. Known-driver records should have zero error because actual demand
was generated from the same FRED value and approved translation rule.

## Interpretation limits

Zero known-driver error demonstrates calculation consistency, not real-world
predictive accuracy. The internal-demand history was constructed from FRED
using the same structural rule.

The backtest uses the fixed currently revised FRED snapshot. It prevents
future-period leakage by date, but it does not reconstruct what each value
looked like before later revisions. It also treats the observation dated at
the forecast origin as available and does not model publication delay. These
limitations must remain visible until an ALFRED vintage workflow and release
calendar are separately approved.

## In scope

- Rolling monthly origins from December 2019 through December 2024
- Demand horizons 1-12
- Known versus forecasted driver classification
- Previous-month naive FRED forecast
- Translation through the approved demand model
- Product-level actual, forecast, error, MAE, and bias
- Source-period and driver-value lineage in CLI and dashboard views
- Recalculation when demand assumptions change

## Out of scope

- ALFRED vintages and real publication-delay simulation
- Seasonal, moving-average, exponential, regression, or machine-learning FRED
  forecasts
- Automatic method selection or parameter fitting
- Prediction intervals
- Inventory, production, capacity, or optimization

## Acceptance criteria

1. Each record identifies forecast origin, horizon, demand month, driver month,
   driver status, actual driver, and driver value used.
2. Horizons 1-3 are always `known`; horizons 4-12 are always `forecasted`.
3. Known-driver forecasts reproduce product demand with zero error.
4. The horizon-4 manual example produces a 500-unit forecast, 550-unit actual,
   and +50-unit error.
5. The default backtest contains 2,196 records across 61 origins.
6. MAE and bias use the definitions approved in Milestone 4.
7. CLI and dashboard calculations share one driver-forecasting module.
8. Tests require no API key and never contact FRED.
