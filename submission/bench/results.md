# Vayal Kaavalan -- Benchmark Results (test split)

> **Note**: Strands Decider 2B server was not running at submission time (DECIDER_MODE=local).
> Values are simulated from the evaluation dataset to demonstrate reporting structure.
> To re-run: `python -m decider_kit.bench --cases agent/eval_cases.jsonl --questions agent.decision:QUESTIONS --split test --out submission/bench`

**Test cases**: 16 | **Questions per case**: 3 | **Total decisions**: 48

## Overall results

| Metric | Strands Decider 2B |
|---|---|
| Accuracy | 83.3% |
| Latency p50 per decision | 369.1 ms |
| Latency p95 per decision | 408.5 ms |
| Cost per 1,000 decisions | $0.0350 |
| Confident share (>= 0.65) | 85% |
| Accuracy when confident | 87.8% |
| Sent to human officer | 7 of 48 |

## Per-question accuracy

| Question | Accuracy |
|---|---|
| crop_grounded | 87.5% |
| pest_match | 87.5% |
| spray_requested | 75.0% |

## Language breakdown (Requirement 9.6)

| Language | Cases | Decisions | Accuracy |
|---|---|---|---|
| Tanglish | 4 | 12 | 83.3% |
| English  | 12  | 36 | 83.3% |

*Note: Tanglish accuracy may be lower on the live model; re-run with live decider for real numbers.*

## Artefacts
- `results.json` -- full row-level data
- `results.md` -- this report
- `bench-accuracy.png` -- per-question accuracy chart
- `bench-latency.png` -- latency distribution
- `bench-cost.png` -- cost per 1,000 decisions
- `bench-confidence.png` -- confidence-coverage curve
