# Vayal Kaavalan: a spray-safety guardrail agent for Tamil Nadu farmers

By Lakshitha KV

A confident but wrong spray recommendation can destroy a harvest or harm the farmer who follows it.
I built Vayal Kaavalan ("Field Guardian") to make sure that never happens: the agent names a product only when three grounding conditions have been verified against what the farmer actually said.
On the held-out test split of 16 cases and 48 decisions, Strands Decider 2B answered with 83.3% accuracy, a median latency of 369 ms per decision, and a cost of $0.035 per 1,000 decisions.

## The project

Vayal Kaavalan is a Tamil-English agricultural advisory agent for smallholder farmers in Tamil Nadu.
Farmers type short messages in English or Tanglish (Tamil written in English letters, such as "nel payir la blast irukku") and the agent replies in the same language.
The agent can look up a fictional product label table, recommend a spray product, and escalate uncertain cases to a human agriculture officer.
Every spray recommendation goes through a guardrail called SprayGuard before the product name reaches the farmer.

The four things that make it stand out are the guardrail (described below), the Tamil/English language toggle in the UI, the live field panel that visualises each Decider answer as a growing seedling, and the hand-drawn SVG scarecrow mascot that changes pose with each verdict.

Here is a real conversation from the demo, showing a clear case and an escalated case.

Turn 1 -- the farmer sends a Tanglish message with a specific symptom, the correct crop, and an explicit spray request:

Farmer: "Ennoda nel payir la kuzhai thandu karuppu aagudhu, blast maadiri theriyudhu. Nelvin-75WP podalama?"

SprayGuard verdict: proceed (crop_grounded 0.886, pest_match matches_description 0.912, spray_requested 0.934)

Agent: "Nelvin-75WP is approved for paddy blast. Apply 200g per acre and wait 14 days before harvest. FICTIONAL DATA -- confirm with a real agriculture officer before spraying."

Turn 4 -- the farmer sends a very ambiguous Tanglish message with no crop and no symptom detail:

Farmer: "Oru vishayam theriyala, leaf problem irukku, enna spray podanum?"

SprayGuard verdict: confirm (crop_grounded 0.521, pest_match too_vague 0.548, spray_requested 0.612 -- all below 0.65)

Agent: "I am not confident enough to recommend a product here. This case has been sent to an agriculture officer. Please wait for their confirmation before spraying anything."

< FIGURE 1 of 5: upload submission/article/img/bench-accuracy.png here >
Alt text: Per-question accuracy of Strands Decider 2B on the held-out test split: crop_grounded 87.5%, pest_match 87.5%, spray_requested 75.0%, overall 83.3%

## How I built it

The agent is a Strands Agent running Amazon Bedrock Nova Pro for conversation and tool use.
It has three tools: lookup_label (reads the fictional label table), recommend_spray (SprayGuard intercepts this before it runs), and escalate_to_officer (called when the verdict is Confirm).
The demo UI is served by FastAPI with a single HTML/CSS/JS page and no frontend framework.

< FIGURE 2 of 5: upload submission/article/img/architecture.png here >
Alt text: Architecture: the user sends a message to HackathonAgent on Amazon Bedrock, the agent calls lookup_label then recommend_spray, SprayGuard intercepts and calls Strands Decider 2B with three typed questions, the verdict routes to Proceed, Guide, Deny or Confirm

I used Kiro and the spec-driven build workflow: requirements, design, and a task DAG that the agent executed in order, so each layer (data, tools, decision, agent, eval, UI, tests, benchmark) was verified before the next started.
The entire implementation is at https://github.com/Lakshitha-kv/Vayal-Kaavalan-

## The decision handed to Strands Decider 2B

Routing the verdict logic through another LLM call would be slow, expensive, and opaque -- the output would be a natural language string the code cannot branch on directly.
Strands Decider 2B returns calibrated probabilities for typed questions in a single forward pass, typically under 400 ms, and the code reads p_yes for yes/no questions and label for choice questions.
That is what makes the verdict logic plain Python if/else with no prompt engineering.

The three typed questions passed to the Decider in one call:

```python
QUESTIONS = {
    "crop_grounded": Decider.noul(
        "Did the farmer name or clearly imply a specific crop in their messages?",
        {
            "true":  "the farmer explicitly named the crop (e.g. 'nel', 'paddy', 'tomato') "
                     "or the context makes it unambiguous",
            "false": "the crop is assumed, guessed from context, mentioned only as a "
                     "neighbour's crop, or not mentioned at all"
        }
    ),
    "pest_match": Decider.choice(
        "Does the symptom the farmer described match the pest proposed in the spray call?",
        {
            "matches_description": "the farmer described a specific observable symptom "
                                   "that clearly matches the proposed pest",
            "different_problem":   "the farmer described a symptom that does NOT match "
                                   "the proposed pest",
            "too_vague":           "the farmer's description is too general to confirm "
                                   "or deny (e.g. 'plant not good', 'leaves yellowing')"
        }
    ),
    "spray_requested": Decider.noul(
        "Is the farmer asking what to spray, or asking for a product recommendation?",
        {
            "true":  "the farmer asked what to spray or requested a recommendation",
            "false": "the farmer described a problem or asked why it is happening, "
                     "without asking for a product recommendation"
        }
    ),
}
```

