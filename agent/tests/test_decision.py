"""Property and unit tests for SprayGuard (agent/decision.py).

Because the installed strands-agents version does not ship strands.interventions,
we inject a lightweight mock of that module before importing agent.decision.
All tests mock Decider.ask to return controlled Decision objects.

All product data referenced here is FICTIONAL and SYNTHETIC — for demonstration only.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Bootstrap: inject strands.interventions mock before importing agent.decision
# ---------------------------------------------------------------------------

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _install_interventions_mock():
    """Install a lightweight strands.interventions stub if the real one is absent."""
    if "strands.interventions" in sys.modules:
        return  # already available (real or previously mocked)

    mock_interv = MagicMock()

    class Proceed:
        pass

    class Deny:
        def __init__(self, reason: str = ""):
            self.reason = reason

    class Guide:
        def __init__(self, feedback: str = ""):
            self.feedback = feedback

    class Confirm:
        def __init__(self, prompt: str = ""):
            self.prompt = prompt

    class InterventionHandler:
        pass

    mock_interv.Proceed = Proceed
    mock_interv.Deny = Deny
    mock_interv.Guide = Guide
    mock_interv.Confirm = Confirm
    mock_interv.InterventionHandler = InterventionHandler

    sys.modules["strands.interventions"] = mock_interv


_install_interventions_mock()

# Now safe to import
from agent.decision import SprayGuard, QUESTIONS, CONFIDENCE_THRESHOLD  # noqa: E402
from strands.interventions import Confirm, Deny, Guide, Proceed  # noqa: E402

# ---------------------------------------------------------------------------
# Helper: build controlled mock answers for Decider.ask
# ---------------------------------------------------------------------------


def make_answers(
    crop_grounded_p_yes: float,
    crop_grounded_conf: float,
    pest_match_label: str,
    pest_match_conf: float,
    spray_requested_p_yes: float,
    spray_requested_conf: float,
) -> dict:
    """Return a fake Decider.ask answers dict with controlled values."""
    cg = MagicMock()
    cg.p_yes = crop_grounded_p_yes
    cg.confidence = crop_grounded_conf

    pm = MagicMock()
    pm.label = pest_match_label
    pm.confidence = pest_match_conf

    sr = MagicMock()
    sr.p_yes = spray_requested_p_yes
    sr.confidence = spray_requested_conf

    return {"crop_grounded": cg, "pest_match": pm, "spray_requested": sr}


def make_event(product: str = "Nelvin-75WP", crop: str = "paddy", pest: str = "blast"):
    """Return a minimal mock ToolUseEvent for recommend_spray."""
    event = MagicMock()
    event.tool_use = {
        "name": "recommend_spray",
        "input": {"crop": crop, "pest": pest, "product": product},
    }
    event.agent = MagicMock()
    event.agent.messages = []
    return event


def _make_guard_with_mock_decider():
    """Return a (SprayGuard, mock_decider) pair ready for testing."""
    mock_decider = MagicMock()
    mock_decider.last_latency_ms = 0.0
    guard = SprayGuard(mock_decider)
    return guard, mock_decider


# ---------------------------------------------------------------------------
# Property 1: Single Decider call per non-convergence interception
# **Validates: Requirements 2.1**
# ---------------------------------------------------------------------------


def test_property1_single_decider_call_per_invocation():
    """For every non-retried before_tool_call invocation, decider.ask is called exactly once.

    We run before_tool_call for three different tool events and assert that ask is called
    once per event (three total after three calls).

    Validates: Requirements 2.1
    """
    guard, mock_decider = _make_guard_with_mock_decider()

    # Use "proceed" answers so there is no state change that might affect subsequent calls
    proceed_answers = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.9)
    mock_decider.ask.return_value = proceed_answers

    events = [
        make_event(product="Nelvin-75WP", crop="paddy", pest="blast"),
        make_event(product="Nelvin-75WP", crop="tomato", pest="blight"),
        make_event(product="Nelvin-75WP", crop="groundnut", pest="leaf_spot"),
    ]

    for i, event in enumerate(events):
        guard.before_tool_call(event)
        # After each call, ask should have been called exactly i+1 times total
        assert mock_decider.ask.call_count == i + 1, (
            f"After {i + 1} before_tool_call invocations, expected ask.call_count={i + 1}, "
            f"got {mock_decider.ask.call_count}"
        )


# ---------------------------------------------------------------------------
# Property 2: Three questions in every ask call
# **Validates: Requirements 2.2, 3.4**
# ---------------------------------------------------------------------------


def test_property2_three_questions_in_every_ask_call():
    """The questions dict passed to decider.ask always has exactly the keys
    crop_grounded, pest_match, spray_requested.

    Validates: Requirements 2.2, 3.4
    """
    guard, mock_decider = _make_guard_with_mock_decider()

    proceed_answers = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.9)
    mock_decider.ask.return_value = proceed_answers

    event = make_event()
    guard.before_tool_call(event)

    assert mock_decider.ask.call_count == 1
    # ask(state, questions) → second positional arg is questions
    _, call_args, call_kwargs = mock_decider.ask.mock_calls[0]
    # call_args is a tuple; positional args are at index 0, 1...
    pos_args = call_args
    # questions is either in positional args[1] or keyword arg "questions"
    if len(pos_args) >= 2:
        questions_passed = pos_args[1]
    else:
        questions_passed = call_kwargs.get("questions")

    expected_keys = {"crop_grounded", "pest_match", "spray_requested"}
    assert set(questions_passed.keys()) == expected_keys, (
        f"Expected question keys {expected_keys}, got {set(questions_passed.keys())}"
    )


# ---------------------------------------------------------------------------
# Unit tests — verdict branches
# ---------------------------------------------------------------------------


def test_proceed_branch_all_conditions_pass():
    """All confidences ≥ 0.65, pest_match=matches_description, crop_grounded p_yes=0.9,
    spray_requested p_yes=0.9 → returns Proceed."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Proceed), f"Expected Proceed, got {type(result).__name__}"


