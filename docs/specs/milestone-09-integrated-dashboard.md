# Milestone 09: Learner-first integrated planning dashboard

## Status

Approved on 2026-08-07.

## Audience

The primary user is a learner entering the dashboard with no assumed knowledge
of forecasting, inventory, procurement, supplier performance, or capacity
planning. An instructor or business reviewer is a secondary audience.

Every design choice should therefore prefer plain language, visible
assumptions, calculation lineage, and reversible exploration over compact
expert shorthand.

## Goal

Turn the separate planning modules into one consistent learning workflow that
shows how a change to a business assumption moves through:

```text
FRED market signal
    -> fictional internal demand
    -> demand forecast
    -> inventory and production requirement
    -> material and supplier plan
    -> capacity-feasible production
```

## Approved interaction model

### One shared working scenario

The dashboard uses one session-only working scenario. Shared controls cover:

- forecast origin;
- company market share, customer allocation, and units per home;
- starting finished-goods inventory and its percentage safety-stock policy;
- starting material inventory, material safety-stock method, service level,
  and scheduled-receipt treatment; and
- working calendar, run rates, setup, downtime, and overtime.

Changing one control recalculates all downstream views. Scenario values are not
saved to a database and can be restored to approved defaults with one reset
action.

### Baseline comparison

The approved baseline uses default business and planning assumptions at the
same selected forecast origin as the working scenario. Using the same origin
keeps periods comparable and isolates the effect of learner-adjusted business
assumptions.

The overview compares:

- 12-month forecast demand;
- net production requirements;
- material purchase actions;
- past-due order-release actions;
- work-center overload months; and
- ending deferred production.

### Requirements versus feasible output

The dashboard keeps these concepts separate:

- `unconstrained production requirement`: what the demand, inventory, and
  safety-stock rules request;
- `capacity-feasible production`: what the monthly work-center model can build;
  and
- `deferred production`: the unbuilt difference carried forward.

Milestone 9 does not silently rewrite the inventory or procurement plans after
capacity allocation. The learner sees both views side by side and is told why
they differ.

## Approved navigation

The workflow is organized in learning order:

1. **Overview** — what changed and what needs attention?
2. **Demand signal** — where does fictional company demand come from?
3. **Forecast** — what is known and what must be forecast?
4. **Inventory** — how much finished product should be made?
5. **Materials and suppliers** — what should be purchased and when?
6. **Capacity** — what can the work centers actually build?
7. **Source data** — what external data entered the model?

Detailed tables and formulas remain available below the plain-language summary
rather than being removed.

## Overview and exceptions

The Overview provides:

- a short workflow explanation;
- baseline-versus-working scenario metrics;
- past-due purchasing recommendations;
- supplier receipts reduced by risk adjustment;
- overloaded work-center months;
- final deferred production by product;
- source-to-result lineage; and
- CSV downloads for each planning layer.

Exception counts are not recommendations to optimize automatically. They are
prompts for the learner to inspect assumptions and trade-offs.

## Language and accessibility rules

- Lead with the business question before the formula.
- Expand an acronym the first time it appears.
- Put units in labels and table headings.
- State whether positive or negative values are favorable or unfavorable.
- Do not use color as the only indication of an exception.
- Keep source values, assumptions, requirements, feasible output, and hindsight
  actuals visibly distinct.
- Use help text for immediate definitions and reserve the complete terminology
  system for Milestone 10.

## Downloads

Downloads are generated in memory and contain the current working scenario's:

- fictional demand records;
- finished-goods inventory plan;
- material procurement plan;
- capacity work-center plan; and
- capacity product allocation plan.

No download contains a FRED API key or causes an external request.

## Interpretation limits

- The integrated plan remains a deterministic educational scenario.
- The baseline is a comparison reference, not an industry benchmark.
- Session-only controls are lost when the dashboard session ends.
- Unconstrained procurement and inventory requirements are not automatically
  reconciled to constrained production output.
- No optimization, database, deployment, or multi-user collaboration is added.
- Complete term definitions and guided learning content remain Milestone 10.

## Acceptance criteria

1. One shared scenario controls every downstream planning view.
2. Reset restores all approved defaults without external calls.
3. Baseline and working scenarios use the same forecast origin.
4. Overview comparison and exception tables are calculated from shared modules.
5. Unconstrained requirements and capacity-feasible output are visibly distinct.
6. Every major planning layer has an in-memory CSV download.
7. Navigation follows the approved learning order.
8. Labels and explanations assume no prior planning knowledge.
9. Existing CLI behavior and calculation modules remain available.
10. Tests require no API key and never contact FRED.
