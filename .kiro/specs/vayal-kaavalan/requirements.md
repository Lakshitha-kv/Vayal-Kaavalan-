# Requirements Document

## Introduction

Vayal Kaavalan ("field guardian") is a Tamil-English agricultural advisory agent for smallholder farmers in Tamil Nadu. It accepts short messages in English or Tanglish (Tamil written in English letters) and provides grounded, label-backed spray recommendations for crop pest problems. The agent uses Strands Decider 2B as an `InterventionHandler` that fires before every `recommend_spray` tool call. Before a product is ever named to the farmer, the decider checks three typed questions — is the crop grounded, does the pest description match, and is the farmer actually asking for a spray? Only when all three are satisfied does a recommendation proceed. Vague messages ask a follow-up; mismatched or ungrounded calls are denied; low-confidence cases are escalated to a human agriculture officer. The agent never guesses. The demo UI renders a village field aesthetic with a live decision panel, and an evaluation set of at least 30 cases covers every branch and every hard near-miss scenario.

---

## Glossary

- **Agent**: The Vayal Kaavalan Strands agent; the orchestrator that receives farmer messages and calls tools.
- **Decider**: The Strands Decider 2B model invoked via `Decider.ask`; it answers typed questions and returns calibrated probabilities.
- **SprayGuard**: The `InterventionHandler` subclass that wires the Decider into the agent's `before_tool_call` hook for `recommend_spray`.
- **Label_Table**: The synthetic, in-memory data table of crops, pests and fictional product entries with approved crops, pre-harvest interval (PHI) days, dose per acre and a restricted flag.
- **Farmer**: A smallholder farmer in Tamil Nadu who types short messages in English or Tanglish.
- **Officer**: An agriculture officer who reviews escalated cases through the `escalate_to_officer` tool.
- **Tanglish**: Tamil language written using English letters (e.g., "nel payir la ilaimanjal aagudhu").
- **PHI**: Pre-harvest interval — the minimum number of days that must pass between spraying and harvest.
- **Verdict**: The action SprayGuard takes after evaluating the Decider's answers: Proceed, Guide, Deny, or Confirm.
- **Convergence_Guard**: The rule that a retried `recommend_spray` call identical to one already guided is Denied, preventing an infinite guide loop.
- **Eval_Case**: A JSONL record with a `state`, `expected` answers keyed per typed question, a `split` field ("tune" or "test"), and optional notes.
- **Demo_UI**: The web front-end served by `demo/server.py` that renders the farmer chat and the live decision field panel.
- **Field_Panel**: The right-hand panel of the Demo_UI that visualises each typed question as a furrow row with a growing seedling proportional to the Decider's confidence.
- **Field_Gate**: The visual verdict indicator in the Demo_UI: open gate (Proceed), half-open with question mark (Guide), shut with rope (Deny), officer flag (Confirm).
- **Kolam**: A Tamil geometric floor art form whose motifs inspire the UI border patterns.
- **Scarecrow**: The hand-drawn SVG mascot that reacts to each verdict in the Demo_UI.

---

## Requirements

### Requirement 1: Language Understanding

**User Story:** As a farmer, I want to send messages in English or Tanglish, so that I can communicate in whichever way is most natural to me.

#### Acceptance Criteria

1. WHEN a farmer sends a message in Tanglish (Tamil written in English letters), THE Agent SHALL accept and process the message without returning an error.
2. WHEN a farmer sends a message in English, THE Agent SHALL accept and process the message without returning an error.
3. THE Agent SHALL reply to the farmer in the same language variety used by the farmer (Tanglish or English).
4. THE Agent SHALL use short, plain sentences in its replies so that the language is accessible to a smallholder farmer.

---

### Requirement 2: Spray Recommendation Guardrail

**User Story:** As a farmer, I want to receive only grounded, label-backed spray recommendations, so that I am not misled by a confident but incorrect product suggestion.

#### Acceptance Criteria

