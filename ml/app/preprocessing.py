"""Text and record preprocessing for GovScheme AI.

This module normalizes the uploaded scheme dataset without inferring eligibility.
Blank structured criteria remain unknown. JSON fields are parsed as data.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any

TEXT_FIELDS = (
    "scheme_name", "parent_scheme", "ministry", "department",
    "objectives", "benefits", "eligibility_criteria", "exclusions",
    "application_mode", "documents_required", "category_file",
    "target_categories", "target_occupation", "state",
)
JSON_FIELDS = ("benefits", "official_link")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        # Handles pandas/numpy NaN without importing pandas into this module.
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        return False


def normalize_text(value: Any) -> str:
    """Return normalized text; never convert missing values into eligibility claims."""
    if is_missing(value):
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return flatten_value(value)
    text = unicodedata.normalize("NFC", str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_json_field(value: Any) -> Any:
    """Parse JSON strings where possible; preserve non-JSON text unchanged."""
    if is_missing(value) or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def flatten_value(value: Any) -> str:
    """Flatten nested JSON/list values deterministically for searchable text."""
    if is_missing(value):
        return ""
    if isinstance(value, dict):
        pieces = []
        for key in sorted(value.keys(), key=lambda item: str(item).casefold()):
            val_text = flatten_value(value[key])
            if val_text:
                pieces.append(f"{normalize_text(key)} {val_text}")
        return " ".join(pieces)
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if isinstance(value, set):
            items = sorted(items, key=lambda item: str(item).casefold())
        return " ".join(part for part in (flatten_value(item) for item in items) if part)
    return normalize_text(value)


def normalize_application_mode(value: Any) -> str:
    text = normalize_text(value)
    key = re.sub(r"\s+", " ", text.casefold())
    variants = {
        "online": "Online",
        "offline": "Offline",
        "online/offline": "Online and Offline",
        "offline/online": "Online and Offline",
        "online and offline": "Online and Offline",
        "offline and online": "Online and Offline",
    }
    return variants.get(key, text)


def prepare_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a row and parse JSON fields while preserving raw eligibility gaps."""
    record = dict(raw)
    for field in record:
        if field in JSON_FIELDS:
            record[field] = parse_json_field(record[field])
        elif isinstance(record[field], str):
            record[field] = normalize_text(record[field])

    if "application_mode" in record:
        record["application_mode"] = normalize_application_mode(record["application_mode"])

    # Keep these values as None when blank. Do not infer 'no restriction'.
    for field in ("min_age", "max_age", "max_income"):
        value = record.get(field)
        if is_missing(value) or value == "":
            record[field] = None
        else:
            try:
                numeric = float(value)
                record[field] = int(numeric) if numeric.is_integer() else numeric
            except (TypeError, ValueError):
                # Preserve malformed source value for audit rather than guessing.
                record[field] = normalize_text(value)

    return record


def build_scheme_document(raw: dict[str, Any]) -> str:
    """Build searchable text from the actual dataset fields.

    Field labels are included to retain context; structured numeric eligibility
    fields are intentionally not turned into user-profile text.
    """
    record = prepare_record(raw)
    fields = (
        ("scheme", "scheme_name"),
        ("category", "category_file"),
        ("parent scheme", "parent_scheme"),
        ("ministry", "ministry"),
        ("department", "department"),
        ("objectives", "objectives"),
        ("benefits", "benefits"),
        ("eligibility criteria", "eligibility_criteria"),
        ("exclusions", "exclusions"),
        ("application mode", "application_mode"),
        ("documents required", "documents_required"),
        ("target categories", "target_categories"),
        ("target occupation", "target_occupation"),
        ("state", "state"),
    )
    chunks = []
    for label, field in fields:
        value = record.get(field)
        text = flatten_value(value)
        if text:
            chunks.append(f"{label}: {text}")
    return " ".join(chunks)


def build_profile_query(profile: dict[str, Any]) -> str:
    """Create a text query from qualitative profile fields only."""
    fields = (
        ("state", "state"),
        ("occupation", "occupation"),
        ("gender", "gender"),
        ("category", "category"),
        ("interests", "interests"),
        ("query", "query"),
    )
    chunks = []
    for label, field in fields:
        text = normalize_text(profile.get(field))
        if text:
            chunks.append(f"{label}: {text}")
    # Age and income are excluded from text similarity; they belong in rule checks.
    return " ".join(chunks)
