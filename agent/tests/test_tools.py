"""Unit tests for agent.tools: lookup_label, recommend_spray, escalate_to_officer.

All product data referenced here is FICTIONAL and SYNTHETIC — for demonstration only.
"Nelvin-75WP" is used as the known product (it appears in labels.json).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `agent` and `decider_kit` are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from agent.tools import lookup_label, recommend_spray, escalate_to_officer

KNOWN_PRODUCT = "Nelvin-75WP"
UNKNOWN_PRODUCT = "NoSuchProduct-999XX"


# ---------------------------------------------------------------------------
# lookup_label
# ---------------------------------------------------------------------------

def test_lookup_label_known_product_returns_all_five_fields():
    """lookup_label with a known product returns a dict containing all five required fields."""
    result = lookup_label(KNOWN_PRODUCT)
    assert isinstance(result, dict)
    assert "product" in result
    assert "approved_crops" in result
    assert "phi_days" in result
    assert "dose_per_acre" in result
    assert "restricted" in result


def test_lookup_label_known_product_values():
    """lookup_label returns the correct values for Nelvin-75WP from labels.json."""
    result = lookup_label(KNOWN_PRODUCT)
    assert result["product"] == "Nelvin-75WP"
    assert "paddy" in result["approved_crops"]
    assert result["phi_days"] == 14
    assert result["dose_per_acre"] == "200g"
    assert result["restricted"] is False


def test_lookup_label_case_insensitive():
    """lookup_label is case-insensitive for the product name."""
    result_lower = lookup_label(KNOWN_PRODUCT.lower())
    result_upper = lookup_label(KNOWN_PRODUCT.upper())
    assert result_lower["product"] == result_upper["product"] == "Nelvin-75WP"


def test_lookup_label_unknown_product_returns_error():
    """lookup_label with an unknown product returns {"error": "product not found"}."""
    result = lookup_label(UNKNOWN_PRODUCT)
    assert result == {"error": "product not found"}


# ---------------------------------------------------------------------------
# recommend_spray
# ---------------------------------------------------------------------------

def test_recommend_spray_known_product_has_disclaimer():
    """recommend_spray with a known product returns a dict that has a disclaimer containing 'FICTIONAL'."""
    result = recommend_spray(crop="paddy", pest="blast", product=KNOWN_PRODUCT)
    assert isinstance(result, dict)
    assert "disclaimer" in result
    assert "FICTIONAL" in result["disclaimer"]


def test_recommend_spray_known_product_has_all_expected_fields():
    """recommend_spray returns product, crop, pest, dose_per_acre, phi_days, restricted, disclaimer."""
    result = recommend_spray(crop="paddy", pest="blast", product=KNOWN_PRODUCT)
    for field in ("product", "crop", "pest", "dose_per_acre", "phi_days", "restricted", "disclaimer"):
        assert field in result, f"Missing field: {field}"


def test_recommend_spray_unknown_product_returns_error():
    """recommend_spray with an unknown product returns an error dict."""
    result = recommend_spray(crop="paddy", pest="blast", product=UNKNOWN_PRODUCT)
    assert "error" in result


# ---------------------------------------------------------------------------
# escalate_to_officer
# ---------------------------------------------------------------------------

def test_escalate_to_officer_returns_escalated_true():
    """escalate_to_officer returns a dict with escalated=True."""
    result = escalate_to_officer(summary="Farmer unsure about product choice for tomato.")
    assert result["escalated"] is True


def test_escalate_to_officer_summary_matches_input():
    """escalate_to_officer echoes back the exact summary string provided."""
    summary = "Unclear pest description; needs officer review."
    result = escalate_to_officer(summary=summary)
    assert result["summary"] == summary


def test_escalate_to_officer_has_message_field():
    """escalate_to_officer returns a dict that also contains a 'message' field."""
    result = escalate_to_officer(summary="Test case.")
    assert "message" in result
    assert isinstance(result["message"], str)
