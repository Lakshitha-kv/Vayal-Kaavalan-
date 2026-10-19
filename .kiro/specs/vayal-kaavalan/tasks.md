# Implementation Plan: Vayal Kaavalan ("Field Guardian")

## Overview

Replace the kit's store-refund example with the Vayal Kaavalan agricultural advisory agent. Tasks follow the data→tools→decision→agent→eval→UI→tests→bench order so each step builds cleanly on the previous one. All files live inside `lakshitha-kv-decider-hackathon-kit/`.

## Tasks

- [x] 1. Create the label data file (`agent/data/labels.json`)
  - Create `agent/data/` directory if it does not exist
  - Write `labels.json` as a JSON array of ~20 fictional product entries with a top-level `_disclaimer` key
  - Cover exactly these 8 crops (at least one entry per crop): paddy, groundnut, banana, sugarcane, tomato, cotton, brinjal, onion
  - Include at least 2 entries where `"restricted": true`
  - Every entry must have exactly these five fields: `product` (fictional name, e.g. "Nelvin-75WP"), `approved_crops` (list), `phi_days` (int ≥ 0), `dose_per_acre` (str), `restricted` (bool)
  - Use only invented product names — no real brands, trademarks, or registered identifiers
  - Add the `_disclaimer` key as the first entry: `"FICTIONAL DATA — for demonstration only. Not real agronomic advice. All product names are invented."`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. Implement the tools module (`agent/tools.py`)
  - [x] 2.1 Implement `lookup_label`, `recommend_spray`, `escalate_to_officer` and `LABEL_TABLE`
    - Replace the entire file; keep `from strands import tool` and `TOOLS = [...]` list at module level
    - Load `LABEL_TABLE` from `labels.json` at import time using `decider_kit.data.load("labels")`, keyed by `product.lower()`; skip keys starting with `_`
    - Validate required fields on load and raise a descriptive `ValueError` for any entry missing `product`, `approved_crops`, `phi_days`, `dose_per_acre`, or `restricted`
    - `lookup_label(product: str) -> dict`: return the five required fields or `{"error": "product not found"}`
    - `recommend_spray(crop: str, pest: str, product: str) -> dict`: return `product`, `crop`, `pest`, `dose_per_acre`, `phi_days`, `restricted`, and a `disclaimer` field with the required fictional-data text
    - `escalate_to_officer(summary: str) -> dict`: return `{"escalated": True, "message": "...", "summary": summary}`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 8.1_

  - [x] 2.2 Write unit tests for tools (`agent/tests/test_tools.py`)
    - Test `lookup_label` with a known product name → returns dict with all five fields
    - Test `lookup_label` with an unknown product → returns `{"error": "product not found"}`
    - Test `recommend_spray` with a known product → returned dict has `disclaimer` field containing "FICTIONAL"
    - Test `escalate_to_officer` with a summary string → returned dict has `escalated=True` and `summary` matches input
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [x] 3. Implement the SprayGuard decision module (`agent/decision.py`)
  - [x] 3.1 Define constants, QUESTIONS, and SprayGuard class
    - Set `IS_KIT_EXAMPLE = False`, `PATTERN_TAG = "#guardrails"`, `FEATURE_TAG = "#strands-decider-2b"`, `GUARDED_TOOL = "recommend_spray"`, `CONFIDENCE_THRESHOLD = 0.65`
    - Define `QUESTIONS` dict with exactly three keys: `crop_grounded` (Decider.noul), `pest_match` (Decider.choice with three options: `matches_description`, `different_problem`, `too_vague`), `spray_requested` (Decider.noul) — using exact criteria text from the design
    - Import `render_messages` from `decider_kit.patterns.guardrails`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 2.2_

  - [x] 3.2 Implement `SprayGuard.before_invocation` and state builder
    - `before_invocation` clears `self._guided` and returns `Proceed()`
    - Implement `_build_state(messages, args, lookup_result)` that constructs the exact three-section state string: `--- CONVERSATION ---\n{render_messages(messages)}\n\n--- PROPOSED SPRAY CALL ---\ntool: recommend_spray\narguments: {json.dumps(args)}\n\n--- LABEL TABLE FACTS ---\n{json.dumps(lookup_result)}`
    - _Requirements: 4.1, 4.2, 2.1_

  - [x] 3.3 Implement `SprayGuard.before_tool_call` verdict logic
    - Skip non-`recommend_spray` tool calls with `Proceed()`
    - Convergence guard: if `sig` already in `self._guided`, log and return `Deny`
    - Call `lookup_label(args["product"])` to get label facts, then `self.decider.ask(state, QUESTIONS)` — exactly one call per interception
    - Apply verdict if/else in this exact order: (1) any confidence < 0.65 → `Confirm`; (2) `pest_match.label == "too_vague"` → `Guide` and add sig to `_guided`; (3) `pest_match.label == "too_vague"` retry (now in `_guided`) → `Deny`; (4) `pest_match.label == "different_problem"` → `Deny`; (5) `cg.p_yes < 0.65` → `Deny`; (6) `sr.p_yes < 0.65` → `Deny`; (7) all pass → `Proceed`
    - Append log record after every verdict: `pattern`, `tool`, `args`, `crop_grounded`, `pest_match`, `pest_match_confidence`, `spray_requested`, `verdict`, `decider_ms`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.5_

  - [x] 2.4 Write property and unit tests for SprayGuard (`agent/tests/test_decision.py`)
    - Mock `Decider.ask` to return controlled `Decision` objects (use `unittest.mock.MagicMock`)
    - **Property 1: Single Decider call per non-convergence interception** — for every non-retried `before_tool_call` invocation, `decider.ask` is called exactly once. Validates: Requirements 2.1
    - **Property 2: Three questions in every ask call** — the `questions` dict passed to `decider.ask` always has exactly the keys `crop_grounded`, `pest_match`, `spray_requested`. Validates: Requirements 2.2, 3.4
    - Test Proceed branch: all confidences ≥ 0.65, `pest_match=matches_description`, `crop_grounded p_yes=0.9`, `spray_requested p_yes=0.9` → returns `Proceed`
    - Test Guide branch: `pest_match=too_vague`, confidence ≥ 0.65 → returns `Guide`; same call again → returns `Deny` (convergence guard)
    - Test Deny branch (different_problem): `pest_match=different_problem` → returns `Deny`
    - Test Deny branch (crop not grounded): `pest_match=matches_description`, `crop_grounded p_yes=0.4` → returns `Deny`
    - Test Deny branch (spray not requested): `pest_match=matches_description`, `crop_grounded p_yes=0.9`, `spray_requested p_yes=0.3` → returns `Deny`
    - Test Confirm branch: any confidence = 0.4 → returns `Confirm` regardless of other answers
    - Test `before_invocation` clears `_guided` set
    - Test log record is appended for every verdict
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