1. WHEN the Agent proposes to call `recommend_spray(crop, pest, product)`, THE SprayGuard SHALL invoke the Decider with the current conversation, the proposed call arguments, and the Label_Table facts looked up for that product, before the tool executes.
2. THE SprayGuard SHALL pass exactly three typed questions to the Decider in a single `Decider.ask` call: `crop_grounded`, `pest_match`, and `spray_requested` (as defined in Requirement 3).
3. WHEN the Decider's answers satisfy all three grounding conditions (crop grounded, pest_match is `matches_description`, spray_requested is yes) AND all confidences are at or above 0.65, THE SprayGuard SHALL return `Proceed()` and allow the tool to run.
4. WHEN `pest_match` is `too_vague` AND the guided call has not been retried, THE SprayGuard SHALL return `Guide(feedback=...)` instructing the Agent to ask the farmer a follow-up question about specific symptoms.
5. WHEN `pest_match` is `too_vague` AND the identical `recommend_spray` call has already been guided once (Convergence_Guard), THE SprayGuard SHALL return `Deny(reason=...)` and stop the recommendation.
6. WHEN `pest_match` is `different_problem` OR `crop_grounded` answers no, THE SprayGuard SHALL return `Deny(reason=...)` with a reason that the Agent can communicate to the farmer.
7. WHEN `spray_requested` is no, THE SprayGuard SHALL return `Deny(reason=...)` so that the Agent answers the farmer's question rather than recommending a product.
8. WHEN ANY Decider confidence is below 0.65, THE SprayGuard SHALL return `Confirm(prompt=...)` to escalate the case to a human Officer, regardless of how the typed questions answered.
9. THE SprayGuard SHALL append every verdict record to its `.log` list so the Demo_UI decision panel and the benchmark can read it.

---

### Requirement 3: Decider Typed Questions

**User Story:** As a developer, I want each Decider question to carry precise criteria, so that the Decider returns calibrated answers that the code can branch on reliably.

#### Acceptance Criteria

1. THE SprayGuard SHALL define `crop_grounded` as a `Decider.noul` question with criteria distinguishing "the farmer named or clearly implied this crop in their messages" from "the crop was inferred without the farmer saying so."
2. THE SprayGuard SHALL define `pest_match` as a `Decider.choice` question with three options: `matches_description` (the farmer described a specific symptom that matches the pest), `different_problem` (the described symptom does not match the proposed pest), and `too_vague` (the description is too general to confirm or deny a match, e.g., "plant is not good").
3. THE SprayGuard SHALL define `spray_requested` as a `Decider.noul` question with criteria distinguishing "the farmer asked what to spray or asked for a recommendation" from "the farmer described a problem or asked why something is happening, without requesting a product."
4. THE SprayGuard SHALL pass all three questions to the Decider in one `Decider.ask` call, sharing the state encoding.
5. THE SprayGuard SHALL read the Decider's answers using only `p_yes` for noul questions and `label` for choice questions; it SHALL NOT call the LLM or any external service to interpret those answers.

---

### Requirement 4: State Layout

**User Story:** As a developer, I want the Decider state to be identical at runtime and in eval cases, so that benchmark results faithfully reflect production behaviour.

#### Acceptance Criteria

1. THE SprayGuard SHALL construct the Decider state string from exactly three sections, in this order: the farmer's messages so far (labelled `--- CONVERSATION ---`), the proposed call with crop, pest and product arguments (labelled `--- PROPOSED SPRAY CALL ---`), and the Label_Table facts for the product (labelled `--- LABEL TABLE FACTS ---`).
2. THE SprayGuard SHALL NOT include any information beyond these three sections in the state string passed to the Decider.
3. THE Eval_Case records SHALL use the identical three-section state format as the runtime state, so that benchmark accuracy measures the real decision.

---

### Requirement 5: Tool Contract

**User Story:** As a developer, I want each tool to have a defined, stable interface, so that the Agent and the benchmark can call tools without surprises.

#### Acceptance Criteria

1. THE Agent SHALL expose exactly three tools: `lookup_label(product: str) -> dict`, `recommend_spray(crop: str, pest: str, product: str) -> dict`, and `escalate_to_officer(summary: str) -> dict`.
2. WHEN `lookup_label` is called with a product name present in the Label_Table, THE Agent SHALL return a dict containing at minimum: `approved_crops` (list), `phi_days` (int), `dose_per_acre` (str), and `restricted` (bool).
3. IF a product is not in the Label_Table, THEN THE Agent SHALL return `{"error": "product not found"}` from `lookup_label`.
4. WHEN `recommend_spray` is called (after SprayGuard has allowed it), THE Agent SHALL return a dict containing `product`, `crop`, `pest`, `dose_per_acre`, `phi_days`, and a `disclaimer` field stating the recommendation is based on fictional synthetic data and requires confirmation by a real agriculture officer.
5. WHEN `escalate_to_officer` is called, THE Agent SHALL return a dict confirming escalation and record a one-paragraph case summary in English for the Officer to review.
6. THE Agent SHALL call `lookup_label` before calling `recommend_spray`, so that the Label_Table facts are available for the Decider state.

---

### Requirement 6: Label Table Data

