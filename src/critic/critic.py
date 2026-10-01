"""Deterministic Critic and bounded retry policy; meaning remains human review."""

from typing import Any
from src.critic.rules import evaluate_rules


def run_critic(research_bundle: dict[str, Any], *, retry_count=0, max_retry_rounds=1):
    """Real deterministic validation, with narrowly bounded transient retries.

    Mechanical validation cannot approve meaning or factual truth. Quotas,
    credentials, empty searches and unknown failures never trigger extra calls.
    """
    report = evaluate_rules(research_bundle)
    if type(max_retry_rounds) is not int or max_retry_rounds not in (0, 1) or type(retry_count) is not int or retry_count < 0:
        raise ValueError("Invalid retry limits")
    findings = report["findings"]
    excluded = sorted({finding["module"] for finding in findings
                       if finding["level"] == "needs_fix" and finding["module"]})
    if any(finding["level"] == "needs_fix" and not finding["module"] for finding in findings):
        excluded = ["quant", "local", "trend"]
    retries = []
    exhausted = []
    results = research_bundle.get("results", {}) if isinstance(research_bundle, dict) else {}
    if not isinstance(results, dict):
        results = {}
    for module, result in results.items():
        if module not in ("quant", "local", "trend") or module in excluded:
            continue
        errors = result.get("errors", []) if isinstance(result, dict) else []
        warning_codes = [warning.get("code", "") if isinstance(warning, dict) else warning
                         for warning in result.get("warnings", [])] if isinstance(result, dict) else []
        if any(isinstance(code, str) and code.startswith("MOCK_") for code in warning_codes):
            continue
        if not errors:
            continue
        transient = all(isinstance(error, dict) and (
            error.get("code") == "PROVIDER_UNAVAILABLE" or
            (error.get("code") == "PROVIDER_HTTP_ERROR" and error.get("http_status") in (500, 502, 503, 504)))
                        for error in errors)
        if not transient:
            continue
        if retry_count < max_retry_rounds:
            retries.append({"module": module, "reason": "TRANSIENT_PROVIDER_FAILURE",
                            "attempt": retry_count + 1})
        else:
            exhausted.append(module)
    usable = any(module not in excluded and isinstance(result, dict)
                 and result.get("status") != "failed"
                 and "MOCK_ONLY_NOT_REAL_DATA" not in result.get("warnings", [])
                 and result.get("insights") and result.get("sources")
                 for module, result in results.items() if module in ("quant", "local", "trend"))
    warnings = ["SEMANTIC_AND_FACTUAL_REVIEW_REQUIRED"]
    if excluded:
        warnings.append("INVALID_MODULE_EVIDENCE_EXCLUDED")
    if exhausted:
        warnings.append("TRANSIENT_RETRY_LIMIT_REACHED")
    return {"schema_version": "0.1", "request_id": research_bundle.get("request_id", "unknown") if isinstance(research_bundle, dict) else "unknown",
            "status": "retry_required" if retries else ("manual_review" if usable else "failed"),
            "checks": {"rules": report, "excluded_modules": excluded,
                       "semantic_review": {"performed": False, "status": "manual_review"},
                       "retry_policy": {"max_rounds": max_retry_rounds, "rounds_used": retry_count,
                                        "exhausted_modules": exhausted}},
            "retry": retries, "warnings": warnings}


def mock_critic(research_bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "request_id": research_bundle.get("request_id", "unknown"),
        "status": "manual_review",
        "checks": {},
        "retry": [],
        "warnings": ["MOCK_CRITIC_NOT_FOR_QUALITY_EVALUATION"],
    }
