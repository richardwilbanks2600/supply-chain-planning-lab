# Milestone 10: Guided explanations, glossary, and handoff

## Status

Implemented on 2026-08-07.

## Audience and reading level

The primary learner is assumed to have no prior forecasting, inventory,
procurement, supplier-performance, or capacity-planning knowledge. Definitions
use plain language first, then show the exact project formula or rule. Acronyms
are expanded on first use and every interpretation warning explains why a
reasonable beginner might otherwise reach the wrong conclusion.

## Goal

Make the integrated planning workflow independently understandable without
removing the calculations, record lineage, or limitations that make it
inspectable.

## Maintained terminology registry

`learning.py` is the authoritative learner-content registry. Each entry has:

- a stable key used by the dashboard;
- the displayed term and topic;
- a one-sentence tooltip definition;
- a complete plain-language explanation;
- the relevant dashboard location;
- an optional formula or decision rule;
- an optional manually understandable example;
- an optional common interpretation mistake; and
- search keywords.

The registry covers the principal source-data units, demand assumptions,
forecast methods and performance measures, inventory calculations, supplier
measures, purchasing outputs, and capacity terms displayed by the integrated
workflow. Duplicate keys fail during module import.

## Guidance placement rules

Use the least disruptive explanation that can answer the learner's question:

1. **Tooltip:** one sentence defining a control or metric at the point of use.
2. **What does this mean? popover:** a short group of definitions and formulas
   needed to understand the current workflow step.
3. **Expander:** an optional manual calculation or focused example that belongs
   to one dashboard view.
4. **Learning Guide:** the complete searchable definition, formula, example,
   related location, and interpretation mistake.
5. **Focused walkthrough:** reserved for a multi-step example. Milestone 10
   uses an expander for the rolling-average example because it does not require
   modal interruption or persistent state.

The dashboard must not require a learner to open every tooltip. Each page still
leads with its business question and plain-language purpose.

## Learning Guide

The dedicated tab provides:

- a visible, labeled text search;
- an optional topic filter;
- a result count and a clear no-results message;
- expandable complete entries;
- rolling-average method comparisons;
- further-study credit; and
- an accessibility and interpretation checklist.

Search covers names, definitions, formulas, examples, mistakes, and keywords.
It is case-insensitive and does not call an external service.

## Forecast-method lesson

The guide compares:

- 2-, 3-, and 6-month simple moving averages;
- a weighted moving average; and
- simple exponential smoothing.

Each method shows its formula, responsiveness, smoothing behavior, appropriate
teaching use, and caution. The dashboard explicitly distinguishes explanation
from implementation: the project calculates the 3-month simple average, while
the weighted and exponential methods are learning comparisons only.

The central lesson is that shorter memory reacts faster but retains more
short-lived variation, while longer memory produces a steadier forecast that
lags sustained changes.

## Further study

Per the approved minimal-credit rule, the dashboard displays only:

**Operations and Supply Chain Management, 7th Edition**

It does not display authors, publisher, ISBN, pricing, or purchasing details.

## Accessibility rules

- Controls retain visible labels; no definition depends on an icon alone.
- Exceptions use words and counts rather than color alone.
- Charts remain paired with the underlying tables or records.
- Units appear in labels, fields, captions, or maintained definitions.
- Native Streamlit controls preserve keyboard navigation and focus behavior.
- Search results report their count and show a textual empty state.
- Source data, fictional assumptions, forecasts, requirements, and feasible
  output remain explicitly distinct.

## Scope limits

- No forecasting method is added to the planning calculations.
- No optimization, database, deployment, user tracking, or saved scenario is
  introduced.
- The registry explains the approved model; it does not turn assumptions into
  industry recommendations.
- The Further Study text names one textbook and version only.

## Acceptance criteria

1. One maintained registry supplies tooltip and guide definitions.
2. Every integrated planning step has a contextual explanation control.
3. The dashboard contains a searchable, topic-filterable Learning Guide.
4. Every complete entry can show its rule, example, and mistake when provided.
5. The guide compares rolling-average lengths, weighted averages, and simple
   exponential smoothing without claiming unimplemented methods are active.
6. Further Study displays only the approved textbook name and edition.
7. Accessibility and interpretation rules are visible and tested where
   practical.
8. Existing calculations, CLI commands, and offline behavior remain unchanged.
9. Tests require no API key and do not contact FRED.
