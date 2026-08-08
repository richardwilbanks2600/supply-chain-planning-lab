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

## Practicum hardening and local interface

**Status:** Implemented

- Validate incoming FRED fields with Pydantic before transformation.
- Test successful and failed external-service behavior with fixtures and mocks.
- Preserve raw outside evidence before validation.
- Add optional console and file logging without exposing secrets.
- Give the CLI and local Streamlit dashboard one shared workflow.

This practicum milestone improves trust and usability without adding production
planning logic or changing the meaning of the external indicator.

## Milestone 2: Validate and describe the data

**Status:** Implemented

**Specification:** `docs/specs/milestone-02-data-inspection.md`

**Learning focus:** Data quality, validation, and descriptive analysis

Potential outcomes:

- Define a validated observation model with explicit types and units.
- Detect missing, duplicate, malformed, or unexpectedly ordered records.
- Add commands for listing and filtering processed observations.
- Calculate transparent descriptive measures such as minimum, maximum, and recent average.
- Document what seasonally adjusted annual rate means and what the series cannot tell us.

Decision gate: agree on which descriptive measures are useful before implementing them.

The implemented measures are minimum, maximum, latest value, latest
valid-observation change, and the average of up to the trailing 12 valid
observations. Their definitions and limitations are documented in the
milestone specification.

## Milestone 3: Translate a market signal into fictional demand

**Status:** Implemented

**Specification:** `docs/specs/milestone-03-fictional-demand.md`

**Learning focus:** External signals versus internal demand

Implemented outcomes:

- Package a validated 2000-2025 FRED source snapshot.
- Create a small fictional product and customer catalog.
- Translate the market pace into demand with inspectable assumptions.
- Keep FRED source values and derived internal units clearly labeled.
- Present source lineage and adjustable assumptions in the dashboard.

Decision gate: define the fictional products, customers, time horizon, and meaning of demand.

The revised scenario packages FRED `PERMIT` observations from January 2000
through December 2025 and converts their market pace into fictional internal
demand. The model applies a visible three-month lag, company market share,
product units per home, and customer allocations. The dashboard exposes these
business assumptions as sliders. Cancellations are currently zero, and every
derived record retains its FRED source lineage.

## Milestone 4: Forecasting and forecast performance

**Status:** Implemented

**Specification:** `docs/specs/milestone-04-baseline-forecasting.md`

**Learning focus:** Baseline forecasts, forecast error, and bias

Potential outcomes:

- Establish a simple, explainable baseline forecasting method.
- Compare forecast values with synthetic actual demand.
- Calculate forecast error and bias using manually verified examples.
- Explain the limitations of the selected forecasting method.
- Visualize forecast versus actual demand.

Decision gate: compare candidate baseline methods and select one based on the learning objective.

The approved comparison includes previous-month, same-month-last-year, and
trailing-three-month baselines. Same month last year is the primary baseline.
Forecasts are evaluated at product-month grain over 2020-2025 using MAE and
signed mean error (bias).

## Milestone 5: FRED-informed forecasting

**Status:** Implemented

**Specification:** `docs/specs/milestone-05-fred-informed-forecasting.md`

**Learning focus:** Known external drivers versus genuinely unknown future values

Potential outcomes:

- Distinguish demand horizons covered by already-observed lagged permits from
  horizons that require a forecast of future FRED values.
- Establish a simple baseline forecast for the FRED `PERMIT` series.
- Translate forecasted permit pace through the approved demand model.
- Compare FRED-informed demand forecasts with the internal-history baselines.
- Explain why a model evaluated on data generated by the same structural rule
  is a teaching demonstration rather than independent empirical validation.
- Reserve more complex forecast methods for an explicit, later approval.

Decision gate: approve the FRED forecast horizon, information available at
each forecast origin, baseline method, and treatment of revised observations.

