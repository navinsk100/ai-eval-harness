# AI EVAL HARNESS 

An evaluation harness for an AI-driven performance analysis agent. Grades the
agent against curated scenarios of realistic load testing + JVM + observability
data, so that prompt changes, model upgrades, and architectural shifts can be
measured rather than guessed.

## What this repo is

- **Scenarios** (`scenarios/`): YAML files describing one performance incident
  each. The agent never sees the `ground_truth` block — only the grader does.
- **Fixtures** (`fixtures/<scenario_id>/`): the raw evidence files the agent
  reads (Gatling logs, JVM metrics, thread dumps, slow query logs).
- **Agent** (`perf_eval/agent.py`): the thing under test. V0 is a single
  Claude call with all evidence inlined. V1 (later) will use tool use.
- **Graders** (`perf_eval/graders/`): score the agent's diagnosis.
  Deterministic checks for format/citations/forbidden claims; LLM-as-judge
  for root cause correctness and reasoning quality.
- **Runner** (`perf_eval/runner.py`): orchestrates scenario → agent → grade
  and writes run artifacts to `runs/<timestamp>/`.

## Quickstart

```bash
# Install
uv pip install -e .         # or: pip install -e .

# Set up your API key
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY

# Run all scenarios
python scripts/run_evals.py

# Run a specific scenario
python scripts/run_evals.py --scenarios 001_jdbc_pool_exhaustion

# Compare a new prompt against the baseline
python scripts/run_evals.py --prompt v2 --tag "added-self-critique"
```

## Mental model

- **Scenarios** are the exam questions. Defined once, version controlled.
- **Fixtures** are the data the agent reads to answer each question.
- **Runs** are the agent's score over time as you iterate on prompts, models,
  retrieval, and orchestration.

Each run produces:
- `runs/<timestamp>/results.jsonl` — raw per-scenario results
- `runs/<timestamp>/summary.md` — human-readable report
- `runs/<timestamp>/diffs.md` — delta against the previous run

## Adding a scenario

1. Create `scenarios/NNN_short_name.yaml` (see `scenarios/_schema.yaml`).
2. Create `fixtures/NNN/` with the evidence files referenced in the YAML.
3. Run `python scripts/run_evals.py --scenarios NNN_short_name` to validate.

## Build order

Start dumb, measure, then add complexity:

1. Week 1: 10 scenarios + V0 agent (single-shot prompt). Establish baseline.
2. Week 2-3: Iterate the prompt, add a few-shot examples block.
3. Week 4+: Add RAG over a curated performance engineering knowledge base.
4. Month 2+: Move to tool-use loop (V1 agent), expand scenarios to 50+.

## Design decisions

### Why eval harnesses, not just better prompts
Prompt quality drifts as models update and scenarios diversify. Without an
eval harness, teams iterate on vibes. This project treats the agent as the
*thing under test* and tracks its quality via a reproducible, versioned
scoring loop.

### Type-level separation of agent inputs and ground truth
Scenarios contain both the evidence (what the agent sees) and the ground
truth (what the grader compares against). To prevent eval contamination,
the agent receives an `AgentInput` type that structurally excludes the
`ground_truth` field — enforced by Pydantic, not by developer discipline.

### Deterministic graders + LLM-as-judge, weighted together
Format compliance, citation presence, and forbidden-claim detection are
cheap deterministic checks. Root-cause correctness and reasoning quality
need semantic understanding, so Claude grades those. Each criterion carries
a weight reflecting its importance to the product value proposition.

### Confidently-wrong is weighted hardest
A confident wrong diagnosis is worse than a tentative one. The grader
reflects that: forbidden-claim weight is 2.0 (vs 0.5 for format), and the
LLM judge caps confidently-wrong scores at 0.2.

### Fixtures live on disk, not inline
Scenarios reference evidence files by path. The V0 agent inlines them into
one prompt; the planned V1 agent uses MCP-style tool calls to fetch evidence
on demand. Same scenarios, same ground truth — only the agent's data access
pattern changes.
