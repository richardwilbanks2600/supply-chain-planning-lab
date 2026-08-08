# Data dictionary

This dictionary describes the version-controlled inputs and the principal
structured outputs produced by Supply Chain Planning Lab. All planning records
are monthly. Empty values are not silently imputed: required missing values
raise a validation error, while FRED's `.` observation marker is explicitly
skipped during transformation.

## Source datasets

### FRED permit snapshot

File: `src/supply_chain_planning_lab/resources/fred_permit_2000_2025.csv`

Provenance: Federal Reserve Bank of St. Louis FRED `PERMIT` series, retrieved
for January 2000 through December 2025 and committed as a fixed teaching
snapshot. It contains 312 chronological monthly observations. FRED reports the
series as thousands of housing units at a seasonally adjusted annual rate
(SAAR). A row is an external market indicator, not an order or company demand.

| Field | Type | Unit / allowable values | Meaning and transformation |
|---|---|---|---|
| `series_id` | string | `PERMIT` | FRED series identifier; any other value is rejected. |
| `period` | string | `YYYY-MM` | Observation month, derived from FRED's observation date. Duplicate or malformed months are rejected. |
| `value` | number | thousands of units SAAR | Valid finite FRED observation. The live transformer skips FRED's `.` marker rather than filling it. |
| `unit` | string | `thousands_of_units_saar` | Canonical project unit assigned during transformation. |

### Supplier delivery history

File: `src/supply_chain_planning_lab/resources/supplier_delivery_history.csv`

Provenance: fixed fictional teaching data. It is not observed supplier or FRED
data. Every required field must be present and valid; missing values are not
filled.

| Field | Type | Unit / allowable values | Meaning and transformation |
|---|---|---|---|
| `supplier_id` | string | approved supplier ID | Supplier associated with the component. |
| `component_sku` | string | approved component SKU | Purchased component delivered. |
| `delivery_id` | string | unique text ID | Stable delivery observation identifier. |
| `promised_lead_months` | integer | months, nonnegative | Planned elapsed months. |
| `actual_lead_months` | integer | months, nonnegative | Actual elapsed months. `actual <= promised` is on time. |
| `ordered_quantity` | integer | component units, positive | Quantity ordered. |
| `received_quantity` | integer | component units, nonnegative | Quantity received. `received >= ordered` is in full. |

## Internal demand output

Grain: one requested ship month, customer, and product. Provenance: fixed FRED
snapshot, learner-visible `DemandAssumptions`, and the fixed realization-factor
dataset. The calculation converts SAAR thousands to expected demand, applies a
product-month realization factor, then allocates realized whole units with the
same repeatable rounding rule. Cancellations are zero.

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `period` | string | `YYYY-MM` | Fictional requested ship month. |
| `fred_period` | string | `YYYY-MM` | Source permit month, three months before `period`. |
| `fred_value_saar_thousands` | number | thousands of units SAAR | FRED value used in the calculation. |
| `monthly_housing_pace` | number | homes/month | `(FRED value * 1000) / 12`. This is a rate conversion, not observed monthly permits. |
| `company_market_share_percent` | number | 0-100 percent | Fictional share of addressable housing pace. |
| `customer` | string | approved customer name | Fictional customer receiving allocated demand. |
| `customer_type` | string | `builder`, `distributor`, `remodeler` | Customer segment label. |
| `customer_allocation_percent` | number | percent; all customers total 100 | Customer share of product demand. |
| `product_sku` | string | `WIN-2436`, `WIN-3648`, `DOOR-3680` | Fictional product identifier. |
| `product_name` | string | approved product name | Learner-facing product label. |
| `units_per_home` | number | product units/home | Fictional product attachment rate. |
| `fred_expected_demand_units` | integer | product units | Customer share of demand implied by FRED and visible assumptions before static variation. |
| `company_variation_factor` | number | positive multiplier | Monthly company-wide component of the static realization factor. |
| `product_seasonal_factor` | number | positive multiplier | Mild recurring month-of-year component for the product. |
| `product_variation_factor` | number | positive multiplier | Small fixed product-month component. |
| `unusual_event_factor` | number | positive multiplier | Usually 1.0; occasional fixed unusual-month adjustment. |
| `realization_factor` | number | 0.75-1.25 | Final committed multiplier applied to expected product demand. |
| `variation_type` | string | `typical`, `unusual` | Identifies whether an unusual-month adjustment is present. |
| `demand_units` | integer | product units | Customer share of realized fictional demand after static variation. |
| `unit` | string | `finished_units` | Unit label for expected and realized demand. |

