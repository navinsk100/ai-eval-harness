"""The agent under test (V0).

V0 is deliberately simple: load all evidence into one prompt, single Claude
call, parse JSON response. Goal is to establish a baseline of what frontier
models can do with minimal scaffolding.

V1 will replace the inline evidence blob with MCP-style tool use where the
agent fetches evidence on demand. See README for the build order.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import anthropic

from .schema import AgentDiagnosis, AgentInput, EvalContaminationError, Scenario

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Approximate pricing in USD per million tokens. Update when Anthropic changes.
# These numbers are for the Sonnet tier; adjust if you swap models.
PRICE_INPUT_PER_M = 3.0
PRICE_OUTPUT_PER_M = 15.0


class PerfAnalysisAgent:
    """The thing under test. V0 = single-shot Claude call."""

    def __init__(self, model: str, prompt_version: str = "v1") -> None:
        self.model = model
        self.prompt_version = prompt_version
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.system_prompt = (PROMPTS_DIR / "system.md").read_text()
        self.few_shot = (PROMPTS_DIR / "few_shot_examples.md").read_text()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def diagnose(
        self, agent_input: AgentInput
    ) -> tuple[AgentDiagnosis, str, float, int]:
        """Run a diagnosis on one scenario.

        Returns (diagnosis, raw_llm_response, cost_usd, duration_ms).

        Note the input type: `AgentInput`, not `Scenario`. The agent cannot
        access ground truth by construction — that field doesn't exist on
        AgentInput.
        """
        start = time.monotonic()

        evidence_blob = self._build_evidence_blob(agent_input)
        user_message = self._build_user_message(agent_input, evidence_blob)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt + "\n\n" + self.few_shot,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text
        diagnosis = self._parse_response(raw)

        duration_ms = int((time.monotonic() - start) * 1000)
        cost_usd = self._estimate_cost(response.usage)

        return diagnosis, raw, cost_usd, duration_ms

    # ---------------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------------

    def _build_evidence_blob(self, agent_input: AgentInput) -> str:
        """Read fixture files into a single text blob. V1 will replace this
        with on-demand tool calls."""
        parts: list[str] = []
        inputs = agent_input.inputs

        # Test results
        tr = inputs.test_results
        parts.append(
            f"### Test Results ({tr.tool})\n"
            f"Target RPS: {tr.target_rps} | Actual RPS: {tr.actual_rps} | "
            f"Duration: {tr.duration_sec}s\n\n"
            f"```\n{_read_truncated(tr.fixture_path, 5000)}\n```"
        )

        # Metrics
        for m in inputs.metrics:
            parts.append(
                f"### Metrics ({m.source}, window={m.time_window_sec}s)\n"
                f"```\n{_read_truncated(m.fixture_path, 5000)}\n```"
            )

        # Logs
        for log in inputs.logs:
            parts.append(
                f"### Logs ({log.line_count} lines)\n"
                f"```\n{_read_truncated(log.fixture_path, 3000)}\n```"
            )

        # Thread dumps
        for td in inputs.thread_dumps:
            captured = f" at t={td.captured_at_sec}s" if td.captured_at_sec else ""
            parts.append(
                f"### Thread Dump{captured} ({td.thread_count} threads)\n"
                f"```\n{_read_truncated(td.fixture_path, 5000)}\n```"
            )

        # Heap dumps
        for hd in inputs.heap_dumps:
            captured = f" at t={hd.captured_at_sec}s" if hd.captured_at_sec else ""
            parts.append(
                f"### Heap {hd.type}{captured}\n"
                f"```\n{_read_truncated(hd.fixture_path, 3000)}\n```"
            )

        # Slow queries
        if inputs.slow_queries:
            parts.append(
                f"### Slow Queries\n"
                f"```\n{_read_truncated(inputs.slow_queries.fixture_path, 3000)}\n```"
            )

        return "\n\n".join(parts)

    def _build_user_message(self, agent_input: AgentInput, evidence_blob: str) -> str:
        ctx = agent_input.inputs.context
        return (
            "Analyze the following performance test results and produce a "
            "diagnosis as a JSON object matching the AgentDiagnosis schema.\n\n"
            "## System Context\n"
            f"- Architecture: {ctx.architecture_notes}\n"
            f"- Deployment: {ctx.deployment}\n"
            f"- JVM args: {ctx.jvm_args}\n\n"
            "## Evidence\n"
            f"{evidence_blob}\n\n"
            "## Required Output\n"
            "Respond with ONLY a JSON object conforming to AgentDiagnosis. "
            "Every claim in `primary_root_cause` and `contributing_factors` "
            "must cite specific evidence from the data above. "
            "If evidence is insufficient for a confident diagnosis, say so "
            "explicitly in `notes` and lower your `overall_confidence`."
        )

    def _parse_response(self, raw: str) -> AgentDiagnosis:
        """Extract JSON from the response. Claude sometimes wraps it in
        markdown fences; strip those out."""
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON object found in response: {raw[:300]}")
        return AgentDiagnosis.model_validate_json(text[start:end])

    def _estimate_cost(self, usage: Any) -> float:
        input_cost = usage.input_tokens * PRICE_INPUT_PER_M / 1_000_000
        output_cost = usage.output_tokens * PRICE_OUTPUT_PER_M / 1_000_000
        return input_cost + output_cost


# =========================================================================
# Helpers
# =========================================================================

def _read_truncated(path: Path, max_chars: int) -> str:
    """Read a file and truncate to max_chars, with a marker if truncated."""
    if not path.exists():
        return f"[fixture missing: {path}]"
    content = path.read_text(errors="replace")
    if len(content) > max_chars:
        return content[:max_chars] + f"\n... [truncated, full size: {len(content)} chars]"
    return content


# =========================================================================
# Eval contamination check (belt-and-suspenders on top of type separation)
# =========================================================================

def assert_no_ground_truth_leak(scenario: Scenario, prompt_text: str) -> None:
    """Scan a prompt for any ground-truth strings before sending to LLM.

    Catches contamination that could happen via shared config, accidental
    pasting, or programmatic mistakes. Raises EvalContaminationError if
    a distinctive ground-truth phrase appears in the prompt.
    """
    gt = scenario.ground_truth
    forbidden_strings: list[str] = [
        gt.primary_root_cause.summary,
        gt.primary_root_cause.component,
        *[e.signal for e in gt.primary_root_cause.evidence_required],
        *[cf.summary for cf in gt.contributing_factors],
        *gt.required_recommendations,
        *[rh.description for rh in gt.red_herrings],
    ]
    prompt_lower = prompt_text.lower()
    for forbidden in forbidden_strings:
        tokens = forbidden.split()
        if len(tokens) >= 6:
            distinctive = " ".join(tokens[:6]).lower()
            if distinctive in prompt_lower:
                raise EvalContaminationError(
                    f"Scenario {scenario.id}: ground-truth phrase "
                    f"'{distinctive}' found in agent prompt. "
                    f"This invalidates the eval."
                )
