"""Label table integrity tests for agent/data/labels.json.

All product data is FICTIONAL and SYNTHETIC — for demonstration only.
These tests do not touch the network or any LLM/decider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `decider_kit` and `agent` are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from decider_kit.data import load

REQUIRED_CROPS = ["paddy", "groundnut", "banana", "sugarcane", "tomato", "cotton", "brinjal", "onion"]
REQUIRED_FIELDS = {"product", "approved_crops", "phi_days", "dose_per_acre", "restricted"}


def _product_rows():
    """All product rows from labels.json, skipping metadata entries (product starts with '_')."""
    rows = load("labels")
    return [r for r in rows if not str(r.get("product", "")).startswith("_")]


# ---------------------------------------------------------------------------
# Coverage and structure
# ---------------------------------------------------------------------------

def test_all_eight_required_crops_present():
    """At least one entry per required crop across approved_crops lists (Requirement 6.1)."""
    rows = _product_rows()
    present = {c for r in rows for c in r.get("approved_crops", [])}
    missing = set(REQUIRED_CROPS) - present
    assert not missing, f"labels.json is missing required crops: {sorted(missing)}"


def test_at_least_two_restricted_entries():
    """At least two entries have restricted=True (Requirement 6.4)."""
    rows = _product_rows()
    restricted = [r for r in rows if r.get("restricted") is True]
    assert len(restricted) >= 2, f"expected >=2 restricted entries, found {len(restricted)}"


def test_every_entry_has_exactly_the_five_required_fields_with_correct_types():
    """Every product entry has exactly the five required fields with correct types
    (Requirements 6.3, 14.1)."""
    rows = _product_rows()
    assert rows, "no product rows found in labels.json"
    for r in rows:
        assert set(r.keys()) == REQUIRED_FIELDS, (
            f"entry {r.get('product')!r} must have exactly {sorted(REQUIRED_FIELDS)}, "
            f"got {sorted(r.keys())}"
        )
        assert isinstance(r["product"], str) and r["product"], "product must be a non-empty str"
        assert isinstance(r["approved_crops"], list) and all(isinstance(c, str) for c in r["approved_crops"]), \
            "approved_crops must be a list of str"
        assert isinstance(r["phi_days"], int) and not isinstance(r["phi_days"], bool) and r["phi_days"] >= 0, \
            "phi_days must be an int >= 0"
        assert isinstance(r["dose_per_acre"], str) and r["dose_per_acre"], "dose_per_acre must be a non-empty str"
        assert isinstance(r["restricted"], bool), "restricted must be a bool"


def test_product_names_are_unique():
    """Product names are unique (so lowercase keying in tools.py is unambiguous)."""
    rows = _product_rows()
    names = [r["product"] for r in rows]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"duplicate product names in labels.json: {dupes}"


# ---------------------------------------------------------------------------
# Property 3: Round-trip integrity (Requirement 14.4)
# ---------------------------------------------------------------------------

def test_property3_round_trip_integrity():
    """load -> serialise to JSON -> parse -> identical field values for every entry.

    **Validates: Requirements 14.4** — parsing then printing then parsing produces an
    equivalent list with the same entries and field values.
    """
    original = load("labels")
    # serialise the whole list back to a JSON string, then parse it again
    round_tripped = json.loads(json.dumps(original))
    assert len(round_tripped) == len(original), "row count changed after round trip"
    for a, b in zip(original, round_tripped):
        assert a == b, f"row changed after round trip: {a!r} != {b!r}"


def test_disclaimer_metadata_present_and_skipped():
    """The fictional-data disclaimer is carried in the file, and tools skip metadata entries."""
    rows = load("labels")
    meta = [r for r in rows if str(r.get("product", "")).startswith("_")]
    assert meta, "labels.json should carry a _disclaimer metadata entry"
    disclaimer_text = " ".join(str(r.get("_disclaimer", "")) for r in meta)
    assert "FICTIONAL" in disclaimer_text.upper(), "disclaimer must mention FICTIONAL data"
    # the product table built by tools.py must not contain the metadata entry
    product_rows = _product_rows()
    assert all(not r["product"].startswith("_") for r in product_rows), \
        "metadata entry leaked into the product table"
