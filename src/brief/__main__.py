"""Generate a JSON and Markdown Research Brief from an existing bundle."""

import argparse
import json
from pathlib import Path

from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--quant-evidence", type=Path, help="Optional SBIZ365 provider archive from this run")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8-sig"))
        evidence = json.loads(args.quant_evidence.read_text(encoding="utf-8-sig")) if args.quant_evidence else None
        brief = generate_brief(bundle, quant_evidence=evidence)
        markdown = render_markdown(brief)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "research_brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "RESEARCH_BRIEF.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"status": brief["status"], "source_count": brief["source_count"]}, ensure_ascii=False))
    return int(brief["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
