# Milestone 04: Baseline forecasting and forecast performance

## Status

Approved on 2026-08-07.

## Goal

Teach how simple one-month-ahead forecasts use only information available
before the forecast month, and how forecast error and bias reveal different
performance characteristics.

## Approved forecast grain and evaluation period

Forecasts are calculated for monthly product demand summed across customers.
Customer allocations remain part of the demand scenario, but the forecast
comparison occurs at product-total level so rounding differences among
customers do not obscure the baseline methods.

The common evaluation period is January 2020 through December 2025. Each
method uses earlier realized fictional demand as required and produces one
forecast per product and evaluation month.

## Approved baseline methods

### Previous month

```text
forecast(t) = realized demand(t - 1 month)
```

This method responds quickly but carries short-term increases or decreases
directly into the next month.

### Same month last year

```text
forecast(t) = realized demand(t - 12 months)
```

This is the primary baseline. It preserves yearly timing patterns and is easy
to verify, but it responds slowly when the market level changes.

"Primary" means the designated reference method, not the method expected to
have the lowest error. Because the upstream FRED series is seasonally adjusted,
the comparison may show that a shorter-history baseline performs better.

### Trailing three-month average

```text
forecast(t) = [realized(t-1) + realized(t-2) + realized(t-3)] / 3
```

This method smooths short-term variation. It can lag during sustained rises or
falls because older values retain equal weight.

All three are one-month-ahead baselines and use internal-demand history only.
They do not use the FRED source value for the forecast month.

## Manual example

Assume a product has these realized fictional values:

| Period | Actual units |
| --- | ---: |
| 2023-01 | 100 |
| 2023-10 | 90 |
| 2023-11 | 105 |
| 2023-12 | 120 |
| 2024-01 | 130 |

For January 2024:

- Previous month forecast: `120`; error: `130 - 120 = +10`
- Same month last year forecast: `100`; error: `130 - 100 = +30`
- Trailing three-month forecast: `(90 + 105 + 120) / 3 = 105`; error:
  `130 - 105 = +25`

## Approved error measures

```text
error = realized demand - forecast
absolute error = |error|
MAE = average absolute error
bias = average error
```

A positive error or bias means the method underforecast demand. A negative
value means it overforecast demand. MAE describes typical error magnitude;
bias describes direction and can hide offsetting positive and negative errors.

Calculations retain full precision. The CLI and dashboard round displayed
forecast values and metrics to one decimal place.

## Relationship to FRED

The realized internal-demand history is derived from the approved FRED market-
pace model, so these baselines remain indirectly tied to FRED. They
intentionally use only past internal demand to establish a fair benchmark.

The next milestone will distinguish demand periods whose lagged FRED driver is
already known from longer horizons that require a forecast of future FRED
values. It will compare an explicit FRED-informed approach against these
baselines.

## In scope

- Product-month demand aggregation
- Three approved one-month-ahead baseline methods
- Common 2020-2025 evaluation period
- Signed error, absolute error, MAE, and bias
- CLI and dashboard comparison views
- Recalculation when demand-scenario sliders change
- Offline tests with a manually verified example

## Out of scope

- Selecting methods automatically from performance
- Forecasting FRED or using future FRED observations
- Weighted, exponential, or optimized moving averages
- Prediction intervals or statistical significance tests
- Inventory, production, capacity, or optimization

## Related rolling-average learning section

The Milestone 10 Learning Guide compares different simple-moving-average window
lengths, weighted moving averages, and simple exponential smoothing. It explains
the mathematics and the tradeoff between responsiveness and smoothing. That
explanation does not change the approved three-month baseline in this milestone.

## Acceptance criteria

1. Every forecast uses only generated internal demand preceding its forecast period.
2. All methods are evaluated over January 2020 through December 2025 at
   product-month level.
3. The three methods match the manual example exactly.
4. Error signs, MAE, and bias follow the approved definitions.
5. CLI and dashboard calculations share the same forecasting module.
6. Dashboard slider changes recalculate realized fictional demand and all baselines.
7. Forecasts and realized fictional demand are visually and textually distinguishable.
8. Tests require no API key and never contact FRED.
