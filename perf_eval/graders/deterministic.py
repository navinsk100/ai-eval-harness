"""Deterministic graders. No LLM calls, no cost, fast.

These check things that can be verified mechanically: format compliance,
required recommendations match, no forbidden claims, required evidence
citations present.
"""
from __future__ import annotations

from ..schema import AgentDiagnosis, CriterionScore, Scenario


def grade_format_compliance(diag: AgentDiagnosis) -> CriterionScore:
    """Did the agent produce a structurally complete diagnosis?"""
    issues: list[str] = []
    if not diag.primary_root_cause.evidence:
        issues.append("primary root cause has no evidence citations")
    if not diag.recommendations:
        issues.append("no recommendations provided")
    if diag.overall_confidence > 0.9 and len(diag.primary_root_cause.evidence) < 2:
        issues.append("high confidence with thin evidence (<2 citations)")

    score = 1.0 if not issues else max(0.0, 1.0 - 0.3 * len(issues))
    return CriterionScore(
        name="format_compliance",
        score=score,
        weight=0.5,
        explanation="; ".join(issues) if issues else "ok",
        grader="deterministic",
    )


def grade_required_recommendations(
    scenario: Scenario, diag: AgentDiagnosis
) -> CriterionScore:
    """At least one required recommendation pattern must appear in the
    agent's recommendations."""
    rec_text = " ".join(r.action.lower() for r in diag.recommendations)
    matched = []
    for req in scenario.ground_truth.required_recommendations:
        req_tokens = [t for t in req.lower().split() if len(t) > 4]
        if not req_tokens:
            continue
        # Match if at least 2 distinctive tokens from the requirement appear
        hits = sum(1 for t in req_tokens if t in rec_text)
        if hits >= min(2, len(req_tokens)):
            matched.append(req)

    total = len(scenario.ground_truth.required_recommendations)
    score = len(matched) / total if total > 0 else 1.0
    return CriterionScore(
        name="required_recommendations",
        score=score,
        weight=1.0,
        explanation=f"matched {len(matched)}/{total}",
        grader="deterministic",
    )


def grade_no_forbidden_claims(
    scenario: Scenario, diag: AgentDiagnosis
) -> CriterionScore:
    """Primary root cause must not match any forbidden claim pattern.

    Weighted heavily (2.0) — confidently wrong is the worst failure mode.
    """
    primary = diag.primary_root_cause.summary.lower()
    forbidden_hits = []
    for f in scenario.ground_truth.forbidden_claims:
        tokens = [t for t in f.lower().split() if len(t) > 4]
        if not tokens:
            continue
        if all(t in primary for t in tokens):
            forbidden_hits.append(f)

    if forbidden_hits:
        # Confident-wrong is much worse than tentative-wrong
        confidence_penalty = diag.primary_root_cause.confidence
        score = max(0.0, 1.0 - confidence_penalty)
        return CriterionScore(
            name="no_forbidden_claims",
            score=score,
            weight=2.0,
            explanation=(
                f"hit forbidden claim: '{forbidden_hits[0]}' "
                f"at confidence {confidence_penalty:.2f}"
            ),
            grader="deterministic",
        )

    return CriterionScore(
        name="no_forbidden_claims",
        score=1.0,
        weight=2.0,
        explanation="no forbidden claims matched",
        grader="deterministic",
    )


def grade_evidence_citations(
    scenario: Scenario, diag: AgentDiagnosis
) -> CriterionScore:
    """Required evidence (criticality=required) must be cited in the
    primary root cause's evidence list."""
    required = [
        e for e in scenario.ground_truth.primary_root_cause.evidence_required
        if e.criticality.value == "required"
    ]
    cited_signals = [c.signal.lower() for c in diag.primary_root_cause.evidence]

    matched = 0
    for req in required:
        req_tokens = {t for t in req.signal.lower().split() if len(t) > 4}
        if not req_tokens:
            continue
        for cited in cited_signals:
            cited_tokens = {t for t in cited.split() if len(t) > 4}
            if len(req_tokens & cited_tokens) >= 2:
                matched += 1
                break

    score = matched / len(required) if required else 1.0
    return CriterionScore(
        name="evidence_citations",
        score=score,
        weight=1.5,
        explanation=f"cited {matched}/{len(required)} required signals",
        grader="deterministic",
    )


def grade_expected_signals(
    scenario: Scenario, diag: AgentDiagnosis
) -> CriterionScore:
    """Soft check: do expected signal terms appear anywhere in the diagnosis?"""
    expected = scenario.ground_truth.expected_signals_in_diagnosis
    if not expected:
        return CriterionScore(
            name="expected_signals",
            score=1.0,
            weight=0.3,
            explanation="no expected signals defined",
            grader="deterministic",
        )

    # Build a haystack of all agent text
    haystack_parts = [
        diag.primary_root_cause.summary,
        " ".join(c.signal for c in diag.primary_root_cause.evidence),
        " ".join(r.action + " " + r.rationale for r in diag.recommendations),
        diag.notes,
    ]
    haystack = " ".join(haystack_parts).lower()

    matched = sum(1 for sig in expected if sig.lower() in haystack)
    score = matched / len(expected)
    return CriterionScore(
        name="expected_signals",
        score=score,
        weight=0.3,
        explanation=f"matched {matched}/{len(expected)} expected signal terms",
        grader="deterministic",
    )


def grade_no_unexpected_signals(
    scenario: Scenario, diag: AgentDiagnosis
) -> CriterionScore:
    """Soft warning: do off-track signal terms appear in the primary diagnosis?"""
    unexpected = scenario.ground_truth.unexpected_signals_warning
    if not unexpected:
        return CriterionScore(
            name="no_unexpected_signals",
            score=1.0,
            weight=0.3,
            explanation="no unexpected signals defined",
            grader="deterministic",
        )
    primary_text = (
        diag.primary_root_cause.summary + " "
        + " ".join(c.signal for c in diag.primary_root_cause.evidence)
    ).lower()
    hits = [sig for sig in unexpected if sig.lower() in primary_text]
    score = 1.0 - (len(hits) / max(1, len(unexpected)))
    return CriterionScore(
        name="no_unexpected_signals",
        score=max(0.0, score),
        weight=0.3,
        explanation=f"unexpected terms in primary diagnosis: {hits}" if hits else "ok",
        grader="deterministic",
    )


def run_deterministic_graders(
    scenario: Scenario, diag: AgentDiagnosis
) -> list[CriterionScore]:
    return [
        grade_format_compliance(diag),
        grade_required_recommendations(scenario, diag),
        grade_no_forbidden_claims(scenario, diag),
        grade_evidence_citations(scenario, diag),
        grade_expected_signals(scenario, diag),
        grade_no_unexpected_signals(scenario, diag),
    ]
