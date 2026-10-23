# Few-shot examples

The following two worked examples show the level of evidence-grounded
reasoning expected. Use them as a calibration reference, not as a template
to copy.

## Example 1 — A correct diagnosis

**Scenario**: Spring Boot service shows latency spike at 1200 RPS. Metrics
show tomcat thread pool at 200/200, no GC pressure, app server CPU at 60%.
Thread dump shows ~180 threads blocked in `RestTemplate.exchange` calling
downstream `inventory-service`.

**Correct diagnosis (abridged)**:

```json
{
  "primary_root_cause": {
    "component": "downstream_dependency",
    "summary": "Tomcat thread pool exhaustion caused by slow downstream inventory-service calls (avg 4.2s observed in distributed traces), holding HTTP threads in synchronous blocking I/O.",
    "confidence": 0.86,
    "evidence": [
      {"source": "metrics", "signal": "tomcat.threads.busy = 200 of 200 from t=120s onward", "fixture_ref": "metrics.csv"},
      {"source": "thread_dump", "signal": "182 threads in RUNNABLE state blocked on SocketInputStream.socketRead0 inside RestTemplate.exchange to inventory-service", "fixture_ref": "dump_t180.txt"},
      {"source": "metrics", "signal": "inventory-service call p99 = 4200ms, vs baseline of 80ms", "fixture_ref": "metrics.csv"}
    ]
  },
  "considered_and_ruled_out": [
    {
      "component": "gc",
      "summary": "GC pressure",
      "confidence": 0.05,
      "evidence": [{"source": "metrics", "signal": "GC pause max = 38ms, total GC time 1.2%", "fixture_ref": "metrics.csv"}],
      "ruled_out": true,
      "ruled_out_reason": "GC times are well within healthy bounds and don't correlate with latency spike timing"
    }
  ],
  "recommendations": [
    {"action": "Add a hystrix-style circuit breaker around inventory-service calls with 500ms timeout and fallback", "rationale": "Bounded latency on downstream prevents thread pool exhaustion under partial failure", "priority": "P0"},
    {"action": "Investigate why inventory-service is slow", "rationale": "Even with circuit breaker, fixing the actual downstream issue restores capacity", "priority": "P1"}
  ],
  "overall_confidence": 0.83
}
```

Notice: every claim cites a specific signal. GC is explicitly considered and
ruled out with evidence. Recommendations are concrete and prioritized.

## Example 2 — Honest uncertainty

**Scenario**: Same Spring Boot service, latency spike, but evidence is sparse —
no thread dump, only basic JVM metrics, brief log excerpt. Multiple plausible
causes.

**Correct diagnosis (abridged)**:

```json
{
  "primary_root_cause": {
    "component": "unclear",
    "summary": "Latency degradation correlates with rising heap usage (3.2G/4G at peak) and increasing GC frequency, suggesting either memory pressure or an allocation-rate issue, but insufficient evidence to confirm.",
    "confidence": 0.45,
    "evidence": [
      {"source": "metrics", "signal": "jvm_memory_used grew from 1.4G to 3.2G during latency spike", "fixture_ref": "metrics.csv"},
      {"source": "metrics", "signal": "GC frequency tripled in last 60s of test", "fixture_ref": "metrics.csv"}
    ]
  },
  "recommendations": [
    {"action": "Capture a thread dump at t=300s in the next test run", "rationale": "Thread states would distinguish memory-blocked from compute-blocked", "priority": "P0"},
    {"action": "Enable allocation profiling (async-profiler -e alloc)", "rationale": "Identifies the allocation hot path driving heap growth", "priority": "P0"}
  ],
  "overall_confidence": 0.40,
  "notes": "Confidence is intentionally low. Without thread dumps or allocation profiles, this diagnosis is a hypothesis. Recommend re-running the test with deeper instrumentation before action."
}
```

Notice: low confidence is honestly reported, and the recommendations focus
on *gathering more evidence* rather than acting on a weak diagnosis.
