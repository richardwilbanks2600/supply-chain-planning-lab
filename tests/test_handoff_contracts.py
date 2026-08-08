"""Contracts that keep learner-facing documentation aligned with the code."""

import ast
import csv
from io import StringIO
from pathlib import Path

from supply_chain_planning_lab.capacity import (
    ProductCapacityRecord,
    WorkCenterCapacityRecord,
)
from supply_chain_planning_lab.cli import build_parser
from supply_chain_planning_lab.demand import DemandRecord, load_fred_snapshot
from supply_chain_planning_lab.integrated_planning import (
    build_integrated_plan,
    records_csv,
)
from supply_chain_planning_lab.inventory import InventoryPlanRecord
from supply_chain_planning_lab.procurement import ProcurementPlanRecord
from supply_chain_planning_lab.scenario import default_planning_scenario


EXPECTED_COMMANDS = {
    "capacity-plan",
    "demand",
    "fetch",
    "forecast",
    "fred-forecast",
    "inspect",
    "inventory-plan",
    "procurement-plan",
    "project-info",
}


def test_top_level_help_names_every_supported_workflow() -> None:
    """Protect the handoff README from an incomplete top-level help menu."""

    help_text = build_parser().format_help()

    assert "FRED-driven demand-to-capacity" in help_text
    for command in EXPECTED_COMMANDS:
        assert command in help_text


def test_download_headers_match_their_typed_record_contracts() -> None:
    """Fail when a principal download drifts from its documented record type."""

    plan = build_integrated_plan(
        load_fred_snapshot(),
        default_planning_scenario(forecast_origin="2024-12"),
    )
    contracts = (
        (plan.demand_records, DemandRecord),
        (plan.inventory_records, InventoryPlanRecord),
        (plan.procurement_records, ProcurementPlanRecord),
        (plan.capacity_plan.products, ProductCapacityRecord),
        (plan.capacity_plan.work_centers, WorkCenterCapacityRecord),
    )

    for records, contract in contracts:
        header = next(csv.reader(StringIO(records_csv(records))))
        assert header == list(contract.__annotations__)


def test_source_functions_have_docstrings_and_type_hints() -> None:
    """Keep every function inspectable for the next developer or learner."""

    source_root = Path(__file__).parents[1] / "src" / "supply_chain_planning_lab"
    failures: list[str] = []
    for path in sorted(source_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            label = f"{path.name}:{node.lineno}:{node.name}"
            if ast.get_docstring(node) is None:
                failures.append(f"{label} missing docstring")
            if node.returns is None:
                failures.append(f"{label} missing return type")
            arguments = (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            )
            for argument in arguments:
                if argument.arg in {"self", "cls"}:
                    continue
                if argument.annotation is None:
                    failures.append(f"{label} missing type for {argument.arg}")
            if node.args.vararg and node.args.vararg.annotation is None:
                failures.append(f"{label} missing vararg type")
            if node.args.kwarg and node.args.kwarg.annotation is None:
                failures.append(f"{label} missing kwarg type")

    assert not failures, "\n".join(failures)
