"""Render run summaries to disk and to stdout."""
from __future__ import annotations

from pathlib import Path

from .schema import RunSummary
from .store import get_previous_run_id, get_scenario_results, get_run_summary


def write_run_artifacts(run_dir: Path, summary: RunSummary) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    # Raw JSONL — one line per scenario result
    with (run_dir / "results.jsonl").open("w") as f:
        for r in summary.scenario_results:
            f.write(r.model_dump_json() + "\n")

    # Human-readable summary
    (run_dir / "summary.md").write_text(_render_summary(summary))

    # Diff against the previous run
    prev_id = get_previous_run_id(exclude_run_id=summary.run_id)
    if prev_id:
        diff = _render_diff(prev_id, summary)
        (run_dir / "diffs.md").write_text(diff)

    # stdout summary
    print()
    print(f"📊 Run {summary.run_id}")
    print(f"   Model: {summary.model}  Prompt: {summary.prompt_version}  Tag: {summary.tag or '-'}")
    print(f"   Aggregate: {summary.aggregate_score:.2f}   Pass rate: {summary.pass_rate:.0%}")
    print(f"   Cost: ${summary.total_cost_usd:.2f}   Duration: {summary.total_duration_ms/1000:.1f}s")
    print(f"   Artifacts: {run_dir}/")


def _render_summary(s: RunSummary) -> str:
    lines = [
        f"# Eval Run {s.run_id}",
        "",
        f"- **Model**: `{s.model}`",
        f"- **Prompt version**: `{s.prompt_version}`",
        f"- **Tag**: `{s.tag or '-'}`",
        f"- **Git SHA**: `{s.git_sha}`",
        f"- **Aggregate score**: **{s.aggregate_score:.2f}**",
        f"- **Pass rate**: {s.pass_rate:.0%}",
        f"- **Cost**: ${s.total_cost_usd:.2f}",
        f"- **Duration**: {s.total_duration_ms/1000:.1f}s",
        "",
        "## Per-scenario results",
        "",
        "| ID | Score | Pass | Cost | Time (ms) |",
        "|---|---|---|---|---|",
    ]
    for r in s.scenario_results:
        lines.append(
            f"| `{r.scenario_id}` | {r.weighted_score:.2f} | "
            f"{'✓' if r.passed else '✗'} | ${r.cost_usd:.3f} | {r.duration_ms} |"
        )

    lines.append("")
    lines.append("## Failures and partial passes")
    lines.append("")
    any_failures = False
    for r in s.scenario_results:
        if r.weighted_score < 0.7:
            any_failures = True
            lines.append(f"### `{r.scenario_id}` (score {r.weighted_score:.2f})")
            for c in r.criteria:
                if c.score < 0.7:
                    lines.append(f"- **{c.name}** ({c.score:.2f}, weight {c.weight}): {c.explanation}")
            lines.append("")
            lines.append(f"**Agent's diagnosis**: {r.agent_output.primary_root_cause.summary}")
            lines.append(f"**Confidence**: {r.agent_output.primary_root_cause.confidence:.2f}")
            lines.append("")
    if not any_failures:
        lines.append("All scenarios passed. 🎉")

    return "\n".join(lines)


def _render_diff(prev_run_id: str, curr: RunSummary) -> str:
    prev_run = get_run_summary(prev_run_id)
    prev_results = {r["scenario_id"]: r for r in get_scenario_results(prev_run_id)}

    if not prev_run:
        return f"# Diff vs {prev_run_id}\n\nNo previous run data found."

    delta = curr.aggregate_score - prev_run["aggregate_score"]
    arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "·")

    lines = [
        f"# Diff: {prev_run_id} → {curr.run_id}",
        "",
        f"Aggregate: {prev_run['aggregate_score']:.2f} → **{curr.aggregate_score:.2f}** "
        f"({delta:+.2f}) {arrow}",
        f"Pass rate: {prev_run['pass_rate']:.0%} → {curr.pass_rate:.0%}",
        f"Cost: ${prev_run['total_cost_usd']:.2f} → ${curr.total_cost_usd:.2f}",
        "",
        "## Per-scenario delta",
        "",
    ]
    for r in curr.scenario_results:
        if r.scenario_id in prev_results:
            prev_score = prev_results[r.scenario_id]["weighted_score"]
            d = r.weighted_score - prev_score
            mark = "↑" if d > 0.05 else ("↓" if d < -0.05 else "·")
            lines.append(
                f"- {mark} `{r.scenario_id}`: {prev_score:.2f} → {r.weighted_score:.2f} ({d:+.2f})"
            )
        else:
            lines.append(f"- ✨ NEW `{r.scenario_id}`: {r.weighted_score:.2f}")

    removed = set(prev_results) - {r.scenario_id for r in curr.scenario_results}
    for sid in sorted(removed):
        lines.append(f"- 🗑 REMOVED `{sid}` (was {prev_results[sid]['weighted_score']:.2f})")

    return "\n".join(lines)
