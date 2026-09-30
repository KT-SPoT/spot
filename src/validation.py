"""Non-mutating ScoutResult envelope checks; not evidence-quality evaluation."""

import argparse
import json
from pathlib import Path


def validate_scout_result(result, *, expected_module, request_id) -> list[str]:
    """Return field-level errors. Extensions are allowed; no coercion is performed.

    Timestamp nulls follow the existing contracts.py scaffold. Source metadata
    completeness, date semantics and research quality are outside this validator.
    """
    if not isinstance(result, dict):
        return ["result: expected object"]
    errors = []
    types = {
        "schema_version": str, "request_id": str, "module": str, "status": str,
        "started_at": (str, type(None)), "finished_at": (str, type(None)),
        "query_context": dict, "summary": str, "insights": list,
        "sources": list, "warnings": list, "errors": list,
    }
    for field, kind in types.items():
        if field not in result:
            errors.append(f"{field}: missing required field")
        elif not isinstance(result[field], kind):
            errors.append(f"{field}: invalid type")
    for field, allowed in {
        "schema_version": ("0.1",), "module": ("quant", "local", "trend"),
        "status": ("success", "partial", "failed"),
    }.items():
        if field in result and result[field] not in allowed:
            errors.append(f"{field}: unsupported value")
    for field, expected in (("module", expected_module), ("request_id", request_id)):
        if field in result and result[field] != expected:
            errors.append(f"{field}: does not match expected value")
    for field in ("insights", "sources"):
        if isinstance(result.get(field), list):
            for index, item in enumerate(result[field]):
                if not isinstance(item, dict):
                    errors.append(f"{field}[{index}]: expected object")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--module", required=True, choices=("quant", "local", "trend"))
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    try:
        result = json.loads(args.result.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    errors = validate_scout_result(result, expected_module=args.module, request_id=args.request_id)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
