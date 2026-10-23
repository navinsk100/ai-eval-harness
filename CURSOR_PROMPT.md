# Cursor onboarding prompt for perf-eval

Copy the entire block below into Cursor (Composer or chat) after unzipping
the scaffolded project into your workspace. This prompt tells Cursor what
the project is, what state it's in, and what to do next.

---

## Prompt to paste into Cursor

I'm building `perf-eval`, an evaluation harness for an AI-driven performance
analysis agent. The agent ingests load test results (Gatling/k6/JMeter) plus
observability data (JVM metrics, thread dumps, logs, slow queries) and
produces a structured diagnosis with root cause, contributing factors, and
recommendations. The eval harness grades the agent against curated scenarios
with known ground truth so I can measure quality as I iterate on prompts,
models, and orchestration.

### Project state

I've scaffolded the repo with the following structure:

```
perf-eval/
├── pyproject.toml
├── README.md
├── .env.example
├── perf_eval/
│   ├── __init__.py
│   ├── schema.py             # Pydantic models — Scenario, AgentInput, AgentDiagnosis, etc.
│   ├── loader.py             # Load scenarios from YAML
│   ├── agent.py              # The V0 agent under test (single-shot Claude call)
│   ├── runner.py             # Orchestrates scenario → agent → graders → store
│   ├── reporter.py           # Render run summaries and diffs
│   ├── store.py              # SQLite history of runs
│   └── graders/
│       ├── __init__.py
│       ├── deterministic.py  # Fast graders: format, citations, forbidden claims
│       └── llm_judge.py      # Claude-as-judge graders for correctness, reasoning
├── prompts/
│   ├── system.md             # System prompt for the agent
│   ├── few_shot_examples.md  # Worked examples
│   └── judge_prompts/
│       ├── root_cause.md
│       └── reasoning_quality.md
├── scenarios/
│   ├── _schema.yaml          # Schema reference for scenario authoring
│   └── 001_jdbc_pool_exhaustion.yaml  # First worked scenario
├── fixtures/
│   └── 001/                  # Evidence files for scenario 001
│       ├── gatling_simulation.log
│       ├── jvm_metrics.csv
│       ├── app.log
│       ├── thread_dump_t300.txt
│       └── slow_queries.json
├── runs/                     # Run artifacts go here (gitignored)
└── scripts/
    └── run_evals.py          # CLI entrypoint
```

### Key design decisions you must preserve

1. **Type-level eval-contamination prevention**: The `Scenario` class
   contains `ground_truth`. The `AgentInput` class does NOT. The agent
   under test only ever receives an `AgentInput`. This is enforced via
   `Scenario.to_agent_input()` in `schema.py`. NEVER pass a `Scenario`
   to the agent. Never add a `ground_truth` field to `AgentInput`.

2. **Runtime contamination check**: `assert_no_ground_truth_leak` in
   `agent.py` scans the agent's prompt for ground-truth strings before
   sending to the LLM. The runner calls this on every scenario.

3. **Fixtures are file paths, not inline content**: Scenarios reference
   fixtures by `fixture_path`. The agent reads them at diagnose time.
   In V1 this becomes MCP tool calls.

4. **Graders are layered**: Deterministic graders run first (cheap, no LLM
   call). LLM-as-judge graders run second (expensive, more accurate on
   semantic correctness). Both contribute weighted criteria to the final
   scenario score.

5. **Pydantic everywhere**: Every YAML and every LLM response is parsed
   through a Pydantic model. No raw dicts.

### What I need from you

Help me extend and maintain this project. Specifically:

**Authoring scenarios**: When I ask you to add a scenario (e.g., "add a
scenario for GC humongous allocation"), generate:
- The YAML file in `scenarios/NNN_short_name.yaml` matching `_schema.yaml`
- The fixture files in `fixtures/NNN/` (realistic-looking Gatling logs,
  metrics CSVs, thread dumps, etc., synthetic but with the right shape)
- Ensure the ground-truth block has at least 2 required evidence items,
  2-3 red herrings, and 2-3 forbidden claims
- Ensure `expected_signals_in_diagnosis` and `unexpected_signals_warning`
  are populated for the soft graders

**Iterating on prompts**: When I ask you to improve the system prompt or
few-shot examples, modify `prompts/system.md` or `prompts/few_shot_examples.md`
and bump the prompt version in any docs that reference it.

**Adding graders**: When I ask for new graders, add them to
`perf_eval/graders/deterministic.py` or `llm_judge.py`. Always add them
to the `run_deterministic_graders` or `run_llm_graders` function so they
participate in scoring. Weight them appropriately:
- Confidently-wrong checks: weight 2.0+
- Root cause correctness (LLM judge): weight 3.0
- Format/structural checks: weight 0.5

**Evolving the schema**: When new evidence types are needed (e.g., GC logs,
async-profiler output, NMT reports), add them as new top-level keys in
`Inputs` in `schema.py`. Make them optional with sensible defaults so
existing scenarios continue to load. Bump `schema_version` if the change
is breaking.

**Never violate**: Do not pass `Scenario` (full object including ground
truth) to any agent code. Do not put any ground-truth content into prompts.
Do not weaken the contamination check.

### My immediate next steps

1. Install dependencies: `pip install -e .`
2. Add my Anthropic API key to `.env`
3. Run a smoke test on scenario 001: `python scripts/run_evals.py --scenarios 001_jdbc_pool_exhaustion --skip-llm-graders`
4. Once that works, run with LLM judges enabled to get the full score
5. Iterate on the system prompt to see scores improve

Once I'm running, I'll come back to you for help authoring scenarios 002
through 010 — please be ready to suggest a good distribution of failure
modes (GC issues, thread pool starvation, slow query / N+1, cache miss
storms, downstream timeouts, async runaway, classloader leak, etc.).

When I ask you to "add scenario for X", produce the full YAML and all
fixture files in one response. Default to medium difficulty unless I
specify otherwise. Make fixtures realistic in size (Gatling logs should
be at least 50 lines, metrics CSVs should be at least 30 rows, thread
dumps should reference real class/method paths from typical Spring Boot
+ Hibernate + HikariCP stacks).

Confirm you've understood the project layout and design decisions, then
ask me what I want to work on first.
