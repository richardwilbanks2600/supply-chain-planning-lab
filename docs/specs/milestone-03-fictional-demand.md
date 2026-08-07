# Milestone 03: Translate FRED market pace into fictional demand

## Status

Revised scenario approved on 2026-08-07.

## Goal

Teach how an external market indicator can drive a fictional internal-demand
scenario through visible business assumptions without presenting the
assumptions as observed facts or a forecast.

## Approved FRED source

The project packages a processed snapshot of the national FRED `PERMIT` series
from January 2000 through December 2025. It contains 312 monthly observations
in `thousands_of_units_saar`. The snapshot was retrieved on 2026-08-07 through
the project's existing FRED API workflow; the exact raw response remains in
the locally ignored `data/raw/` evidence directory.

The packaged snapshot makes the teaching scenario reproducible. It does not
update when the dashboard reruns. Refreshing it must be an explicit,
reviewable data-maintenance action.

## Approved fictional dimensions

Products:

- `WIN-2436`: 24 x 36 Vinyl Window
- `WIN-3648`: 36 x 48 Vinyl Window
- `DOOR-3680`: 36 x 80 Insulated Exterior Door

Customers:

- Building Houses Company (`builder`)
- Building Supply Company (`distributor`)
- Building Remodeler (`remodeler`)

## Meaning of pace

FRED reports `PERMIT` as thousands of housing units at a seasonally adjusted
annual rate (SAAR). A value of `1,500.0` describes an annualized pace of
approximately 1.5 million housing units after seasonal adjustment. It does not
mean 1.5 million permits were issued in that month.

The scenario divides the annualized rate by 12 to obtain a seasonally adjusted
monthly pace proxy:

```text
monthly housing pace = FRED PERMIT value x 1,000 / 12
```

For `1,500.0`, the monthly pace is `125,000`. This remains a pace, not an
observed monthly permit count.

## Approved demand model

The default scenario assumptions are:

- Three-month lag from permit month to demand month
- Company market share: `0.10%`
- Units per addressable home:
  - 24 x 36 Vinyl Window: `6`
  - 36 x 48 Vinyl Window: `4`
  - 36 x 80 Insulated Exterior Door: `1`
- Customer allocation:
  - Building Houses Company: `50%`
  - Building Supply Company: `30%`
  - Building Remodeler: `20%`
- Cancellations: none

The calculation is:

```text
monthly housing pace = lagged FRED value x 1,000 / 12
addressable homes = monthly housing pace x company market-share percentage
product demand = round(addressable homes x product units per home)
customer demand = whole-unit allocation of product demand to customers
```

The dashboard exposes company market share, customer allocation, and each
product's units per home as sliders. Slider changes recalculate the scenario
deterministically from the same FRED snapshot; no random demand is generated.

Because a three-month lag is used and the FRED snapshot begins in January
2000, derived demand begins in April 2000. Calculations stop at December 2025,
producing 309 demand months and 2,781 customer-product-month records.

## Manual example

Given `PERMIT = 1,500.0`, the default assumptions produce:

```text
monthly housing pace = 1,500 x 1,000 / 12 = 125,000
addressable homes = 125,000 x 0.10% = 125
24 x 36 window demand = 125 x 6 = 750 units
36 x 48 window demand = 125 x 4 = 500 units
exterior-door demand = 125 x 1 = 125 units
total product demand = 1,375 units
```

The 750 small-window units allocate as `375`, `225`, and `150` units across
the three customers. When percentages produce fractional units, the largest
fractional remainders receive the remaining whole units so customer demand
always equals total product demand.

## Source lineage

Every derived record retains:

- Demand month and source FRED month
- FRED SAAR value and calculated monthly housing pace
- Company market-share assumption
- Customer and allocation percentage
- Product, product attachment rate, and calculated finished units

The lineage makes each value manually traceable to FRED plus approved
assumptions. The model is fictional and does not establish that national
permits cause this company's orders.

## In scope

- Fixed, validated FRED `PERMIT` snapshot for 2000-2025
- Transparent pace, lag, market-share, product, and allocation calculations
- Interactive dashboard scenario sliders
- Default-scenario CLI inspection and filtering
- Offline tests and learner documentation

## Out of scope

- Cancellations, random variation, or customer-specific events
- Forecasting, forecast performance, or causal estimation
- Inventory, backlog, shipment, material, capacity, or scheduling calculations
- Optimization, databases, or deployment

## Acceptance criteria

1. The packaged FRED snapshot contains all 312 unique months from January 2000
   through December 2025 and requires no runtime network access.
2. The default model produces 309 demand months using a visible three-month
   lag and retains source lineage on every record.
3. Company market share and units-per-home values are finite and nonnegative.
4. Customer allocations cover all customers and total exactly 100 percent.
5. Customer whole-unit allocations preserve each calculated product total.
6. Dashboard sliders recalculate deterministic values from the fixed snapshot.
7. No cancellation, forecast, inventory, or production rules are introduced.
8. Tests use packaged or temporary data and never contact FRED.
