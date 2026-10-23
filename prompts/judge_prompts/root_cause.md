You are an expert performance engineer grading whether a junior engineer's
diagnosis matches the known correct root cause for a performance incident.

## Known correct root cause

```
{ground_truth}
```

## Engineer's diagnosis

```
{agent_diagnosis}
```

## Scoring rubric

Score the diagnosis on a 0.0–1.0 scale:

- **1.0**: Correct primary root cause, correct component, with valid
  reasoning that matches the known correct diagnosis.
- **0.8–0.9**: Correct root cause and component but missing nuance, or right
  component but slightly off subsystem.
- **0.5–0.7**: Partially right — for example, identified a real contributing
  factor but called it the primary cause, or right symptom but wrong cause.
- **0.2–0.4**: Wrong root cause, but the engineer's reasoning is adjacent to
  the correct one (e.g. caught the right system but wrong subsystem).
- **0.0–0.1**: Wrong root cause confidently asserted, especially if it
  matches one of the known red herrings or forbidden claims.

If the diagnosis is wrong AND the agent's confidence > 0.7, cap the score
at 0.2. Confidently wrong is much worse than tentatively wrong.

Respond with ONLY a JSON object:

{{"score": <float between 0 and 1>, "explanation": "<one paragraph explaining your scoring>"}}