### Demand realization factors

File: `src/supply_chain_planning_lab/resources/demand_realization_factors.csv`

Provenance: fixed fictional teaching data generated once with seed `7970` by
`scripts/generate_demand_realization_factors.py`. Runtime planning reads the
committed CSV and never regenerates it. Grain: requested ship month and product.
The 933 rows cover April 2000 through February 2026 for all three products.
The final six rows support forward inventory and safety-stock calculations;
the displayed realized-demand history still ends in December 2025.

## FRED-informed forecast output

Grain: forecast origin, demand horizon, and product. For horizons 1-3, the
three-month lag means the FRED driver is already known at the origin. Horizons
4-12 carry the latest FRED value at the origin forward. Error is
`realized demand - forecast`; a positive value means underforecasting. A known
FRED driver can still have demand error because the realization factor is not
used by the forecast. This uses revised history, not historical FRED vintages.

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `forecast_origin` | string | `YYYY-MM` | Last information month available to the simulated planner. |
| `horizon_months` | integer | 1-12 | Months between forecast origin and demand month. |
| `demand_period` | string | `YYYY-MM` | Month being forecast. |
| `driver_period` | string | `YYYY-MM` | FRED month linked to demand by the approved lag. |
| `driver_status` | string | `known`, `forecasted` | Whether the driver was available at the origin. |
| `driver_method` | string | approved method label | Rule used for the FRED value. |
| `actual_driver_saar_thousands` | number | thousands of units SAAR | Revised-history actual FRED driver. |
| `driver_value_used_saar_thousands` | number | thousands of units SAAR | Known or carried-forward FRED driver used. |
| `driver_error_saar_thousands` | number | thousands of units SAAR | Actual driver minus value used. |
| `product_sku`, `product_name` | string | approved product | Product identity. |
| `actual_demand_units` | integer | product units | Realized fictional demand from the static demand dataset. |
| `forecast_demand_units` | integer | product units | FRED-driven expected demand from the driver available at the origin. |
| `error_units` | integer | product units | Realized demand minus forecast demand. |
| `absolute_error_units` | integer | product units | Absolute value of `error_units`. |

## Finished-goods inventory output

Grain: forecast origin, horizon, and product. Scheduled receipts are currently
zero. Production is treated as available in the requirement month.

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `forecast_origin` | string | `YYYY-MM` | Forecast origin shared by the plan. |
| `horizon_months` | integer | 1-12 | Month number in the plan. |
| `period` | string | `YYYY-MM` | Requirement month. |
| `product_sku`, `product_name` | string | approved product | Product identity. |
| `forecast_demand_units` | integer | product units | Gross forecast demand. |
| `beginning_inventory_units` | integer | product units | Inventory carried into the month. |
| `scheduled_receipts_units` | integer | product units | Previously planned receipts; currently zero. |
| `inventory_position_units` | integer | product units | Beginning inventory plus scheduled receipts. |
| `safety_stock_basis_period` | string | `YYYY-MM` | Following forecast month used by the policy. |
| `safety_stock_basis_units` | integer | product units | Following-month forecast. |
| `safety_stock_percent` | number | 0-100 percent | Learner-selected protection percentage. |
| `safety_stock_target_units` | integer | product units | Ceiling of basis units times safety-stock percent. |
| `net_production_requirement_units` | integer | product units | Units required to cover demand and target after available inventory. |
| `projected_ending_inventory_units` | integer | product units | Inventory projected after demand and planned production. |

## Procurement output

Grain: forecast origin, horizon, and purchased component. Requirements are BOM
explosions of finished-goods production. Nested `production_source_units` is
serialized as JSON when downloaded as CSV.

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `forecast_origin`, `horizon_months`, `period` | string/integer | monthly plan keys | Shared planning origin, horizon, and requirement month. |
| `component_sku`, `component_name` | string | approved component | Component identity. |
| `unit` | string | component-specific | Purchasing unit such as pieces or square feet. |
| `supplier_id`, `supplier_name` | string | approved supplier | Assigned supplier. |
| `planned_lead_months` | integer | months | Time offset used for order release. |
| `gross_requirement_units` | integer | component units | Total BOM requirement across products. |
| `production_source_units` | object | product SKU to units | Finished-goods production lineage behind the requirement. |
| `beginning_inventory_units` | integer | component units | Raw-material inventory at month start. |
| `scheduled_receipt_units` | integer | component units | Open receipt quantity. |
| `usable_scheduled_receipt_units` | integer | component units | Full or risk-adjusted quantity credited by policy. |
| `receipt_at_risk_units` | integer | component units | Scheduled amount not credited after reliability adjustment. |
| `inventory_position_units` | integer | component units | Inventory plus usable scheduled receipt. |
| `safety_stock_method` | string | `none`, `percentage`, `statistical` | Selected protection rule. |
| `safety_stock_target_units` | integer | component units | Whole-unit protection target. |
| `net_purchase_receipt_units` | integer | component units | Recommended receipt quantity after netting. |
| `projected_ending_inventory_units` | integer | component units | Expected month-end raw material. |
| `recommended_order_release_period` | string | `YYYY-MM` | Receipt month shifted earlier by planned lead time. |
| `release_status` | string | `past_due`, `release_now`, `future`, `no_action` | Timing classification relative to the forecast origin. |

