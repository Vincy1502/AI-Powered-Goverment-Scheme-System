"""Conservative structured eligibility assessment.

Only explicit structured dataset fields are evaluated automatically. Natural-language
criteria/exclusions remain manual-review items; absent values are unknown, never passes.
"""
from __future__ import annotations

import math
import re
from typing import Any

UNKNOWN = {"", "n/a", "na", "none", "null", "not specified", "not available", "unknown"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_text(v) for v in value if _text(v))
    value = str(value).strip()
    return "" if value.casefold() in UNKNOWN else re.sub(r"\s+", " ", value)


def _number(value: Any) -> float | None:
    if value is None or _text(value) == "":
        return None
    try:
        n = float(str(value).replace(",", "").replace("₹", "").strip())
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _tokens(value: Any) -> set[str]:
    text = _text(value).casefold()
    return {re.sub(r"[^a-z0-9]+", "", x) for x in re.split(r"[,|;/]+", text) if x.strip()}


def _gender(value: Any) -> str:
    v = _text(value).casefold()
    aliases = {"f": "female", "woman": "female", "women": "female", "m": "male", "man": "male", "men": "male"}
    return aliases.get(v, v)


def assess_eligibility(scheme: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failed: list[str] = []
    unknown: list[str] = []

    def check(name: str, passed: bool | None, detail: str, source_field: str) -> None:
        checks.append({"criterion": name, "status": "pass" if passed is True else "fail" if passed is False else "unknown",
                       "detail": detail, "source_field": source_field})
        if passed is False:
            failed.append(name)
        elif passed is None:
            unknown.append(name)

    # State: All India is a positive explicit scope; blank state is unknown.
    scheme_state = _text(scheme.get("state"))
    user_state = _text(profile.get("state"))
    if not scheme_state:
        check("state", None, "Scheme state scope is not captured in the structured data.", "state")
    elif scheme_state.casefold() in {"all india", "india", "central"}:
        check("state", True, "Scheme is marked as All India/central.", "state")
    elif not user_state:
        check("state", None, "Your state is missing.", "state")
    else:
        check("state", scheme_state.casefold() == user_state.casefold(),
              f"Scheme state: {scheme_state}; your state: {user_state}.", "state")

    for field, label, profile_field in (("min_age", "minimum age", "age"), ("max_age", "maximum age", "age")):
        rule = _number(scheme.get(field))
        user_value = _number(profile.get(profile_field))
        if rule is None:
            check(label, None, f"{field} is blank or malformed; no unrestricted assumption is made.", field)
        elif user_value is None:
            check(label, None, "Your age is missing or invalid.", field)
        else:
            passed = user_value >= rule if field == "min_age" else user_value <= rule
            check(label, passed, f"Your age {user_value:g}; scheme {label} {rule:g}.", field)

    income_limit = _number(scheme.get("max_income"))
    income = _number(profile.get("income"))
    if income_limit is None:
        check("maximum income", None, "Maximum income is blank or malformed in the dataset.", "max_income")
    elif income is None:
        check("maximum income", None, "Your annual income is missing or invalid.", "max_income")
    else:
        check("maximum income", income <= income_limit,
              f"Your annual income {income:g}; scheme maximum {income_limit:g}.", "max_income")

    allowed_gender = _gender(scheme.get("gender"))
    user_gender = _gender(profile.get("gender"))
    if not allowed_gender:
        check("gender", None, "Gender rule is not captured in the structured data.", "gender")
    elif allowed_gender in {"any", "all", "both", "male/female", "female/male"}:
        check("gender", True, "Dataset explicitly marks the scheme as open to all genders.", "gender")
    elif not user_gender:
        check("gender", None, "Your gender is missing.", "gender")
    else:
        allowed = {"male", "female"} if "/" in allowed_gender else {_gender(x) for x in _tokens(allowed_gender)}
        check("gender", user_gender in allowed,
              f"Scheme gender field: {allowed_gender}; your gender: {user_gender}.", "gender")

    for field, label, profile_field in (("target_categories", "target category", "category"),
                                        ("target_occupation", "target occupation", "occupation")):
        target = _text(scheme.get(field))
        user = _text(profile.get(profile_field))
        if not target:
            check(label, None, f"{field} is not captured in the structured data.", field)
        elif not user:
            check(label, None, f"Your {profile_field} is missing.", field)
        elif _tokens(target) & {"all", "any", "everyone"}:
            check(label, True, f"Dataset marks {field} as inclusive.", field)
        else:
            allowed = _tokens(target)
            selected = _tokens(user)
            check(label, bool(allowed & selected), f"Dataset target: {target}; your {profile_field}: {user}.", field)

    # A natural-language statement is never silently converted into a rule.
    manual_review = []
    if _text(scheme.get("eligibility_criteria")):
        manual_review.append({"field": "eligibility_criteria", "text": _text(scheme.get("eligibility_criteria")),
                              "reason": "Natural-language eligibility conditions require human/official-source review."})
    if _text(scheme.get("exclusions")):
        manual_review.append({"field": "exclusions", "text": _text(scheme.get("exclusions")),
                              "reason": "Exclusions are not safely machine-interpreted and must be reviewed manually."})

    provenance = scheme.get("eligibility_rule_provenance")
    verified_provenance = isinstance(provenance, dict) and provenance.get("verified") is True and bool(_text(provenance.get("source_url"))) and bool(_text(provenance.get("checked_at")))
    if failed:
        status = "not_eligible"
        summary = "At least one captured structured criterion conflicts with the supplied profile."
    elif unknown:
        status = "insufficient_information"
        summary = "One or more structured criteria or profile values are missing/unknown; missing data was not treated as a pass."
    elif manual_review:
        status = "potential_eligibility"
        summary = "Captured structured criteria passed, but natural-language rules/exclusions still require manual review."
    elif verified_provenance:
        status = "confirmed_eligible"
        summary = "All evaluated structured criteria passed and verified rule provenance is attached."
    else:
        status = "potential_eligibility"
        summary = "Structured checks passed, but verified official-rule provenance is absent; eligibility is not confirmed."

    return {"eligibility_status": status, "eligibility_summary": summary, "eligibility_checks": checks,
            "failed_criteria": failed, "unknown_criteria": unknown, "manual_review": manual_review,
            "rule_provenance": provenance if isinstance(provenance, dict) else None,
            "confirmed_eligibility_allowed": status == "confirmed_eligible"}
