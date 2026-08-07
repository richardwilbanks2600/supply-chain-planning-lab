# Milestone 03: Introduce a fictional demand scenario

## Status

Approved on 2026-08-07.

## Goal

Help a learner distinguish internal customer demand from an external market
indicator by providing one fixed, inspectable order-history scenario for a
fictional building-components manufacturer.

## Approved scenario

The fictional products are:

- `WIN-2436`: 24 x 36 Vinyl Window
- `WIN-3648`: 36 x 48 Vinyl Window
- `DOOR-3680`: 36 x 80 Insulated Exterior Door

The fictional customers are:

- Building Houses Company (`builder`)
- Building Supply Company (`distributor`)
- Building Remodeler (`remodeler`)

The history covers every month from January 2024 through December 2025. The
CSV contains exactly one row for every month, customer, and product
combination, including rows with zero demand.

## Meaning and calculation of demand

Internal demand is the final accepted quantity of finished units assigned to
the customer's requested ship month, net of cancellations:

```text
demand units = gross order units - cancelled units
```

For example:

| Customer | Product | Gross orders | Cancelled | Demand |
| --- | --- | ---: | ---: | ---: |
| Building Houses Company | 24 x 36 Vinyl Window | 120 | 5 | 115 |
| Building Supply Company | 24 x 36 Vinyl Window | 80 | 2 | 78 |

For these two rows, total product demand is `115 + 78 = 193` finished units.
Aggregations only sum row-level values; they do not allocate, forecast, or
adjust demand.

The requested ship month remains the demand period even if a future shipment
occurs later. Demand is not reduced by inventory or production capacity, and
it is not a measure of shipments, production, or revenue.

## Static-data rule

The synthetic history is a fixed, version-controlled CSV packaged with the
project. It is not regenerated when the CLI or dashboard runs. Runtime code
loads and validates the stored records, making dashboard results and tests
reproducible. Any future scenario change must be a deliberate reviewable edit.

## Separation from the external indicator

FRED `PERMIT` remains an external construction-market indicator measured in
thousands of housing units at a seasonally adjusted annual rate. Internal
demand is measured in finished product units. The two datasets may be shown in
separate views, but Milestone 3 does not convert permits into orders, claim a
causal relationship, or use permits to calculate company demand.

## Data-quality rules

- The CSV header and field order are fixed and validated.
- Periods use canonical `YYYY-MM` values.
- Customer names, customer types, product SKUs, and product names must match
  the approved catalog.
- Gross orders, cancellations, and demand are nonnegative whole units.
- Cancellations cannot exceed gross orders.
- Every row must satisfy the approved demand equation.
- Duplicate month/customer/product combinations fail validation.
- The packaged scenario must contain all 216 approved combinations and no
  others.

## In scope

- A static two-year synthetic order-history CSV
- Runtime validation and transparent additive summaries
- Inclusive month, customer, and product filtering
- A CLI summary that requires no API key or network call
- A dashboard view that presents internal demand separately from FRED
- Offline tests and learner documentation

## Out of scope

- Random or runtime demand generation
- Forecasting, forecast error, or causal modeling
- Inventory, backlog, shipment, material, capacity, or scheduling calculations
- Optimization, databases, or deployment

## Acceptance criteria

1. The packaged dataset contains 216 unique rows covering the approved grid.
2. Loading demand never contacts FRED and does not require an API key.
3. Invalid dimensions, quantities, calculations, or duplicate combinations
   fail with a clear row-specific error.
4. CLI and dashboard totals equal the sum of the selected validated rows.
5. Filters are inclusive and do not mutate the source records.
6. Internal demand is labeled in finished units and remains visibly separate
   from the differently scaled FRED indicator.
7. Dashboard reruns read the same static values.
8. Tests use only committed or temporary files and never contact FRED.