def test_guide_branch_too_vague_first_call():
    """pest_match=too_vague, all confidences ≥ 0.65 → returns Guide on first call."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "too_vague", 0.9, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Guide), f"Expected Guide, got {type(result).__name__}"


def test_guide_branch_too_vague_second_call_returns_deny():
    """pest_match=too_vague on first call → Guide; identical call again → Deny (convergence guard)."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "too_vague", 0.9, 0.9, 0.9)

    event = make_event()  # same event object (same args → same sig)

    first = guard.before_tool_call(event)
    assert isinstance(first, Guide), f"First call expected Guide, got {type(first).__name__}"

    # Second call with identical args — convergence guard fires (no decider call this time)
    second = guard.before_tool_call(event)
    assert isinstance(second, Deny), f"Second call expected Deny, got {type(second).__name__}"


def test_deny_branch_different_problem():
    """pest_match=different_problem → returns Deny."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "different_problem", 0.9, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Deny), f"Expected Deny, got {type(result).__name__}"


def test_deny_branch_crop_not_grounded():
    """pest_match=matches_description, crop_grounded p_yes=0.4 → returns Deny."""
    guard, mock_decider = _make_guard_with_mock_decider()
    # crop_grounded p_yes=0.4, but confidence is still ≥ 0.65 (confidence = max(p, 1-p) = 0.6 for p=0.4)
    # We set conf=0.7 so it doesn't trigger the Confirm branch
    mock_decider.ask.return_value = make_answers(0.4, 0.7, "matches_description", 0.9, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Deny), f"Expected Deny (crop not grounded), got {type(result).__name__}"


def test_deny_branch_spray_not_requested():
    """pest_match=matches_description, crop_grounded p_yes=0.9, spray_requested p_yes=0.3 → returns Deny."""
    guard, mock_decider = _make_guard_with_mock_decider()
    # spray_requested p_yes=0.3, confidence=0.7 so Confirm doesn't fire
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.9, 0.3, 0.7)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Deny), f"Expected Deny (spray not requested), got {type(result).__name__}"


def test_confirm_branch_low_confidence_crop_grounded():
    """crop_grounded confidence=0.4 (below 0.65) → returns Confirm regardless of other answers."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.4, "matches_description", 0.9, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Confirm), f"Expected Confirm (low confidence), got {type(result).__name__}"


