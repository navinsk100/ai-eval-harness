"""Load scenarios from YAML files into validated Scenario objects."""
from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def load_scenario(scenario_id: str) -> Scenario:
    """Load a single scenario by ID. Filename must be `<id>.yaml`."""
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {path}")
    with path.open() as f:
        data = yaml.safe_load(f)
    return Scenario.model_validate(data)


def load_all_scenarios(filter_ids: list[str] | None = None) -> list[Scenario]:
    """Load all scenarios from the scenarios/ directory.

    If `filter_ids` is provided, only those scenarios are loaded.
    Files starting with `_` (like `_schema.yaml`) are skipped.
    """
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        if filter_ids and path.stem not in filter_ids:
            continue
        with path.open() as f:
            data = yaml.safe_load(f)
        scenarios.append(Scenario.model_validate(data))
    return scenarios
