# perf-eval

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
