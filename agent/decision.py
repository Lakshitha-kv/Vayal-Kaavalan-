"""SprayGuard decision module for Vayal Kaavalan ("Field Guardian")  (#guardrails)

What it does
    Before the agricultural advisory agent calls `recommend_spray`, SprayGuard fires a single
    `Decider.ask` call carrying three typed questions:
    - Is the farmer's crop grounded (named or clearly implied)?
    - Does the symptom match the proposed pest?
    - Is the farmer actually asking for a spray recommendation?
    Only when all three conditions pass does the recommendation proceed. Otherwise the agent
    guides the farmer to describe symptoms better (Guide), refuses the call (Deny), or escalates
    to a human agriculture officer (Confirm) when the decider is uncertain.

Typed questions and options
    crop_grounded (noul), pest_match (choice: matches_description / different_problem / too_vague),
    spray_requested (noul); see QUESTIONS below.

Wiring
    `SprayGuard` is a Strands `InterventionHandler`; agent/agent.py passes it to the Agent:
        Agent(..., interventions=[SprayGuard(decider)])
    It only inspects `recommend_spray`; all other tools run untouched. A call already sent
    back with Guide is denied on retry (convergence guarantee).
"""

from __future__ import annotations

import json
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from decider_kit import Decider
from decider_kit.patterns.guardrails import render_messages

from .tools import lookup_label

IS_KIT_EXAMPLE = False  # submission check requires this to be False

PATTERN_TAG = "#guardrails"
FEATURE_TAG = "#strands-decider-2b"
GUARDED_TOOL = "recommend_spray"
CONFIDENCE_THRESHOLD = 0.65

QUESTIONS = {
    "crop_grounded": Decider.noul(
        "Did the farmer name or clearly imply a specific crop in their messages?",
        {
            "true": "the farmer explicitly named the crop (e.g. 'nel', 'paddy', 'tomato') "
                    "or the context makes it unambiguous (e.g. a paddy farmer asking about blast)",
            "false": "the crop is assumed, guessed from context, mentioned only as a neighbour's crop, "
                     "or not mentioned at all"
        }
    ),
    "pest_match": Decider.choice(
        "Does the symptom the farmer described match the pest proposed in the spray call?",
        {
            "matches_description": "the farmer described a specific observable symptom "
                                   "(e.g. brown neck rot, leaf curl, white fly clusters) "
                                   "that clearly matches the proposed pest",
            "different_problem":   "the farmer described a symptom that does NOT match the proposed pest "
                                   "(e.g. yellowing leaves but the call proposes a fungicide for blast)",
            "too_vague":           "the farmer's description is too general to confirm or deny "
                                   "(e.g. 'plant not good', 'leaves yellowing', 'some problem')"
        }
    ),
    "spray_requested": Decider.noul(
        "Is the farmer asking what to spray, or asking for a product recommendation?",
        {
            "true":  "the farmer asked what to spray, which product to use, or requested a recommendation "
                     "(e.g. 'enna spray pannanum?', 'what can I use?', 'suggest something')",
            "false": "the farmer described a problem, asked why it is happening, or asked about the pest — "
                     "without asking for a product recommendation"
        }
    ),
}


class SprayGuard(InterventionHandler):
    name = "spray-guard"

    def __init__(self, decider: Decider):
        self.decider = decider
        self.log: list[dict[str, Any]] = []
        self._guided: set[str] = set()  # convergence guard: calls already sent back with Guide

    def before_invocation(self, event, **kwargs) -> Proceed:
        self._guided.clear()  # new farmer message resets guided-call memory
        return Proceed()

    def _build_state(self, messages, args, lookup_result) -> str:
        return (
            f"--- CONVERSATION ---\n{render_messages(messages)}\n\n"
            f"--- PROPOSED SPRAY CALL ---\ntool: recommend_spray\narguments: {json.dumps(args)}\n\n"
            f"--- LABEL TABLE FACTS ---\n{json.dumps(lookup_result)}"
        )

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        if name != GUARDED_TOOL:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"recommend_spray:{json.dumps(args, sort_keys=True)}"

        # Convergence guard: retried guided call → Deny
        if sig in self._guided:
            self.log.append({
                "pattern": PATTERN_TAG,
                "tool": "recommend_spray",
                "args": args,
                "verdict": "deny",
                "reason": "convergence_guard",
                "decider_ms": 0,
            })
            return Deny(reason="Symptom description remains too vague after follow-up. Recommend the farmer visit an agriculture officer in person.")

        # Build state and call Decider exactly once
        lookup_result = lookup_label(args.get("product", ""))
        state = self._build_state(event.agent.messages, args, lookup_result)
        answers = self.decider.ask(state, QUESTIONS)
        decider_ms = round(self.decider.last_latency_ms or 0)

        cg = answers["crop_grounded"]
        pm = answers["pest_match"]
        sr = answers["spray_requested"]

        # Evaluate: confidence check first
        if any(a.confidence < CONFIDENCE_THRESHOLD for a in [cg, pm, sr]):
            verdict = "confirm"
            result = Confirm(prompt=f"Low-confidence case: {json.dumps(args)}. Escalate to officer?")
        elif pm.label == "too_vague":
            self._guided.add(sig)
            verdict = "guide"
            result = Guide(feedback="Ask the farmer to describe specific symptoms: which part of the plant is affected, what colour, any spots or coating?")
        elif pm.label == "different_problem":
            verdict = "deny"
            result = Deny(reason="The symptom described does not match the proposed pest. Do not recommend this product.")
        elif cg.p_yes < CONFIDENCE_THRESHOLD:
            verdict = "deny"
            result = Deny(reason="The farmer's crop was not clearly stated. Ask the farmer to confirm which crop is affected.")
        elif sr.p_yes < CONFIDENCE_THRESHOLD:
            verdict = "deny"
            result = Deny(reason="The farmer asked about the problem, not for a spray recommendation. Answer their question first.")
        else:
            verdict = "proceed"
            result = Proceed()

        # Append log record
        self.log.append({
            "pattern": PATTERN_TAG,
            "tool": "recommend_spray",
            "args": args,
            "crop_grounded": round(cg.p_yes or 0, 3),
            "pest_match": pm.label,
            "pest_match_confidence": round(pm.confidence, 3),
            "spray_requested": round(sr.p_yes or 0, 3),
            "verdict": verdict,
            "decider_ms": decider_ms,
        })
        return result
