"""Vayal Kaavalan tools: label lookup, spray recommendation, and officer escalation.

All product data is FICTIONAL and SYNTHETIC — for demonstration only.
Not real agronomic advice. All product names are invented.
"""

from __future__ import annotations

from strands import tool
from decider_kit.data import load as _load_data

# ---------------------------------------------------------------------------
# LABEL_TABLE: built at import time from agent/data/labels.json
# Keyed by lowercase product name for O(1) lookup.
# Entries whose product name starts with "_" (e.g. "_disclaimer") are skipped.
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {"product", "approved_crops", "phi_days", "dose_per_acre", "restricted"}

_rows = _load_data("labels")

LABEL_TABLE: dict[str, dict] = {}
for _r in _rows:
    # Skip metadata / comment entries
    if _r.get("product", "").startswith("_"):
        continue
    # Validate required fields
    _missing = _REQUIRED_FIELDS - set(_r.keys())
    if _missing:
        raise ValueError(
            f"labels.json entry is missing required fields {sorted(_missing)}: {_r!r}"
        )
    LABEL_TABLE[_r["product"].lower()] = _r


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@tool
def lookup_label(product: str) -> dict:
    """Look up a fictional product label: approved crops, PHI days, dose per acre, restricted flag."""
    entry = LABEL_TABLE.get(product.strip().lower())
    if not entry:
        return {"error": "product not found"}
    return {
        "product":        entry["product"],
        "approved_crops": entry["approved_crops"],
        "phi_days":       entry["phi_days"],
        "dose_per_acre":  entry["dose_per_acre"],
        "restricted":     entry["restricted"],
    }


@tool
def recommend_spray(crop: str, pest: str, product: str) -> dict:
    """Recommend a fictional spray product for a crop pest (SprayGuard intercepts before this runs)."""
    entry = LABEL_TABLE.get(product.strip().lower())
    if not entry:
        return {"error": "product not found in label table"}
    return {
        "product":       entry["product"],
        "crop":          crop,
        "pest":          pest,
        "dose_per_acre": entry["dose_per_acre"],
        "phi_days":      entry["phi_days"],
        "restricted":    entry["restricted"],
        "disclaimer": (
            "FICTIONAL DATA — This recommendation is based on synthetic, invented product data "
            "and is NOT real agronomic advice. Do NOT act on this without confirmation from a "
            "qualified agriculture officer."
        ),
    }


@tool
def escalate_to_officer(summary: str) -> dict:
    """Escalate a low-confidence case to a human agriculture officer for review."""
    return {
        "escalated": True,
        "message": (
            "This case has been flagged for review by an agriculture officer. "
            "The farmer should wait for the officer's confirmation before spraying."
        ),
        "summary": summary,
    }


TOOLS = [lookup_label, recommend_spray, escalate_to_officer]
