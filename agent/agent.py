"""The agent: an LLM does the talking (Amazon Bedrock by default), Strands Decider 2B makes the decision.

Vayal Kaavalan ("Field Guardian") is a Tamil-English agricultural advisory agent for smallholder
farmers in Tamil Nadu. The agent recommends fictional, label-backed spray products for crop pest
problems. Before any product name reaches the farmer, SprayGuard fires a single Strands Decider
call with three typed questions (crop grounded? symptom matches? spray requested?) and only lets
the recommendation proceed when all three pass. The interface below (`HackathonAgent.chat`) stays
the same as the kit contract, so the demo UI, the benchmark, the video and the AWS deployment keep
working unchanged.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Nel payir la kuzhai thandu karuppu aagudhu, blast maadiri. Nelvin-75WP podalama?")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import SprayGuard
from .tools import TOOLS

NAME = "Vayal Kaavalan"

SYSTEM_PROMPT = """You are Vayal Kaavalan, an agricultural advisory assistant for smallholder farmers in Tamil Nadu.
IMPORTANT: All product data in your label table is FICTIONAL and SYNTHETIC — for demonstration only.
Every recommendation you make MUST be confirmed by a real, qualified agriculture officer before any farmer acts on it.

How to behave:
- Reply in the same language the farmer uses: English or Tanglish (Tamil written in English letters).
- Use short, plain sentences. Avoid jargon.
- ALWAYS call lookup_label(product) before calling recommend_spray.
- If the farmer's message is too vague to identify the crop and pest clearly, ask a specific follow-up
  question about which part of the plant is affected, what colour it is, and whether there are spots, holes or a coating.
- Never name a product without having called lookup_label first.
- Never invent product names. Only use products returned by lookup_label.
- If SprayGuard denies a recommend_spray call, tell the farmer plainly why (use the reason) and do NOT name the product.
- If a case is escalated to an officer (Confirm), call escalate_to_officer with a one-paragraph English summary
  of the conversation, the proposed recommendation and the reason for low confidence, then tell the farmer, in their
  language, that the case has been sent to an agriculture officer and no spray should be used until the officer confirms.
"""


class HackathonAgent:
    """One Strands agent per session, with the SprayGuard decision pattern wired in."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None, eager: bool | None = None):
        import os

        self.decider = decider or Decider()
        # `eager` is kept for the kit contract (demos only). Vayal Kaavalan always follows the single
        # grounded system prompt — SprayGuard is what makes the on-camera decisions safe, so no eager
        # prompt is used.
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()  # LLM_PROVIDER in .env: bedrock, local, ugmdu
        self.sessions: dict[str, tuple[Agent, SprayGuard]] = {}

    def _session(self, session_id: str) -> tuple[Agent, SprayGuard]:
        if session_id not in self.sessions:
            guard = SprayGuard(self.decider)
            agent = Agent(model=agent_model(self.model_id), system_prompt=SYSTEM_PROMPT, tools=TOOLS,
                          interventions=[guard], callback_handler=None)
            self.sessions[session_id] = (agent, guard)
        return self.sessions[session_id]

    def chat(self, message: str, session_id: str = "default", images: list[Any] | None = None) -> dict[str, Any]:
        """`images` (optional): photos the user attached (paths, bytes or base64); the LLM sees them
        as Strands image blocks. A decision that looks at them passes the same list to Decider.ask."""
        agent, guard = self._session(session_id)
        before = len(guard.log)
        t0 = time.perf_counter()
        # the LLM sees the photos as image blocks; tools get them via decider_kit.llm.attached_images
        result = agent([*image_blocks(images), {"text": message}] if images else message,
                       invocation_state={"images": list(images or [])})
        reply = strip_thinking(str(result))  # drop Nova <thinking> / Qwen  blocks
        return {"reply": reply, "decisions": guard.log[before:], "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000), "agent": NAME, "eager": self.eager}


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    for msg in sys.argv[1:] or ["Nel payir la kuzhai thandu karuppu aagudhu, blast maadiri. Nelvin-75WP podalama?"]:
        print(json.dumps(a.chat(msg), indent=1))
