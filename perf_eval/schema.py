"""Pydantic models for scenarios, agent inputs/outputs, and run results.

Key design choice: `Scenario` (which includes `ground_truth`) is what the
harness loads from YAML and what graders consume. `AgentInput` is the
stripped-down view the agent under test receives — it explicitly does NOT
contain ground truth. This prevents accidental eval contamination at the
type level.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


# =========================================================================
# Enums
# =========================================================================

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Criticality(str, Enum):
    REQUIRED = "required"
    STRONG = "strong"
    SUPPORTING = "supporting"


# =========================================================================
# Scenario inputs (what the agent sees)
# =========================================================================

class TestResults(BaseModel):
    tool: str                       # "gatling" | "k6" | "jmeter" | "blazemeter"
    fixture_path: Path
    duration_sec: int
    target_rps: int
    actual_rps: int


class MetricSource(BaseModel):
    source: str                     # "prometheus" | "otel" | "datadog" | "csv"
    fixture_path: Path
    time_window_sec: int


class LogSource(BaseModel):
    fixture_path: Path
    line_count: int = 0


class TimedArtifact(BaseModel):
    """Base for time-bounded diagnostic artifacts."""
    fixture_path: Path
    captured_at_sec: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadDump(TimedArtifact):
    thread_count: Optional[int] = None
    notable_states: list[str] = Field(default_factory=list)


class HeapDump(TimedArtifact):
    type: str = "histogram"         # "histogram" | "full"
    total_size_mb: Optional[float] = None


class FlameGraph(TimedArtifact):
    profiler: str = "async-profiler"
    duration_sec: Optional[int] = None


class SlowQueries(BaseModel):
    fixture_path: Path


class SystemContext(BaseModel):
    architecture_notes: str
    deployment: str
    jvm_args: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)


class Inputs(BaseModel):
    """The agent-visible block. Everything below this can be shown to the LLM."""
    test_results: TestResults
    metrics: list[MetricSource] = Field(default_factory=list)
    logs: list[LogSource] = Field(default_factory=list)
    thread_dumps: list[ThreadDump] = Field(default_factory=list)
    heap_dumps: list[HeapDump] = Field(default_factory=list)
    flame_graphs: list[FlameGraph] = Field(default_factory=list)
    slow_queries: Optional[SlowQueries] = None
    context: SystemContext


# =========================================================================
# Ground truth (grader-only block)
# =========================================================================

class EvidenceSpec(BaseModel):
    source: str                     # "metrics" | "logs" | "thread_dump" | ...
    signal: str
    criticality: Criticality


class RootCauseSpec(BaseModel):
    summary: str
    component: str
    confidence_floor: float = 0.6
    evidence_required: list[EvidenceSpec]


class ContributingFactor(BaseModel):
    summary: str
    criticality: Criticality


class RedHerring(BaseModel):
    description: str
    why_not_cause: str


class GroundTruth(BaseModel):
    primary_root_cause: RootCauseSpec
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    red_herrings: list[RedHerring] = Field(default_factory=list)
    required_recommendations: list[str]
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_signals_in_diagnosis: list[str] = Field(default_factory=list)
    unexpected_signals_warning: list[str] = Field(default_factory=list)


# =========================================================================
# Full scenario (what the harness loads)
# =========================================================================

class GradingHints(BaseModel):
    weight: float = 1.0
    notes: str = ""


class Scenario(BaseModel):
    id: str
    title: str
    schema_version: int = 1
    difficulty: Difficulty
    category: list[str]
    tags: list[str] = Field(default_factory=list)
    severity: str = "medium"        # "low" | "medium" | "high"
    inputs: Inputs
    ground_truth: GroundTruth
    grading: GradingHints = Field(default_factory=GradingHints)

    def to_agent_input(self) -> "AgentInput":
        """Strip ground truth before handing to the agent.

        This is THE function that enforces the agent/grader information
        separation. The agent only ever receives an AgentInput.
        """
        return AgentInput(
            id=self.id,
            title=self.title,
            difficulty=self.difficulty,
            inputs=self.inputs,
        )


class AgentInput(BaseModel):
    """The stripped-down view of a scenario that the agent under test sees.

    Critically: NO `ground_truth` field. The agent cannot access the answer
    key even if a developer makes a mistake in the agent code — the type
    doesn't have that attribute.
    """
    id: str
    title: str                      # safe to share — just a label
    difficulty: Difficulty          # safe to share — calibration hint
    inputs: Inputs


# =========================================================================
# Agent output schema
# =========================================================================

class Citation(BaseModel):
    """A pointer to specific evidence supporting a claim."""
    source: str
    signal: str
    fixture_ref: str = ""


class Hypothesis(BaseModel):
    """A candidate root cause or contributing factor."""
    component: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Citation]
    ruled_out: bool = False
    ruled_out_reason: Optional[str] = None


class Recommendation(BaseModel):
    action: str
    rationale: str
    priority: str                   # "P0" | "P1" | "P2"


class AgentDiagnosis(BaseModel):
    """The structured output the agent produces for one scenario."""
    primary_root_cause: Hypothesis
    contributing_factors: list[Hypothesis] = Field(default_factory=list)
    considered_and_ruled_out: list[Hypothesis] = Field(default_factory=list)
    recommendations: list[Recommendation]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


# =========================================================================
# Grading + run results
# =========================================================================

class CriterionScore(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float
    explanation: str
    grader: str                     # "deterministic" | "llm_judge"


class ScenarioResult(BaseModel):
    scenario_id: str
    agent_output: AgentDiagnosis
    criteria: list[CriterionScore]
    weighted_score: float
    passed: bool
    duration_ms: int
    cost_usd: float
    raw_llm_response: str = ""


class RunSummary(BaseModel):
    run_id: str
    started_at: str
    git_sha: str
    model: str
    prompt_version: str
    tag: str = ""
    scenario_results: list[ScenarioResult]
    aggregate_score: float
    pass_rate: float
    total_cost_usd: float
    total_duration_ms: int


class EvalContaminationError(Exception):
    """Raised when ground-truth content leaks into the agent prompt."""