## Capacity outputs

The dashboard provides product-allocation and work-center-load CSVs. These are
finite-capacity teaching plans, not optimized job sequences. Missing capacity
or inventory keys are rejected rather than imputed.

### Product allocation

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `forecast_origin`, `horizon_months`, `period` | string/integer | monthly plan keys | Shared origin, horizon, and production month. |
| `work_center_id`, `work_center_name` | string | approved work center | Resource assigned to the product. |
| `product_sku`, `product_name` | string | approved product | Product identity. |
| `base_production_requirement_units` | integer | product units | Unconstrained requirement from inventory planning. |
| `beginning_deferred_units` | integer | product units | Prior-month units not completed. |
| `total_requested_units` | integer | product units | Base requirement plus beginning deferred units. |
| `run_rate_units_per_hour` | number | product units/hour | Learner-adjustable rate assumption. |
| `requested_run_hours` | number | hours | Requested units divided by run rate. |
| `capacity_factor` | number | 0-1 ratio | Proportional share achievable after setup time. |
| `planned_production_units` | integer | product units | Whole units scheduled within capacity. |
| `planned_run_hours` | number | hours | Planned units divided by run rate. |
| `ending_deferred_units` | integer | product units | Requested units not scheduled; carried forward. |

### Work-center load

| Field | Type | Unit / allowable values | Meaning |
|---|---|---|---|
| `forecast_origin`, `horizon_months`, `period` | string/integer | monthly plan keys | Shared origin, horizon, and production month. |
| `work_center_id`, `work_center_name` | string | approved work center | Capacity resource. |
| `working_days`, `shifts_per_day`, `hours_per_shift` | integer/number | calendar assumptions | Inputs to regular capacity hours. |
| `regular_capacity_hours` | number | hours | Days times shifts times hours per shift. |
| `planned_downtime_percent` | number | 0 to below 100 percent | Share removed from regular hours. |
| `overtime_hours` | number | hours | Additional learner-selected capacity. |
| `effective_capacity_hours` | number | hours | Regular hours after downtime plus overtime. |
| `active_product_count` | integer | products | Products requesting positive output. |
| `required_setup_hours` | number | hours | Active products times setup hours. |
| `requested_run_hours` | number | hours | Runtime required for all requested units. |
| `required_hours` | number | hours | Setup plus requested runtime. |
| `required_utilization_percent` | number | percent | Required hours divided by effective capacity. |
| `capacity_gap_hours` | number | hours | Effective capacity minus required hours; negative means shortage. |
| `overloaded` | boolean | true/false | Whether required hours exceed effective capacity. |
| `capacity_factor` | number | 0-1 ratio | Proportion of requested runtime scheduled. |
| `scheduled_setup_hours`, `scheduled_run_hours`, `scheduled_hours` | number | hours | Capacity assigned to setup, runtime, and both combined. |
| `unused_capacity_hours` | number | hours | Nonnegative unassigned effective capacity. |
| `base_production_requirement_units` | integer | product units | Work-center total before deferred units. |
| `beginning_deferred_units` | integer | product units | Work-center backlog entering the month. |
| `total_requested_units` | integer | product units | Base plus beginning deferred units. |
| `planned_production_units` | integer | product units | Work-center total scheduled. |
| `ending_deferred_units` | integer | product units | Work-center backlog leaving the month. |

## Missing-data and rounding rules

- FRED `.` values are omitted and counted during live transformation; they are
  never converted to zero.
- Required fields, unexpected schemas, nonfinite numbers, duplicate monthly
  keys, and missing planning horizons raise explicit errors.
- Demand allocations and capacity schedules use deterministic whole-unit
  rounding so the same inputs reproduce the same output.
- The fixed FRED snapshot and fictional supplier history contain no blank
  required fields. No statistical imputation is performed anywhere.