The approved model evaluates 1-12 month product-demand horizons from monthly
forecast origins spanning December 2019 through December 2024. Because FRED
permits lead internal demand by three months, horizons 1-3 use known lagged
permit observations and horizons 4-12 use a previous-month-naive permit
forecast. MAE and signed bias are reported by driver status and horizon. The
evaluation deliberately uses the fixed current FRED snapshot; it does not
simulate publication delays or reconstruct historical vintages.

## Milestone 6: Inventory and net production requirements

**Learning focus:** Turning demand into a production requirement

Potential outcomes:

- Add finished-goods inventory and safety-stock assumptions.
- Calculate gross and net production requirements.
- Show every component of the calculation to the learner.
- Identify potential shortages and excess inventory.
- Add business-scenario tests that match manual calculations.

Decision gate: define the inventory-position and safety-stock rules before implementation.

## Milestone 7: Bills of materials and procurement

**Learning focus:** Material requirements and supplier constraints

Potential outcomes:

- Define simplified bills of materials for the fictional products.
- Translate production requirements into material requirements.
- Account for raw-material inventory and open purchase orders.
- Introduce supplier lead time, on-time delivery, and reliability data.
- Identify projected material shortages and procurement risks.

Decision gate: approve the BOM structure, units of measure, and treatment of open orders.

## Milestone 8: Capacity and production planning

**Learning focus:** Feasibility, capacity loading, and scheduling trade-offs

Potential outcomes:

- Define production lines, run rates, working calendars, and available hours.
- Translate required units into required production hours.
- Compare demand with available capacity by period.
- Build a simple, explainable production plan.
- Explore scenarios such as overtime, demand changes, downtime, or supplier delays.

Decision gate: agree on the capacity model and scheduling assumptions before attempting optimization.

## Milestone 9: Teaching dashboard integration

**Learning focus:** Communicating decisions and trade-offs

Potential outcomes:

- Build an interactive dashboard that follows the planning workflow.
- Let learners inspect inputs, calculations, assumptions, and exceptions.
- Compare scenarios involving service, inventory, and production efficiency.
- Automate relevant checks and data collection.
- Integrate the complete planning workflow into a consistent local interface.

Decision gate: define the dashboard audience and the decisions each view should support.

## Milestone 10: Guided explanations, glossary, and handoff

**Learning focus:** Making planning terminology and calculations independently understandable

Potential outcomes:

- Create one maintained terminology registry covering every dashboard term,
  unit, metric, assumption, and formula.
- Add concise tooltips beside controls and metrics for definitions that fit in
  one or two sentences.
- Add **What does this mean?** popovers for formulas, manual examples, source
  lineage, and common interpretation mistakes.
- Add a dedicated searchable **Learning Guide** page containing the complete
  glossary and links back to relevant dashboard sections.
- Add a forecast-method section comparing rolling-average window lengths and
  simple, weighted, and exponential averages, including their formulas and
  smoothing-versus-responsiveness tradeoffs.
- Add a concise **Further study** section that credits the operations-planning
  textbook that informed the project and directs learners to it for deeper
  coverage, using a verified title, authors, edition, and publisher or official
  link.
- Use modal dialogs only for optional guided walkthroughs that benefit from a
  focused, step-by-step explanation.
- Verify that wording is consistent across the dashboard, CLI, specifications,
  and learner documentation.
- Complete accessibility review, packaging, and public-project handoff.

Decision gate: approve the learner audience, reading level, definition list,
textbook citation, and rule for choosing between a tooltip, popover,
walkthrough, or glossary entry.

## Working principles

- Narrow and complete milestones are preferred over broad, unfinished ones.
- Raw source data, processed project data, and presented results remain separate.
- External indicators are not treated as company forecasts without an explicit model and justification.
- Tests use stable fixtures and business scenarios rather than depending on live APIs.
- Planning assumptions remain visible and documented.
- Implementation begins only after the milestone's learning objective and acceptance criteria are understood.
