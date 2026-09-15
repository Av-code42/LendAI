"""
Turns a raw Textract AnalyzeDocument response into the fields this app
actually cares about: an overall confidence, a plausible name, and (for
salary slips) an income figure to cross-check against what the applicant
declared.

Textract's FORMS feature returns generic key/value pairs from whatever
labels it can find on the page -- it has no idea what a "PAN card" or
"salary slip" is. So this is necessarily heuristic (fuzzy key-name
matching, first-match-wins), not a guaranteed-correct parse of arbitrary
real-world document layouts. It's also why AWS's specialized identity
document API (AnalyzeID) isn't used here at all: it only supports US
driver's licenses and passports, not Indian PAN cards, so a PAN card gets
generic FORMS+raw-text regex extraction like everything else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

NAME_KEY_HINTS = ["employee name", "customer name", "account holder", "name of", "name"]
INCOME_KEY_HINTS = ["net pay", "net salary", "take home", "gross salary", "gross pay", "total earnings"]

_NUMBER_PATTERN = re.compile(r"[\d][\d,]*\.?\d*")


@dataclass
class ExtractionResult:
    confidence: float  # 0-1, averaged over detected text blocks
    extracted_name: str | None = None
    extracted_income: float | None = None
    raw_key_values: dict[str, str] = field(default_factory=dict)


def _blocks_by_id(blocks: list[dict]) -> dict[str, dict]:
    return {b["Id"]: b for b in blocks}


def _block_text(block: dict, by_id: dict[str, dict]) -> str:
    words = []
    for rel in block.get("Relationships", []):
        if rel["Type"] != "CHILD":
            continue
        for child_id in rel["Ids"]:
            child = by_id.get(child_id)
            if child and child.get("BlockType") in ("WORD", "SELECTION_ELEMENT"):
                if child["BlockType"] == "WORD":
                    words.append(child.get("Text", ""))
                elif child.get("SelectionStatus") == "SELECTED":
                    words.append("[selected]")
    return " ".join(words).strip()


def _extract_key_value_pairs(blocks: list[dict]) -> dict[str, str]:
    by_id = _blocks_by_id(blocks)
    pairs: dict[str, str] = {}
    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue
        key_text = _block_text(block, by_id)
        value_text = ""
        for rel in block.get("Relationships", []):
            if rel["Type"] != "VALUE":
                continue
            for value_id in rel["Ids"]:
                value_block = by_id.get(value_id)
                if value_block:
                    value_text = _block_text(value_block, by_id)
        if key_text:
            pairs[key_text.strip().lower()] = value_text.strip()
    return pairs


def _find_by_key_hint(pairs: dict[str, str], hints: list[str]) -> str | None:
    for hint in hints:
        for key, value in pairs.items():
            if hint in key and value:
                return value
    return None


def _parse_amount(text: str) -> float | None:
    match = _NUMBER_PATTERN.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def _average_confidence(blocks: list[dict]) -> float:
    scores = [b["Confidence"] for b in blocks if b.get("BlockType") == "LINE" and "Confidence" in b]
    if not scores:
        return 0.0
    return (sum(scores) / len(scores)) / 100.0


def extract(document_type: str, textract_response: dict) -> ExtractionResult:
    blocks = textract_response.get("Blocks", [])
    confidence = _average_confidence(blocks)
    pairs = _extract_key_value_pairs(blocks)
    raw_text = "\n".join(b.get("Text", "") for b in blocks if b.get("BlockType") == "LINE")

    name = _find_by_key_hint(pairs, NAME_KEY_HINTS)
    income = None

    if document_type == "PAN":
        pan_match = PAN_PATTERN.search(raw_text.replace(" ", ""))
        if pan_match:
            pairs.setdefault("pan_number", pan_match.group())

    elif document_type == "SALARY_SLIP":
        income_text = _find_by_key_hint(pairs, INCOME_KEY_HINTS)
        if income_text:
            income = _parse_amount(income_text)

    # BANK_STATEMENT: name extraction via the generic hints above is all
    # this MVP attempts -- transaction-table parsing is future work.

    return ExtractionResult(
        confidence=confidence,
        extracted_name=name,
        extracted_income=income,
        raw_key_values=pairs,
    )


def names_match(declared_name: str, extracted_name: str | None) -> bool | None:
    """None means "couldn't tell" (nothing extracted) -- distinct from a
    confirmed mismatch, and callers should treat it as such (not as a
    pass or a fail)."""
    if not extracted_name:
        return None
    normalize = lambda s: set(re.sub(r"[^a-z\s]", "", s.lower()).split())  # noqa: E731
    declared_tokens = normalize(declared_name)
    extracted_tokens = normalize(extracted_name)
    if not declared_tokens or not extracted_tokens:
        return None
    overlap = declared_tokens & extracted_tokens
    # Most of the shorter name's tokens should appear in the other --
    # tolerant of a missing middle name, OCR-dropped initial, etc.
    smaller = min(len(declared_tokens), len(extracted_tokens))
    return len(overlap) / smaller >= 0.5


def income_mismatch_ratio(declared_income: float, extracted_income: float | None) -> float | None:
    if extracted_income is None or declared_income <= 0:
        return None
    return abs(extracted_income - declared_income) / declared_income