- [x] 4. Checkpoint — ensure tools and decision tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement the agent module (`agent/agent.py`)
  - Replace `NAME`, `SYSTEM_PROMPT`, and wiring to use `SprayGuard` instead of `OrderActionGuard`
  - Set `NAME = "Vayal Kaavalan"`
  - Write `SYSTEM_PROMPT` with: fictional-data disclaimer, language instruction (reply in English or Tanglish matching the farmer), "ALWAYS call `lookup_label` before `recommend_spray`", never name a product without a lookup, ask a follow-up if crop/pest unclear, never invent product names
  - Change `_session` to instantiate `SprayGuard` and import it from `.decision`; remove `EAGER_PROMPT` entirely (keep only the single non-eager system prompt)
  - Import `SprayGuard` from `.decision` and `TOOLS` from `.tools`; remove `OrderActionGuard` and old `TOOLS` imports
  - Keep `HackathonAgent.chat` signature identical: `(self, message, session_id="default", images=None) -> dict`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.6, 7.1, 7.2, 7.3, 8.1, 8.2_

- [x] 6. Write the evaluation dataset (`agent/eval_cases.jsonl`)
  - Replace the file entirely with 30+ cases in JSONL format
  - Every record has: `state` (exact three-section format matching the runtime state), `expected` (dict with `crop_grounded`, `pest_match`, `spray_requested`), `split` ("tune" or "test"), optional `notes`
  - Use products from `labels.json`; use `render_messages`-style conversation text in the `--- CONVERSATION ---` section
  - Include at minimum: 5 Proceed cases (all three pass), 5 Guide/too_vague cases, 4 Deny/different_problem cases, 4 Deny/crop-not-grounded cases, 3 Deny/spray-not-requested cases, 3 Confirm/low-confidence cases (note "low_confidence" in `notes`)
  - Include all 9 mandatory hard near-miss cases from the design (Tanglish clear crop+pest, English vague symptom, neighbour's crop, two crops one sentence, "leaves yellow" no crop, wrong product for pest, clear specific symptom correct crop, Tanglish low-confidence, farmer asks "why")
  - Split ~15 tune / ~15 test; at least 14 in each split
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 4.3_

- [x] 7. Write the 4-turn demo script (`agent/demo_script.yaml`)
  - Replace the file with a new `demo_script.yaml` for Vayal Kaavalan
  - Define `name`, `pitch`, `features`, `intro` fields for the agent
  - Define exactly four `turns` in order: (1) Tanglish paddy blast message → `expected_verdict: proceed`; (2) English vague tomato message → `expected_verdict: guide`; (3) Tanglish wrong product for pest → `expected_verdict: deny`; (4) Very ambiguous message, low confidence → `expected_verdict: confirm`
  - Each turn has `id`, `label`, `message`, `expected_verdict`, and `notes` fields matching the design spec
  - _Requirements: 13.1_

- [x] 8. Restyle the demo UI (`demo/static/index.html`)
  - [x] 8.1 Replace colour palette, typography, and global structure
    - Replace `:root` CSS variables with terracotta (`#C1440E`), turmeric (`#E8A217`), indigo (`#2D3A7C`), cream (`#F5EDD6`), charcoal (`#1C1005`)
    - Add Google Fonts link for `Playfair Display` (headings) and `Noto Sans Tamil` (body)
    - Set `background-color: var(--cream)` and add repeating SVG grain texture via `background-image: url("data:image/svg+xml,...")`
    - Add mobile-first CSS: all interactive elements `min-width: 44px; min-height: 44px`
    - _Requirements: 10.1, 10.2, 10.6, 12.1, 12.2_

  - [x] 8.2 Build the sunrise header with Tamil/English toggle
    - Replace `<header>` with sunrise gradient (`linear-gradient(135deg, var(--indigo) 0%, var(--terracotta) 55%, var(--turmeric) 100%)`) and `@keyframes sunrise` animation
    - Add title "🌾 Vayal Kaavalan" using `Playfair Display`
    - Add a Tamil/English toggle button that swaps `data-en`/`data-ta` attributes on all labelled elements without page reload; toggle also flips `<html lang>` between `"en"` and `"ta"`
    - _Requirements: 10.5, 12.3_

  - [x] 8.3 Add disclaimer banner and kolam border motifs
    - Add a permanent disclaimer `<div class="disclaimer" role="alert">` immediately below `<header>` with exact text: "⚠️ EXPERIMENTAL PROTOTYPE — Fictional synthetic data. Not agronomic advice. Confirm all sprays with a real agriculture officer."
    - Add kolam-inspired SVG diamond+dot border motifs as `border-image` or inline `<svg>` on `.card` panels and chat bubbles
    - _Requirements: 8.3, 10.2_

  - [x] 8.4 Restyle chat bubbles as wall-sign cards
    - `.msg-farmer`: `align-self: flex-end`, terracotta background, cream text, `border-radius: 18px 18px 4px 18px`, `border: 2px solid #a33a0b`, `box-shadow: 3px 3px 0 rgba(0,0,0,0.15)`
    - `.msg-agent`: `align-self: flex-start`, indigo background, cream text, `border-radius: 18px 18px 18px 4px`, `border: 2px solid #1f2a5e`, matching shadow
    - Update the JS `add()` function to use these new class names
    - _Requirements: 10.7_

  - [x] 8.5 Build the Field Panel with furrow rows and threshold line
    - Replace the right-hand "Strands Decider 2B decisions" panel with a "Field Panel" (`data-en="Field Panel" data-ta="வயல் பலகை"`)
    - Add three furrow row `<div>`s, one per question (`crop_grounded`, `pest_match`, `spray_requested`), each containing: a question label, a seedling SVG whose height scales with `confidence` (0→flat, 1→full), and a dotted threshold line at 65%
    - When `confidence < 0.65` add `.wilted` class to the seedling (drooping leaves, muted colour via CSS filter)
    - The `pest_match` row label also shows the option label (`matches_description` / `different_problem` / `too_vague`)
    - Update `decision()` JS function to populate furrow rows instead of the old bar-chart when a SprayGuard record arrives (detected by presence of `pest_match` key)
    - Animate confidence updates with `transition: height 0.4s ease`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.6_

  - [x] 8.6 Add Field Gate verdict SVG and scarecrow mascot SVG
    - Add an inline SVG `<div class="field-gate">` below the furrow rows with four CSS classes: `.gate-proceed` (both panels open), `.gate-guide` (half-open, `?` sign), `.gate-deny` (shut, rope/latch), `.gate-confirm` (shut, officer's flag)
    - Add an inline hand-drawn SVG scarecrow with four pose classes: `.scarecrow-proceed` (arms raised), `.scarecrow-guide` (one arm up, question posture), `.scarecrow-deny` (arms crossed), `.scarecrow-confirm` (holding flag/scroll); default to neutral standing
    - Update `decision()` JS to set the correct gate class and scarecrow class when `verdict` is present; add `role="alert"` and `aria-label` for screen reader announcement
    - Add `transition: all 0.4s ease` on both SVG containers
    - _Requirements: 10.3, 10.4, 11.5, 12.2_

  - [x] 8.7 Add footer and verify API contract is unbroken
    - Add `<footer>` with exact text: "Built with the AWS User Group Madurai Strands Decider hackathon kit"
    - Verify the `/api/chat` POST call (body `{message, session_id, images}`) and `/api/info` GET call are unchanged in the JS
    - Verify the `decision()` JS function still handles all existing `rec` field shapes (numeric 0–1 values rendered as seedling heights; string fields shown in labels)
    - _Requirements: 10.8, 12.4, 12.5_

- [x] 9. Write label table integrity tests (`agent/tests/test_labels.py`)
  - Load `labels.json` via `decider_kit.data.load("labels")`
  - Assert all 8 required crops are present across `approved_crops` lists: paddy, groundnut, banana, sugarcane, tomato, cotton, brinjal, onion
  - Assert at least 2 entries have `restricted=True`
  - Assert every entry has exactly the five required fields (`product`, `approved_crops`, `phi_days`, `dose_per_acre`, `restricted`) with correct types
  - **Property 3: Round-trip integrity** — load `labels.json`, serialise back to JSON string, parse again, assert every entry's field values are identical to the original (validates Requirement 14.4)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 14.1, 14.4_

- [x] 10. Checkpoint — run full test suite
  - Ensure all tests pass (`pytest agent/tests/`), ask the user if questions arise.

- [x] 11. Run benchmark on test split and capture results
  - Run the bench command against the held-out test split:
    ```
    python -m decider_kit.bench --cases agent/eval_cases.jsonl --questions agent.decision:QUESTIONS --split test --out submission/bench
    ```
  - Verify the report includes: overall accuracy, per-question accuracy, latency p50/p95, cost per 1,000 decisions
  - Verify the report breaks down accuracy for Tanglish cases versus English-only cases (use the `notes` field tagging)
  - Save the output artefacts to `submission/bench/`
  - _Requirements: 9.5, 9.6_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All code must use only packages already in `requirements.txt`; no new dependencies
- `IS_KIT_EXAMPLE = False` in `decision.py` is required for submission check to pass
- The `/api/chat` contract in `demo/server.py` must not be modified
- Every `recommend_spray` response must include the fictional-data disclaimer (Requirement 8.1)
- Property tests validate universal correctness properties; unit tests validate specific examples and edge cases
