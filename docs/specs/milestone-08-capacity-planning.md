# Milestone 08: Capacity and production planning

## Status

Approved on 2026-08-07.

## Goal

Teach how a net production requirement becomes work-center load, how load is
compared with effective capacity, and how constrained capacity creates deferred
production.

## Approved work centers and rates

| Work center | Product | Default run rate |
|---|---|---:|
| Window Assembly | `WIN-2436` | 8 units per hour |
| Window Assembly | `WIN-3648` | 6 units per hour |
| Door Assembly | `DOOR-3680` | 1 unit per hour |

The two window products share one work center. Run rates are adjustable
teaching assumptions and are not measured factory standards.

## Approved calendar and availability

Each work center defaults to:

- 20 working days per month;
- one 8-hour shift per day;
- 10% planned downtime;
- four setup hours for each product with a positive monthly requirement; and
- zero overtime hours, adjustable independently by work center from 0 to 40.

```text
regular capacity hours
    = working days x shifts per day x hours per shift

effective capacity hours
    = regular capacity hours x (1 - planned downtime percentage)
      + overtime hours
```

Overtime is added after planned downtime and is therefore not reduced by the
downtime percentage in this simplified model.

## Load and utilization

```text
requested run hours
    = sum(total requested product units / product run rate)

required hours
    = requested run hours + required setup hours

capacity gap hours
    = effective capacity hours - required hours

required utilization
    = required hours / effective capacity hours
```

Required utilization may exceed 100%. A negative capacity gap identifies an
overloaded work-center month.

## Approved constrained-allocation rule

Each product's total requested units equal the current month's net production
requirement plus deferred production carried from the preceding month.

When capacity is sufficient, all requested units are planned. When a shared
work center is overloaded:

1. Setup hours for every active product are reserved first.
2. The remaining runtime is divided proportionally to each product's requested
   run hours.
3. Planned whole units are rounded down so the plan cannot exceed capacity.
4. Unplanned units become ending deferred production and carry into the next
   month.

```text
runtime capacity factor
    = min(1, available runtime hours / requested run hours)

planned product units
    = floor(total requested units x runtime capacity factor)

ending deferred units
    = total requested units - planned product units
```

No product has priority over another in this milestone.

## Manual example

Assume Window Assembly has 144 effective hours and needs:

- 800 small windows at 8 per hour = 100 run hours;
- 600 large windows at 6 per hour = 100 run hours; and
- two setups at four hours each = 8 setup hours.

```text
required hours = 100 + 100 + 8 = 208
capacity gap = 144 - 208 = -64 hours
available runtime = 144 - 8 = 136 hours
capacity factor = 136 / 200 = 0.68
```

The feasible whole-unit plan is:

```text
small windows = floor(800 x 0.68) = 544
large windows = floor(600 x 0.68) = 408
deferred small windows = 800 - 544 = 256
deferred large windows = 600 - 408 = 192
```

The planned runtime is 68 hours for each window product. With eight setup
hours, total scheduled time is exactly 144 hours.

## Relationship to prior milestones

The monthly base requirement is the Milestone 6 net production requirement.
Milestone 8 tests whether that requested production fits the approved capacity
assumptions. Deferred production is a production backlog; this milestone does
not recalculate the Milestone 6 inventory projection or claim that delayed
production still satisfies customer demand on time.

Milestone 7 material purchase recommendations remain a separate requirements
view. Capacity changes do not automatically cancel or retime purchase orders.

## Interpretation limits

- Monthly buckets do not sequence individual jobs, shifts, or days.
- Setup time is fixed by active product and does not depend on production
  sequence or campaign size.
- Proportional allocation is a neutral teaching rule, not an optimized priority
  policy.
- Run rates, downtime, overtime, and calendars are fictional and deterministic.
- Labor skills, absenteeism, maintenance events, quality loss, rework, and
  material shortages are not simulated.
- Deferred production is carried without cancellation or lateness penalties.
- The result is a finite-capacity monthly plan, not an executable shop-floor
  schedule.

## Acceptance criteria

1. The manual example produces 544 small windows, 408 large windows, and
   deferred quantities of 256 and 192.
2. Every product-month row shows base requirement, beginning deferred units,
   total requested units, run rate, planned units, and ending deferred units.
3. Every work-center month shows regular/effective capacity, setup and run
   hours, required utilization, capacity gap, and overload status.
4. Planned setup plus runtime never exceeds effective capacity.
5. Ending deferred production becomes the following month's beginning deferred
   production for the same product.
6. Default plans contain 36 product-month rows and 24 work-center-month rows.
7. Calendar, downtime, overtime, setup, and run-rate assumptions are adjustable.
8. CLI and dashboard views use the same capacity-planning module.
9. Tests require no API key and never contact FRED.
