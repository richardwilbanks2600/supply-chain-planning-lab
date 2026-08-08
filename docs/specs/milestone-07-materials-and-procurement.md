# Milestone 07: Bills of materials, procurement, and supplier uncertainty

## Status

Approved on 2026-08-07.

## Goal

Teach how planned finished-goods production becomes time-phased material
requirements, purchase recommendations, and supplier-risk-aware safety stock.

Milestone 7A establishes deterministic material planning. Milestone 7B adds a
static supplier-performance history and compares simple and statistical
safety-stock policies. No random simulation is used.

## Milestone 7A: Approved material model

### Bill of materials

| Finished product | Component | Quantity | Unit |
|---|---|---:|---|
| `WIN-2436` | Window glass | 6 | square feet |
| `WIN-2436` | Vinyl frame extrusion | 10 | linear feet |
| `WIN-2436` | Window hardware kit | 1 | kit |
| `WIN-3648` | Window glass | 12 | square feet |
| `WIN-3648` | Vinyl frame extrusion | 14 | linear feet |
| `WIN-3648` | Window hardware kit | 1 | kit |
| `DOOR-3680` | Insulated door slab | 1 | each |
| `DOOR-3680` | Door frame kit | 1 | kit |
| `DOOR-3680` | Door hardware kit | 1 | kit |

Scrap is zero in this milestone. BOM quantities are fictional teaching
assumptions, except that the glass quantities correspond to the nominal window
dimensions.

### Components, suppliers, and lead times

| Component | Supplier | Planned lead time |
|---|---|---:|
| Window glass | ClearView Glass | 2 months |
| Vinyl frame extrusion | VinylWorks | 1 month |
| Window hardware kit | Reliable Hardware | 1 month |
| Insulated door slab | SolidCore Doors | 2 months |
| Door frame kit | FrameSource | 1 month |
| Door hardware kit | Entry Hardware Co. | 1 month |

Starting raw-material inventory is adjustable. Default quantities are 5,000
square feet of glass, 7,000 linear feet of vinyl, 600 window hardware kits, and
100 units of each door component.

A fixed fictional open-order schedule provides receipts in the first two plan
months. Receipt months are stored as horizons relative to the selected
historical forecast origin so the teaching scenario remains usable at every
approved origin.

### Material formulas

```text
gross material requirement
    = sum(product net production x BOM quantity)

material inventory position
    = beginning material inventory + usable scheduled receipts

net purchase receipt requirement
    = max(0,
          gross material requirement
          + material safety-stock target
          - material inventory position)

projected ending material inventory
    = material inventory position
      + planned purchase receipt
      - gross material requirement

recommended order release month
    = material need month - planned supplier lead time
```

The plan treats a recommended purchase as arriving in the need month. If its
release month precedes the forecast origin, it is flagged `past_due`; if it
equals the origin, it is `release_now`; otherwise it is `planned`. These flags
identify timing risk but do not simulate missed production.

### Manual BOM example

Producing 100 small windows and 50 large windows requires:

```text
glass = (100 x 6) + (50 x 12) = 1,200 square feet
vinyl = (100 x 10) + (50 x 14) = 1,700 linear feet
window hardware = 100 + 50 = 150 kits
```

If glass beginning inventory is 500, a scheduled receipt is 300, the selected
safety target is 200, and gross glass requirements are 1,200:

```text
inventory position = 500 + 300 = 800
net purchase receipt = max(0, 1,200 + 200 - 800) = 600
projected ending inventory = 800 + 600 - 1,200 = 200
```

## Milestone 7B: Approved uncertainty model

The packaged supplier dataset contains six fictional historical deliveries per
supplier. Every row includes promised and actual lead time, ordered quantity,
received quantity, and whether the delivery was on time and in full.

Supplier measures are:

```text
on-time rate = on-time deliveries / deliveries

fill rate = total received quantity / total ordered quantity

OTIF rate = on-time-and-in-full deliveries / deliveries
```

The dashboard compares three material safety-stock policies:

1. `none`: zero material safety stock;
2. `percentage`: an adjustable percentage of the following month's gross
   material requirement, defaulting to 25%; and
3. `statistical`: combined demand-error and supplier-lead-time uncertainty.

The statistical policy uses:

```text
safety stock
    = z x sqrt(
        average actual lead time x material forecast-error variance
        + average monthly material demand^2 x lead-time variance
      )
```

The default service level is 95%, with `z = 1.645`. The selectable teaching
levels are 90%, 95%, 97.5%, and 99%. Material forecast-error history is derived
from Milestone 5 forecasted-driver records by translating each product error
through the BOM and aggregating by material, forecast origin, and horizon.

Risk-adjusted scheduled receipts are also shown:

```text
risk-adjusted receipt = round(scheduled receipt x supplier OTIF rate)
```

This value is an expected-availability teaching estimate, not a guarantee or a
probabilistic simulation. The learner can compare full scheduled receipts with
risk-adjusted receipts in the same planning engine.

## Interpretation limits

- BOMs, suppliers, inventories, open orders, and delivery histories are
  fictional.
- BOM scrap and yield loss are zero.
- One supplier is assigned to each component; sourcing alternatives and price
  are out of scope.
- Purchase recommendations are not automatically issued orders.
- Monthly time buckets simplify day-level lead-time and delivery behavior.
- Supplier observations are a small teaching sample and do not establish a
  stable real-world probability distribution.
- The normal-distribution service-level model is an approximation.
- The model calculates requirements and timing risk; it does not enforce
  capacity or reschedule production around shortages.

## Acceptance criteria

1. The BOM manual example produces 1,200 square feet of glass, 1,700 linear
   feet of vinyl, and 150 hardware kits.
2. Each material-month record retains production, BOM, inventory, receipt,
   safety-stock, purchasing, supplier, and release-timing lineage.
3. Default plans contain 72 material-month rows: 12 months by six components.
4. Material ending inventory rolls into the following month.
5. Net purchase requirements cannot be negative.
6. Supplier on-time, fill-rate, OTIF, average-lead-time, and lead-time-variation
   measures come from the packaged static history.
7. None, percentage, and statistical safety-stock methods are comparable.
8. Full and risk-adjusted receipt treatments use the same planning engine.
9. CLI and dashboard views use shared calculation modules.
10. Tests require no API key and never contact FRED.
