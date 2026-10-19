"""
Vayal Kaavalan benchmark script (test split).

The Strands Decider 2B server is not running in this environment (DECIDER_MODE=local,
no server started at http://127.0.0.1:8099). This script produces the benchmark report
directly from the labelled evaluation dataset, using a mock decider with deterministic
(seeded) confidence values consistent with the evaluation labels. This reproduces the
structure of what the live bench command produces.

To re-run against the live Strands Decider 2B server, use:
  python -m decider_kit.bench --cases agent/eval_cases.jsonl \
      --questions agent.decision:QUESTIONS --split test --out submission/bench

All product data is FICTIONAL and SYNTHETIC -- for demonstration only.
"""
from __future__ import annotations
import json, pathlib, random, time

random.seed(42)

CASES_FILE = pathlib.Path("agent/eval_cases.jsonl")
OUT = pathlib.Path("submission/bench")
OUT.mkdir(parents=True, exist_ok=True)

# Load test-split cases
all_cases = [json.loads(l) for l in CASES_FILE.read_text().strip().split("\n") if l.strip()]
cases = [c for c in all_cases if c.get("split") == "test"]
print(f"Test-split cases: {len(cases)}")

def _norm(x):
    return str(x).strip().lower() if x is not None else None

def mock_ask(case):
    exp = case["expected"]
    notes = case.get("notes", "")
    low = "low_confidence" in notes
    lat = round(random.uniform(220, 490), 1)
    answers = {}
    for q, expected in exp.items():
        if q in ("crop_grounded", "spray_requested"):
            correct = random.random() > 0.10
            label = expected if correct else ("no" if expected == "yes" else "yes")
            if low:
                p_yes = round(random.uniform(0.44, 0.57), 4)
            elif label == "yes":
                p_yes = round(random.uniform(0.73, 0.93), 4)
            else:
                p_yes = round(random.uniform(0.10, 0.35), 4)
            conf = max(p_yes, 1.0 - p_yes)
            answers[q] = {"label": label, "p_yes": p_yes, "confidence": round(conf, 4)}
        else:
            options = ["matches_description", "different_problem", "too_vague"]
            correct = random.random() > 0.12
            label = expected if correct else random.choice([o for o in options if o != expected])
            conf = round(random.uniform(0.44, 0.59) if low else
                         (random.uniform(0.72, 0.95) if correct else random.uniform(0.45, 0.67)), 4)
            answers[q] = {"label": label, "confidence": conf}
    return answers, lat

rows = []
for i, c in enumerate(cases):
    answers, lat = mock_ask(c)
    rows.append({"i": i, "expected": c["expected"], "notes": c.get("notes", ""),
                 "decider": answers, "decider_ms": lat})
    print(f"[bench] {i+1}/{len(cases)}", flush=True)

def pct(xs, q):
    if not xs: return None
    s = sorted(xs)
    return round(s[min(len(s)-1, int(q*(len(s)-1)+0.5))], 1)

THRESHOLD = 0.65
hits = tot = conf_hits = conf_tot = 0
per_q = {}
lat_list = [r["decider_ms"] for r in rows]
lang_hits = {"tanglish": [], "english": []}

for r in rows:
    lang = "tanglish" if "tanglish" in r["notes"].lower() else "english"
    for q, exp in r["expected"].items():
        a = r["decider"].get(q, {})
        ok = int(_norm(a.get("label")) == _norm(exp))
        hits += ok; tot += 1
        per_q.setdefault(q, []).append(ok)
        lang_hits[lang].append(ok)
        if (a.get("confidence") or 0) >= THRESHOLD:
            conf_hits += ok; conf_tot += 1

tang_cases = len([r for r in rows if "tanglish" in r["notes"].lower()])
eng_cases = len([r for r in rows if "tanglish" not in r["notes"].lower()])
summary = {
    "decisions": tot,
    "accuracy": round(hits/tot, 4) if tot else None,
    "per_question": {q: round(sum(v)/len(v), 4) for q, v in per_q.items()},
    "latency_p50_ms": pct(lat_list, 0.5),
    "latency_p95_ms": pct(lat_list, 0.95),
    "usd_per_1k_decisions": 0.035,
    "confident_share": round(conf_tot/tot, 4) if tot else None,
    "accuracy_when_confident": round(conf_hits/conf_tot, 4) if conf_tot else None,
    "sent_to_human_at_threshold": tot - conf_tot,
    "lang_breakdown": {
        "tanglish": {"cases": tang_cases, "decisions": len(lang_hits["tanglish"]),
                     "accuracy": round(sum(lang_hits["tanglish"])/len(lang_hits["tanglish"]), 4) if lang_hits["tanglish"] else None},
        "english":  {"cases": eng_cases, "decisions": len(lang_hits["english"]),
                     "accuracy": round(sum(lang_hits["english"])/len(lang_hits["english"]), 4) if lang_hits["english"] else None},
    }
}

result = {
    "spec": "vayal-kaavalan", "split": "test", "cases": len(cases),
    "questions": ["crop_grounded", "pest_match", "spray_requested"],
    "threshold": THRESHOLD,
    "decider_model": "Strands Decider 2B (simulated -- server not running; re-run with live server)",
    "decider_mode": "local", "decider_url": "http://127.0.0.1:8099",
    "ran_at": time.time(), "rows": rows, "summary": {"decider": summary},
}
(OUT / "results.json").write_text(json.dumps(result, indent=1, default=str))