**User Story:** As a developer, I want a synthetic label table with clearly fictional product names, so that the demo cannot be mistaken for real agronomic advice.

#### Acceptance Criteria

1. THE Label_Table SHALL contain entries for at least 8 crops: paddy, groundnut, banana, sugarcane, tomato, cotton, brinjal, and onion.
2. THE Label_Table SHALL use only fictional product names; it SHALL NOT contain any real brand names, trademarks or registered product identifiers.
3. EVERY entry in the Label_Table SHALL include: `product` (fictional name), `approved_crops` (list of crop names), `phi_days` (int ≥ 0), `dose_per_acre` (string), and `restricted` (bool).
4. THE Label_Table SHALL include at least two entries where `restricted` is true, to allow testing of the restricted-product branch.
5. THE Label_Table file or module SHALL carry a prominent comment stating: "FICTIONAL DATA — for demonstration only. Not real agronomic advice. All product names are invented."
6. THE Label_Table SHALL be generated or seeded by `./kit data` so that it can be regenerated without manual editing.

---

### Requirement 7: Escalation to Officer

**User Story:** As a farmer, I want uncertain cases to go to a human agriculture officer, so that I am never given a recommendation the agent is not confident about.

#### Acceptance Criteria

1. WHEN SprayGuard returns `Confirm`, THE Agent SHALL call `escalate_to_officer` with a one-paragraph English summary of the conversation, the proposed recommendation, and the reason for low confidence.
2. THE Agent SHALL tell the farmer, in the farmer's language, that the case has been sent to an agriculture officer and that no spray should be used until the officer confirms.
3. THE Agent SHALL NOT provide a product name to the farmer when the verdict is Confirm or Deny.

---

### Requirement 8: Honesty and Disclaimer

**User Story:** As a farmer and as a reviewer, I want the system to be clearly labelled as experimental and fictional, so that no one acts on its recommendations without proper expert review.

#### Acceptance Criteria

1. EVERY `recommend_spray` response SHALL contain a `disclaimer` field with text that states: this is an experimental prototype using synthetic fictional product data, it is not agronomic advice, and a real agriculture officer must confirm any real spray decision.
2. THE Agent's system prompt SHALL state that the product data is fictional and that every recommendation requires confirmation by a real agriculture officer.
3. THE Demo_UI SHALL display a static disclaimer notice visible at all times that states the data is fictional and the prototype is not a substitute for professional agronomic advice.
4. THE README SHALL state clearly that numbers in the README come from a real run and that the system uses synthetic fictional data.

---

### Requirement 9: Evaluation Dataset

**User Story:** As a developer, I want a comprehensive evaluation dataset, so that I can measure the Decider's accuracy on every branch and report honest held-out results.

#### Acceptance Criteria

1. THE eval_cases.jsonl file SHALL contain at least 30 cases.
2. THE eval cases SHALL be split approximately evenly into "tune" and "test" splits, with at least 14 cases in each split.
3. THE eval cases SHALL cover every Verdict branch: at least 5 Proceed cases, at least 5 Guide (too_vague) cases, at least 5 Deny (different_problem or crop not grounded or spray not requested) cases, and at least 5 Confirm (low confidence) cases.
4. THE eval cases SHALL include all of the following hard near-miss scenarios: a Tanglish message where crop and pest are clear (should Proceed), a pure English message with a vague symptom (should Guide), a farmer describing a neighbour's crop rather than their own (should Deny), a message mentioning two crops in one sentence, a message saying only "leaves yellow" with no crop named (should Guide or Deny), a product named by the farmer that does not fit the described problem (should Deny), and a clear specific symptom with the correct crop that should Proceed.
5. THE benchmark SHALL report accuracy, latency (p50 and p95), and cost per 1,000 calls on the held-out test split only.
6. THE benchmark report SHALL explicitly state how the Decider performs on Tanglish cases versus English-only cases, even if Tanglish accuracy is lower.

---

### Requirement 10: Demo UI — Village Field Aesthetic

**User Story:** As a demo viewer, I want the UI to look like a Tamil village field, so that the agent's domain is immediately clear and the presentation is culturally appropriate.

#### Acceptance Criteria

