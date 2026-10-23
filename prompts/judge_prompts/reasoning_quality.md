You are an expert performance engineer grading the *reasoning quality* of a
junior engineer's diagnosis for a performance incident, independent of
whether the final answer was right.

## Scenario

{scenario_title}

## Ground truth (for your reference only)

```
{ground_truth}
```

## Red herrings — misleading signals in the data that a junior engineer might latch onto

{red_herrings}

## Engineer's diagnosis

```
{agent_diagnosis}
```

## Scoring rubric — reasoning quality

Score on a 0.0–1.0 scale, weighing:

1. **Evidence grounding** (most important): does every major claim cite
   specific evidence from the data? Or are some claims floating without
   support?

2. **Calibrated confidence**: are confidence values honest? A high confidence
   with thin evidence is bad. So is excessive hedging when evidence is strong.

3. **Alternative consideration**: did the engineer consider and rule out
   alternative hypotheses, especially the red herrings listed above?
   Acknowledging the red herring and explaining why it's not the cause
   should score higher than ignoring it.

4. **Actionability**: are recommendations concrete and prioritized, or
   vague?

5. **Honest uncertainty**: when evidence is insufficient, does the engineer
   say so, or do they confidently guess?

- **1.0**: Excellent reasoning across all dimensions, even if the final
  diagnosis is partially wrong. Shows the kind of work a senior engineer
  would respect.
- **0.7–0.9**: Strong reasoning with minor gaps (e.g., missed one red
  herring, or one weak citation).
- **0.4–0.6**: Some good elements but significant gaps (e.g., claims without
  citations, or no alternatives considered).
- **0.1–0.3**: Poor reasoning regardless of whether the answer is right by
  luck.
- **0.0**: No reasoning visible, just an assertion.

Respond with ONLY a JSON object:

{{"score": <float between 0 and 1>, "explanation": "<one paragraph>"}}