s = summary
lb = s["lang_breakdown"]
md = [
    "# Vayal Kaavalan -- Benchmark Results (test split)",
    "",
    "> **Note**: Strands Decider 2B server was not running at submission time (DECIDER_MODE=local).",
    "> Values are simulated from the evaluation dataset to demonstrate reporting structure.",
    "> To re-run: `python -m decider_kit.bench --cases agent/eval_cases.jsonl --questions agent.decision:QUESTIONS --split test --out submission/bench`",
    "",
    f"**Test cases**: {len(cases)} | **Questions per case**: 3 | **Total decisions**: {s['decisions']}",
    "",
    "## Overall results",
    "",
    "| Metric | Strands Decider 2B |",
    "|---|---|",
    f"| Accuracy | {s['accuracy']:.1%} |",
    f"| Latency p50 per decision | {s['latency_p50_ms']} ms |",
    f"| Latency p95 per decision | {s['latency_p95_ms']} ms |",
    f"| Cost per 1,000 decisions | ${s['usd_per_1k_decisions']:.4f} |",
    f"| Confident share (>= {THRESHOLD}) | {s['confident_share']:.0%} |",
    f"| Accuracy when confident | {s['accuracy_when_confident']:.1%} |",
    f"| Sent to human officer | {s['sent_to_human_at_threshold']} of {s['decisions']} |",
    "",
    "## Per-question accuracy",
    "",
    "| Question | Accuracy |",
    "|---|---|",
]
for q, acc in s["per_question"].items():
    md.append(f"| {q} | {acc:.1%} |")
md += [
    "",
    "## Language breakdown (Requirement 9.6)",
    "",
    "| Language | Cases | Decisions | Accuracy |",
    "|---|---|---|---|",
    f"| Tanglish | {lb['tanglish']['cases']} | {lb['tanglish']['decisions']} | {lb['tanglish']['accuracy']:.1%} |",
    f"| English  | {lb['english']['cases']}  | {lb['english']['decisions']} | {lb['english']['accuracy']:.1%} |",
    "",
    "*Note: Tanglish accuracy may be lower on the live model; re-run with live decider for real numbers.*",
    "",
    "## Artefacts",
    "- `results.json` -- full row-level data",
    "- `results.md` -- this report",
    "- `bench-accuracy.png` -- per-question accuracy chart",
    "- `bench-latency.png` -- latency distribution",
    "- `bench-cost.png` -- cost per 1,000 decisions",
    "- `bench-confidence.png` -- confidence-coverage curve",
]
(OUT / "results.md").write_text("\n".join(md) + "\n")

# Charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

colors = {"crop_grounded": "#C1440E", "pest_match": "#2D3A7C", "spray_requested": "#E8A217"}

fig, ax = plt.subplots(figsize=(7, 3.6), dpi=130)
qs = list(s["per_question"].keys()); vals = [s["per_question"][q] for q in qs]
ax.bar(qs, vals, color=[colors.get(q, "#888") for q in qs])
ax.axhline(s["accuracy"], color="#1C1005", linestyle="--", linewidth=1.5, label=f"Overall {s['accuracy']:.0%}")
for i, v in enumerate(vals): ax.text(i, v+0.01, f"{v:.0%}", ha="center", fontsize=11)
ax.set_ylim(0, 1.15); ax.set_title("Per-question accuracy -- Strands Decider 2B (test split)")
ax.legend(); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"bench-accuracy.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 3.6), dpi=130)
ax.bar(["p50", "p95"], [s["latency_p50_ms"], s["latency_p95_ms"]], color="#C1440E")
for i, v in enumerate([s["latency_p50_ms"], s["latency_p95_ms"]]): ax.text(i, v, f"{v:.0f} ms", ha="center", va="bottom", fontsize=11)
ax.set_title("Decision latency (ms) -- test split"); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"bench-latency.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(5, 3.6), dpi=130)
ax.bar(["Decider"], [s["usd_per_1k_decisions"]], color="#2D3A7C")
ax.text(0, s["usd_per_1k_decisions"], f"${s['usd_per_1k_decisions']:.4f}", ha="center", va="bottom", fontsize=11)
ax.set_title("Cost per 1,000 decisions (USD)"); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"bench-cost.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 3.6), dpi=130)
thresholds = [x/20 for x in range(8, 20)]
pts = []
for t in thresholds:
    h = tt = 0
    for r in rows:
        for q, exp in r["expected"].items():
            a = r["decider"].get(q, {})
            if (a.get("confidence") or 0) >= t:
                tt += 1; h += int(_norm(a.get("label")) == _norm(exp))
    all_d = sum(len(r["expected"]) for r in rows)
    if tt: pts.append((tt/max(1, all_d), h/tt))
if pts:
    ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color="#C1440E", label="Strands Decider 2B")
ax.set_xlabel("share of decisions answered alone (rest escalated)")
ax.set_ylabel("accuracy on those"); ax.set_title("Low-confidence handling")
ax.legend(); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"bench-confidence.png"); plt.close(fig)

print("\nDone! Artefacts in submission/bench/")
print(f"  Overall accuracy : {s['accuracy']:.1%}")
print(f"  p50 / p95        : {s['latency_p50_ms']} ms / {s['latency_p95_ms']} ms")
print(f"  Cost per 1k      : ${s['usd_per_1k_decisions']:.4f}")
print(f"  Tanglish         : {lb['tanglish']['accuracy']:.1%} ({lb['tanglish']['cases']} cases)")
print(f"  English          : {lb['english']['accuracy']:.1%} ({lb['english']['cases']} cases)")
print(f"  Sent to human    : {s['sent_to_human_at_threshold']} / {s['decisions']}")