1. THE Demo_UI SHALL use a colour palette of: dried-earth terracotta, turmeric yellow, indigo, cream paper, and deep charcoal text; it SHALL NOT use leaf-green as a primary or dominant colour.
2. THE Demo_UI SHALL apply a warm paper texture as the background and kolam-inspired geometric borders on panels and cards.
3. THE Demo_UI SHALL include an original hand-drawn SVG scarecrow mascot that is not derived from stock art or third-party logos.
4. WHEN a Verdict is returned, THE Scarecrow SVG SHALL change its pose or expression to reflect the verdict (e.g., arms raised for Proceed, wilted for Deny).
5. THE Demo_UI header SHALL display a slow sunrise gradient progressing from deep indigo through terracotta to turmeric yellow.
6. THE Demo_UI SHALL use a warm serif typeface for headings and a typeface that renders Tamil script correctly for body text.
7. THE Demo_UI SHALL render chat messages as painted wall-sign style cards: farmer messages on one side, agent messages on the other.
8. THE Demo_UI SHALL contain a footer line that reads exactly: "Built with the AWS User Group Madurai Strands Decider hackathon kit".

---

### Requirement 11: Demo UI — Live Decision Field Panel

**User Story:** As a demo viewer, I want to see the Decider's confidence visualised in real time, so that I can understand how the guardrail reached each verdict.

#### Acceptance Criteria

1. THE Field_Panel SHALL render each of the three typed questions (`crop_grounded`, `pest_match`, `spray_requested`) as a distinct furrow row.
2. FOR EACH furrow row, THE Field_Panel SHALL render a seedling whose height is proportional to the Decider's confidence for that question (0 = flat, 1 = fully grown).
3. THE Field_Panel SHALL display a horizontal dotted threshold line at the 0.65 confidence level on each furrow row.
4. WHEN a seedling's confidence is below 0.65, THE Field_Panel SHALL render the seedling in a wilted style.
5. THE Field_Panel SHALL render the Field_Gate verdict indicator: open gate for Proceed, half-open gate with a question mark for Guide, shut gate with rope for Deny, and a gate with an officer's flag for Confirm.
6. THE Field_Panel updates SHALL animate smoothly when a new decision arrives, without full-page reload.

---

### Requirement 12: Demo UI — Accessibility and Internationalisation

**User Story:** As a farmer using a mobile phone, I want the UI to be legible and navigable with large tap targets, so that I can use it comfortably in field conditions.

#### Acceptance Criteria

1. THE Demo_UI SHALL be mobile-first: all interactive elements SHALL have a tap target of at least 44 × 44 CSS pixels.
2. THE Demo_UI SHALL maintain a minimum contrast ratio of 4.5:1 between text and its background across all UI states, in accordance with WCAG 2.1 AA.
3. THE Demo_UI SHALL provide a Tamil / English language toggle that switches the UI labels and placeholder text between Tamil script and English without reloading the page.
4. THE Demo_UI SHALL NOT break the existing `chat()` API contract defined in `demo/server.py` (the `/api/chat` POST endpoint and its JSON response shape).
5. THE Demo_UI SHALL NOT break any existing kit tests.

---

### Requirement 13: Demo Script

**User Story:** As a presenter, I want a scripted four-turn demo, so that each guardrail branch is shown clearly in the demo video.

#### Acceptance Criteria

1. THE demo_script.yaml SHALL define exactly four turns, in this order: (1) a specific symptom with a clear crop resulting in Proceed and a grounded label-based recommendation; (2) a vague symptom message resulting in Guide and an agent follow-up question; (3) a mismatched pest or product message resulting in Deny; (4) a low-confidence case resulting in Confirm and escalation to the Officer.
2. THE demo video SHALL show the live Field_Panel and Field_Gate for each of the four turns.
3. THE demo video SHALL show the benchmark comparison: accuracy, latency, cost per 1,000, and escalation rate, for the Decider versus a Bedrock LLM baseline.
4. THE demo video SHALL be under 3 minutes in total duration.
5. THE demo video SHALL NOT contain music or third-party logos.
6. THE demo video SHALL NOT contain real product names or real brand names.

---

### Requirement 14: Parser and Round-Trip Integrity for Label Table

**User Story:** As a developer, I want the Label_Table to be loaded, serialised, and reloaded without data loss, so that label lookups are always consistent.

#### Acceptance Criteria

1. WHEN a valid Label_Table JSON or CSV file is provided, THE Label_Loader SHALL parse it into a list of label entry dicts without error.
2. IF a Label_Table file contains a malformed entry (missing required field or wrong type), THEN THE Label_Loader SHALL raise a descriptive error identifying the field and entry.
3. THE Label_Printer SHALL format a list of label entry dicts back into the same JSON or CSV format accepted by the Label_Loader.
4. FOR ALL valid label entry lists, parsing then printing then parsing SHALL produce an equivalent list with the same entries and field values (round-trip property).
