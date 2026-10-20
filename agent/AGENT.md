# Use case

- **Pitch:** a Tamil-English spray-safety guardrail agent that recommends a fictional pesticide only when the crop, pest and spray request are grounded in what the farmer actually said.
- **Who it is for:** smallholder farmers in Tamil Nadu who type short messages in English or Tanglish (Tamil written in English letters), and anyone building safety guardrails for agentic tool calls.
- **Features:**
  - accepts English and Tanglish messages and replies in the farmer's language;
  - looks up a fictional label table before any recommendation and passes the facts to the decider;
  - SprayGuard intercepts every recommend_spray call and checks three typed questions before the tool runs;
  - four verdict branches: Proceed (all pass), Guide (symptom too vague), Deny (mismatch or ungrounded), Confirm (low confidence, escalates to a human agriculture officer);
  - live field panel in the demo UI: three seedling rows scaled by decider confidence, a field gate SVG that changes state per verdict, and a hand-drawn scarecrow mascot that changes pose;
  - Tamil/English language toggle in the UI.
- **The decision handed to Strands Decider 2B:** before recommend_spray runs, are the crop, pest description and spray request grounded in the farmer's actual message? (`#guardrails`)
- **Why a decision model:** the check fires on every spray call; it must be fast, cheap and return calibrated probabilities the Python verdict logic can branch on directly.
- **Amazon Bedrock:** the conversation and tool use (Amazon Nova Pro by default).