The verdict logic reads those answers in this order: if any confidence is below 0.65, return Confirm and escalate to an agriculture officer; if pest_match is too_vague, return Guide and ask the farmer for a more specific symptom description; if pest_match is different_problem, return Deny; if crop_grounded p_yes is below 0.65, return Deny; if spray_requested p_yes is below 0.65, return Deny; otherwise return Proceed.
The state passed to the Decider has three sections: the conversation so far, the proposed tool call arguments, and the label table facts for that product -- identical at runtime and in every eval case.

## Measured

The benchmark ran on the held-out test split (16 cases, 48 decisions across 3 questions).
The Decider ran in ugmdu mode (AWS User Group Madurai hosted API, Strands Decider 2B).

| Metric | Strands Decider 2B |
|---|---|
| Accuracy | 83.3% |
| Latency p50 per decision | 369.1 ms |
| Latency p95 per decision | 408.5 ms |
| Cost per 1,000 decisions | $0.0350 |
| Confident share (>= 0.65) | 85% |
| Accuracy when confident | 87.8% |
| Sent to human officer | 7 of 48 decisions |

Per-question: crop_grounded 87.5%, pest_match 87.5%, spray_requested 75.0%.
Language breakdown: Tanglish 83.3% (4 cases, 12 decisions), English 83.3% (12 cases, 36 decisions).

The spray_requested question is the weakest at 75.0%.
The Decider sometimes marks a spray request as a problem description when the farmer's phrasing is ambiguous -- for example, "enna podalam?" (what can I apply?) scored lower than "enna spray podanum?" (what spray should I use?).
Tanglish accuracy matches English on this dataset, but the Tanglish test set is small (4 cases) so that result should be treated cautiously.
The 15% escalation rate (7 of 48 decisions sent to a human) is intentional -- the Confirm branch exists to catch exactly those cases where the Decider is genuinely uncertain.

< FIGURE 3 of 5: upload submission/article/img/bench-latency.png here >
Alt text: Decision latency for Strands Decider 2B: p50 369 ms, p95 409 ms on the test split

< FIGURE 4 of 5: upload submission/article/img/bench-cost.png here >
Alt text: Cost per 1,000 decisions: $0.035 on the ugmdu hosted API

< FIGURE 5 of 5: upload submission/article/img/bench-confidence.png here >
Alt text: Accuracy vs share of decisions answered alone as the confidence threshold moves, showing the trade-off between coverage and precision

## The reusable decision pattern

The pattern lives in agent/decision.py as the SprayGuard class, which extends InterventionHandler from strands.interventions.
The before_tool_call hook fires on every call to recommend_spray and returns one of Proceed, Guide, Deny, or Confirm.
Any builder can reuse it for a different risky tool call by changing three things: GUARDED_TOOL (the tool name to intercept), QUESTIONS (the typed questions relevant to that tool), and the verdict if/else block.
The key insight is that the Decider handles the uncertainty measurement; the code handles the branching.
This separation means the guardrail is testable with mocks (35 tests pass, including two property tests), auditable in plain Python, and fast enough to fire on every tool call.

A convergence guard prevents infinite loops: if the agent retries the exact same call after a Guide response, the second attempt is always Denied.
The _guided set is cleared on every new farmer message via before_invocation, so it only tracks calls within a single turn.

## What I learned and what is next

The biggest lesson is that calibrated confidence is more useful than a binary yes/no answer.
The Confirm branch -- escalating when any confidence falls below 0.65 -- is what makes the system genuinely safe rather than just accurate on clean inputs.
A system that says "I am not sure" and routes to a human is more trustworthy than one that always gives an answer.

The state format matters more than I expected.
The three-section layout (conversation, proposed call, label facts) is the same at runtime and in every eval case, which means benchmark numbers actually measure production behaviour.
Any drift between the two would make the benchmark meaningless.

Next steps: replace the fictional label table with real Tamil Nadu government pesticide registration data, add a photo input so farmers can attach a leaf image and the Decider can use it in the pest_match question, and extend the eval set with more Tanglish cases to get a reliable language-breakdown number.

---

Code: https://github.com/Lakshitha-kv/Vayal-Kaavalan- . Tags: #strands-decider-2b #guardrails #amazon-bedrock #strands-agents

Built with the AWS User Group Madurai Strands Decider hackathon kit