def test_confirm_branch_low_confidence_pest_match():
    """pest_match confidence=0.4 (below 0.65) → returns Confirm."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.4, 0.9, 0.9)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Confirm), f"Expected Confirm (low pest_match confidence), got {type(result).__name__}"


def test_confirm_branch_low_confidence_spray_requested():
    """spray_requested confidence=0.4 (below 0.65) → returns Confirm regardless of other answers."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.4)

    result = guard.before_tool_call(make_event())

    assert isinstance(result, Confirm), f"Expected Confirm (low spray_requested confidence), got {type(result).__name__}"


# ---------------------------------------------------------------------------
# Unit test — non-recommend_spray tool passes through
# ---------------------------------------------------------------------------


def test_non_guarded_tool_returns_proceed_without_calling_decider():
    """A tool other than recommend_spray returns Proceed without calling the Decider."""
    guard, mock_decider = _make_guard_with_mock_decider()

    event = MagicMock()
    event.tool_use = {"name": "lookup_label", "input": {"product": "Nelvin-75WP"}}

    result = guard.before_tool_call(event)

    assert isinstance(result, Proceed), f"Expected Proceed for non-guarded tool, got {type(result).__name__}"
    mock_decider.ask.assert_not_called()


# ---------------------------------------------------------------------------
# Unit test — before_invocation clears _guided set
# ---------------------------------------------------------------------------


def test_before_invocation_clears_guided_set():
    """before_invocation() clears self._guided so the next invocation starts fresh."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "too_vague", 0.9, 0.9, 0.9)

    event = make_event()

    # First call: Guide fires and adds sig to _guided
    first = guard.before_tool_call(event)
    assert isinstance(first, Guide)
    assert len(guard._guided) == 1, "Expected one entry in _guided after Guide"

    # Simulate a new farmer invocation — clears _guided
    guard.before_invocation(MagicMock())
    assert len(guard._guided) == 0, "_guided should be empty after before_invocation"

    # After clearing, the same call should Guide again (not Deny)
    second = guard.before_tool_call(event)
    assert isinstance(second, Guide), "After before_invocation clears _guided, same call should Guide again"


# ---------------------------------------------------------------------------
# Unit test — log record is appended for every verdict
# ---------------------------------------------------------------------------


def test_log_record_appended_for_proceed_verdict():
    """A log record is appended after a Proceed verdict."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.9)

    guard.before_tool_call(make_event())

    assert len(guard.log) == 1
    record = guard.log[0]
    assert record["verdict"] == "proceed"
    assert record["tool"] == "recommend_spray"


def test_log_record_appended_for_deny_verdict():
    """A log record is appended after a Deny verdict (different_problem)."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "different_problem", 0.9, 0.9, 0.9)

    guard.before_tool_call(make_event())

    assert len(guard.log) == 1
    assert guard.log[0]["verdict"] == "deny"


def test_log_record_appended_for_guide_verdict():
    """A log record is appended after a Guide verdict."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "too_vague", 0.9, 0.9, 0.9)

    guard.before_tool_call(make_event())

    assert len(guard.log) == 1
    assert guard.log[0]["verdict"] == "guide"


def test_log_record_appended_for_confirm_verdict():
    """A log record is appended after a Confirm verdict (low confidence)."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.4, "matches_description", 0.9, 0.9, 0.9)

    guard.before_tool_call(make_event())

    assert len(guard.log) == 1
    assert guard.log[0]["verdict"] == "confirm"


def test_log_record_appended_for_convergence_deny():
    """A log record is appended when the convergence guard fires (Deny on retry)."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "too_vague", 0.9, 0.9, 0.9)

    event = make_event()
    guard.before_tool_call(event)  # Guide → adds to _guided
    guard.before_tool_call(event)  # Convergence Deny

    assert len(guard.log) == 2
    assert guard.log[1]["verdict"] == "deny"


def test_log_record_has_required_fields():
    """Every log record contains all required fields."""
    guard, mock_decider = _make_guard_with_mock_decider()
    mock_decider.ask.return_value = make_answers(0.9, 0.9, "matches_description", 0.9, 0.9, 0.9)

    guard.before_tool_call(make_event())

    record = guard.log[0]
    required_fields = {
        "pattern", "tool", "args",
        "crop_grounded", "pest_match", "pest_match_confidence",
        "spray_requested", "verdict", "decider_ms",
    }
    missing = required_fields - set(record.keys())
    assert not missing, f"Log record missing fields: {missing}"
