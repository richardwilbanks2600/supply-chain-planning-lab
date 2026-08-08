# Milestone 06: Inventory and net production requirements

## Status

Approved on 2026-08-07.

## Goal

Teach how a demand forecast, available finished-goods inventory, and a simple
safety-stock policy become a monthly net production requirement.

## Approved planning design

One inventory plan uses the 12-month FRED-informed product-demand forecast from
a selected Milestone 5 forecast origin. The grain is month and product across
all customers.

The first policy uses:

- adjustable starting inventory for each product;
- safety stock equal to an adjustable percentage of the following month's
  forecast, defaulting to `25%`;
- zero scheduled receipts;
- production available in the month in which it is planned; and
- projected ending inventory carried into the following month.

Default starting inventory is `300` small windows, `200` large windows, and
`50` exterior doors. These fictional values preserve the product mix for 50
homes and are starting assumptions, not optimized recommendations.

The calculation requires one supporting forecast beyond the displayed
12-month plan so the final displayed month can still use the following month's
forecast as its safety-stock basis. That supporting month is not itself part of
the production plan.

## Definitions and formulas

```text
inventory position = beginning inventory + scheduled receipts

safety-stock target
    = round(following month's forecast demand x safety-stock percentage)

net production requirement
    = max(0, forecast demand + safety-stock target - inventory position)

projected ending inventory
    = inventory position + net production requirement - forecast demand
```

`Inventory position` is deliberately narrow in this milestone. It includes
only finished goods already on hand plus scheduled receipts. Scheduled receipts
are fixed at zero until an open-order policy is approved.

## Manual example

Assume April's small-window plan has:

- beginning inventory: `120`
- scheduled receipts: `0`
- forecast demand: `500`
- following-month forecast: `400`
- safety-stock percentage: `25%`

Then:

```text
safety-stock target = round(400 x 25%) = 100
inventory position = 120 + 0 = 120
net production requirement = max(0, 500 + 100 - 120) = 480
projected ending inventory = 120 + 480 - 500 = 100
```

May begins with the `100` units projected to remain at the end of April.

If beginning inventory were `700` instead, net production would be zero and
projected ending inventory would be `200`. The model does not discard excess
stock simply because it exceeds the safety target.

## Interpretation limits

The safety-stock percentage is an explainable teaching policy, not a
statistical recommendation. It does not yet use a service level, forecast-error
distribution, supplier lead time, or supplier reliability. Those methods will
be compared after the required inputs exist and are separately approved.

The plan uses forecast demand, not hindsight actual demand. Production is
assumed to appear immediately in its planned month, so the plan does not yet
test lead-time or capacity feasibility. A production requirement is therefore
not the same thing as an executable production schedule.

## In scope

- Select one historical FRED forecast origin
- Plan 12 months at product-month grain
- Adjustable starting finished-goods inventory by product
- Adjustable following-month-demand safety-stock percentage
- Zero scheduled receipts shown explicitly
- Monthly inventory roll-forward
- Net production requirement and projected ending inventory
- Shared CLI and dashboard calculations
- A visible manual example and policy limitations

## Out of scope

- Statistical safety-stock models
- Service-level optimization
- Actual-demand inventory simulation
- Backorders, lost sales, cancellations, or spoilage
- Scheduled receipts, purchase orders, or supplier lead time
- Bills of materials, raw materials, capacity, or production scheduling
- Optimization

## Acceptance criteria

1. Every row shows forecast demand, beginning inventory, scheduled receipts,
   inventory position, safety-stock basis and target, net production, and
   projected ending inventory.
2. Projected ending inventory for a product becomes its next month's beginning
   inventory.
3. Net production cannot be negative.
4. The manual example produces a 100-unit safety target, 480-unit production
   requirement, and 100-unit projected ending inventory.
5. The default plan contains 36 displayed records: 12 months by three products.
6. The thirteenth forecast month is used only as the final safety-stock basis.
7. CLI and dashboard calculations share one inventory-planning module.
8. Tests require no API key and never contact FRED.
