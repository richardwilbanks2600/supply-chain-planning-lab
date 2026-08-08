# Milestone 03: Translate FRED market pace into fictional demand

## Status

Revised expected-versus-realized demand model approved on 2026-08-07.

## Goal

Teach how an external market indicator can anchor a fictional internal-demand
scenario without making company demand a perfect copy of FRED. The model keeps
expected demand, static company variation, and realized demand visibly separate.

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

The project also packages 933 fixed product-month realization-factor records
covering April 2000 through February 2026. The factors were generated once by
`scripts/generate_demand_realization_factors.py` with seed `7970`, reviewed, and
committed. The dashboard loads the committed CSV; it never generates random
variation at runtime.

Each realization factor combines:

- a monthly company-variation factor;
- a mild product-seasonal factor;
- a small product-specific factor; and
- an occasional unusual-month factor.

Every final factor is between `0.75` and `1.25`. More than 95% are between
`0.85` and `1.15`, so most realized demand stays within 15% of the FRED-driven
expectation while occasional months approach 25% above or below it.

The displayed demand history uses 927 factor rows through December 2025. Six
additional rows for January-February 2026 support the forward inventory and
safety-stock calculations that need months just beyond the visible history.

The calculation is:

```text
monthly housing pace = lagged FRED value x 1,000 / 12
addressable homes = monthly housing pace x company market-share percentage
FRED-driven expected product demand
    = round(addressable homes x product units per home)
realized product demand
    = round(expected product demand x static realization factor)
customer demand = whole-unit allocation of realized product demand to customers
```

The dashboard exposes company market share, customer allocation, and each
product's units per home as sliders. Slider changes recalculate expectation and
scale realized demand with the same committed factors. No factor changes when
the dashboard reruns.

Because a three-month lag is used and the FRED snapshot begins in January
2000, derived demand begins in April 2000. Calculations stop at December 2025,
producing 309 demand months and 2,781 customer-product-month records.

## Manual example

Given `PERMIT = 1,500.0`, the default assumptions produce:

```text
monthly housing pace = 1,500 x 1,000 / 12 = 125,000
addressable homes = 125,000 x 0.10% = 125
24 x 36 window expected demand = 125 x 6 = 750 units
36 x 48 window expected demand = 125 x 4 = 500 units
exterior-door expected demand = 125 x 1 = 125 units
total expected product demand = 1,375 units

April 2000 realization factors:
24 x 36 window = 1.0582; realized demand = round(750 x 1.0582) = 794
36 x 48 window = 1.0617; realized demand = round(500 x 1.0617) = 531
exterior door = 1.0529; realized demand = round(125 x 1.0529) = 132
total realized demand = 1,457 units
```

The 794 realized small-window units allocate as `397`, `238`, and `159` across
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
- FRED-driven expected customer units
- Company, seasonal, product, and unusual-month factor components
- Final realization factor, variation type, and realized customer units

The lineage makes each value manually traceable to FRED plus approved
assumptions. The model is fictional and does not establish that national
permits cause this company's orders.

## In scope

- Fixed, validated FRED `PERMIT` snapshot for 2000-2025
- Fixed, validated demand-realization factors for every product-month
- Transparent expectation, variation, realization, and allocation calculations
- Interactive dashboard scenario sliders
- Default-scenario CLI inspection and filtering
- Offline tests and learner documentation

## Out of scope

- Cancellations, runtime randomness, or customer-specific events
- Forecasting, forecast performance, or causal estimation
- Inventory, backlog, shipment, material, capacity, or scheduling calculations
- Optimization, databases, or deployment

## Acceptance criteria

1. The packaged FRED snapshot contains all 312 unique months from January 2000
   through December 2025 and requires no runtime network access.
2. The default model produces 309 demand months using a visible three-month
   lag and retains source and realization-factor lineage on every record.
3. Company market share and units-per-home values are finite and nonnegative.
4. Customer allocations cover all customers and total exactly 100 percent.
5. The factor dataset covers all 933 product-month combinations, keeps every
   factor between 0.75 and 1.25, and is never regenerated at runtime.
6. Customer whole-unit allocations preserve each realized product total.
7. Dashboard sliders recalculate repeatable values from the fixed inputs.
8. No cancellation, forecast, inventory, or production rules are introduced.
9. Tests use packaged or temporary data and never contact FRED.
