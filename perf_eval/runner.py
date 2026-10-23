"""Run the eval harness: load scenarios, invoke agent, grade, store, report."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .agent import PerfAnalysisAgent, assert_no_ground_truth_leak
from .graders.deterministic import run_deterministic_graders
from .graders.llm_judge import run_llm_graders
from .loader import load_all_scenarios
from .reporter import write_run_artifacts
from .schema import RunSummary, Scenario, ScenarioResult
from .store import store_run

load_dotenv()

RUNS_DIR = Path(__file__).parent.parent / "runs"


def run_evals(
    model: str = "claude-sonnet-4-5",
    prompt_version: str = "v1",
    scenario_filter: list[str] | None = None,
    pass_threshold: float = 0.7,
    tag: str = "",
    skip_llm_graders: bool = False,
) -> RunSummary:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = RUNS_DIR / run_id

    git_sha = _git_sha()
    agent = PerfAnalysisAgent(model=model, prompt_version=prompt_version)
    scenarios = load_all_scenarios(filter_ids=scenario_filter)

    if not scenarios:
        raise SystemExit(
            "No scenarios found. Check scenarios/ directory and any --scenarios filter."
        )

    print(f"Running {len(scenarios)} scenarios with model={model}, prompt={prompt_version}")
    print()

    results: list[ScenarioResult] = []
    total_cost = 0.0
    total_duration = 0

    for scenario in scenarios:
        print(f"  → {scenario.id}: {scenario.title}")
        try:
            result = _run_one_scenario(scenario, agent, skip_llm_graders)
        except Exception as e:
            print(f"    ✗ FAILED with exception: {e}")
            continue

        results.append(result)
        total_cost += result.cost_usd
        total_duration += result.duration_ms

        status = "✓" if result.passed else "✗"
        print(f"    {status} score={result.weighted_score:.2f}  cost=${result.cost_usd:.3f}  {result.duration_ms}ms")

    summary = RunSummary(
        run_id=run_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        git_sha=git_sha,
        model=model,
        prompt_version=prompt_version,
        tag=tag,
        scenario_results=results,
        aggregate_score=(
            sum(r.weighted_score for r in results) / len(results) if results else 0.0
        ),
        pass_rate=(
            sum(1 for r in results if r.passed) / len(results) if results else 0.0
        ),
        total_cost_usd=total_cost,
        total_duration_ms=total_duration,
    )

    store_run(summary)
    write_run_artifacts(run_dir, summary)
    return summary


def _run_one_scenario(
    scenario: Scenario,
    agent: PerfAnalysisAgent,
    skip_llm_graders: bool,
) -> ScenarioResult:
    # Type-level separation: agent only sees AgentInput, never ground_truth.
    agent_input = scenario.to_agent_input()

    # Build the prompt and run the contamination check before calling the LLM.
    evidence = agent._build_evidence_blob(agent_input)  # noqa: SLF001
    user_msg = agent._build_user_message(agent_input, evidence)  # noqa: SLF001
    assert_no_ground_truth_leak(scenario, user_msg)

    # Invoke the agent.
    diag, raw, cost, duration_ms = agent.diagnose(agent_input)

    # Grade.
    criteria = run_deterministic_graders(scenario, diag)
    if not skip_llm_graders:
        criteria.extend(run_llm_graders(scenario, diag))

    weighted_sum = sum(c.score * c.weight for c in criteria)
    weight_total = sum(c.weight for c in criteria)
    weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0

    return ScenarioResult(
        scenario_id=scenario.id,
        agent_output=diag,
        criteria=criteria,
        weighted_score=weighted_score,
        passed=weighted_score >= 0.7,
        duration_ms=duration_ms,
        cost_usd=cost,
        raw_llm_response=raw,
    )


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "no-git"
