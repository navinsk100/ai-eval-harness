"""LLM-as-judge graders. Use Claude to score correctness and reasoning quality.

These are more expensive but catch semantic correctness that deterministic
graders can't.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

from ..schema import AgentDiagnosis, CriterionScore, Scenario

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "judge_prompts"

# Use a strong model for judging — don't cheap out here.
JUDGE_MODEL = os.environ.get("PERF_EVAL_JUDGE_MODEL", "claude-sonnet-4-5")


class LLMJudge:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.root_cause_prompt = (PROMPTS_DIR / "root_cause.md").read_text()
        self.reasoning_prompt = (PROMPTS_DIR / "reasoning_quality.md").read_text()

    def grade_root_cause_correctness(
        self, scenario: Scenario, diag: AgentDiagnosis
    ) -> CriterionScore:
        prompt = self.root_cause_prompt.format(
            ground_truth=scenario.ground_truth.primary_root_cause.model_dump_json(indent=2),
            agent_diagnosis=diag.primary_root_cause.model_dump_json(indent=2),
        )
        response = self.client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = self._parse_judge_response(response.content[0].text)
        return CriterionScore(
            name="root_cause_correctness",
            score=result["score"],
            weight=3.0,                 # the most important criterion
            explanation=result.get("explanation", ""),
            grader="llm_judge",
        )

    def grade_reasoning_quality(
        self, scenario: Scenario, diag: AgentDiagnosis
    ) -> CriterionScore:
        red_herrings_text = "\n".join(
            f"- {rh.description}: {rh.why_not_cause}"
            for rh in scenario.ground_truth.red_herrings
        ) or "(none defined)"

        prompt = self.reasoning_prompt.format(
            scenario_title=scenario.title,
            ground_truth=scenario.ground_truth.model_dump_json(indent=2),
            red_herrings=red_herrings_text,
            agent_diagnosis=diag.model_dump_json(indent=2),
        )
        response = self.client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = self._parse_judge_response(response.content[0].text)
        return CriterionScore(
            name="reasoning_quality",
            score=result["score"],
            weight=1.5,
            explanation=result.get("explanation", ""),
            grader="llm_judge",
        )

    def _parse_judge_response(self, raw: str) -> dict:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"score": 0.0, "explanation": f"judge returned non-JSON: {raw[:200]}"}
        return json.loads(text[start:end])


def run_llm_graders(scenario: Scenario, diag: AgentDiagnosis) -> list[CriterionScore]:
    judge = LLMJudge()
    return [
        judge.grade_root_cause_correctness(scenario, diag),
        judge.grade_reasoning_quality(scenario, diag),
    ]
