# Project Roadmap

This roadmap describes the intended direction of Supply Chain Planning Lab. Future milestones are tentative: each one should be reviewed and converted into a focused specification in `docs/specs/` before implementation begins.

## Project vision

Build an educational command-line tool and dashboard that explains how demand, inventory, materials, supplier constraints, and production capacity are transformed into a production plan for a fictional manufacturer.

The project should remain understandable to the learner building it. Planning rules must be discussed, demonstrated with a small manual example, and approved before they are encoded in software.

## Foundation: API data workflow

**Status:** Implemented

- Retrieve the FRED `PERMIT` construction-market series.
- Preserve the raw JSON response as evidence.
- Normalize observations into an inspectable CSV file.
- Keep the FRED key outside source control.
- Provide a repeatable `uv` command and fixture-based tests.

This establishes the data workflow. Building permits are an external market indicator, not customer orders or a company forecast.

## Milestone 2: Validate and describe the data

**Learning focus:** Data quality, validation, and descriptive analysis

Potential outcomes:

- Define a validated observation model with explicit types and units.
- Detect missing, duplicate, malformed, or unexpectedly ordered records.
- Add commands for listing and filtering processed observations.
- Calculate transparent descriptive measures such as minimum, maximum, and recent average.
- Document what seasonally adjusted annual rate means and what the series cannot tell us.

Decision gate: agree on which descriptive measures are useful before implementing them.

## Milestone 3: Introduce a fictional demand scenario

**Learning focus:** External signals versus internal demand

Potential outcomes:

- Create a small fictional product catalog for a building-components manufacturer.
- Add synthetic historical demand or customer-order data.
- Keep external market indicators separate from internal operational data.
- Explore, without overstating, whether the external series could inform a demand assumption.
- Present the data and assumptions in an inspectable report or dashboard view.

Decision gate: define the fictional products, customers, time horizon, and meaning of demand.

## Milestone 4: Forecasting and forecast performance

**Learning focus:** Baseline forecasts, forecast error, and bias

Potential outcomes:

- Establish a simple, explainable baseline forecasting method.
- Compare forecast values with synthetic actual demand.
- Calculate forecast error and bias using manually verified examples.
- Explain the limitations of the selected forecasting method.
- Visualize forecast versus actual demand.

Decision gate: compare candidate baseline methods and select one based on the learning objective.

## Milestone 5: Inventory and net production requirements

**Learning focus:** Turning demand into a production requirement

Potential outcomes:

- Add finished-goods inventory and safety-stock assumptions.
- Calculate gross and net production requirements.
- Show every component of the calculation to the learner.
- Identify potential shortages and excess inventory.
- Add business-scenario tests that match manual calculations.

Decision gate: define the inventory-position and safety-stock rules before implementation.

## Milestone 6: Bills of materials and procurement

**Learning focus:** Material requirements and supplier constraints

Potential outcomes:

- Define simplified bills of materials for the fictional products.
- Translate production requirements into material requirements.
- Account for raw-material inventory and open purchase orders.
- Introduce supplier lead time, on-time delivery, and reliability data.
- Identify projected material shortages and procurement risks.

Decision gate: approve the BOM structure, units of measure, and treatment of open orders.

## Milestone 7: Capacity and production planning

**Learning focus:** Feasibility, capacity loading, and scheduling trade-offs

Potential outcomes:

- Define production lines, run rates, working calendars, and available hours.
- Translate required units into required production hours.
- Compare demand with available capacity by period.
- Build a simple, explainable production plan.
- Explore scenarios such as overtime, demand changes, downtime, or supplier delays.

Decision gate: agree on the capacity model and scheduling assumptions before attempting optimization.

## Milestone 8: Teaching dashboard and handoff

**Learning focus:** Communicating decisions and trade-offs

Potential outcomes:

- Build an interactive dashboard that follows the planning workflow.
- Let learners inspect inputs, calculations, assumptions, and exceptions.
- Compare scenarios involving service, inventory, and production efficiency.
- Automate relevant checks and data collection.
- Complete documentation, packaging, and public-project handoff.

Decision gate: define the dashboard audience and the decisions each view should support.

## Working principles

- Narrow and complete milestones are preferred over broad, unfinished ones.
- Raw source data, processed project data, and presented results remain separate.
- External indicators are not treated as company forecasts without an explicit model and justification.
- Tests use stable fixtures and business scenarios rather than depending on live APIs.
- Planning assumptions remain visible and documented.
- Implementation begins only after the milestone's learning objective and acceptance criteria are understood.
