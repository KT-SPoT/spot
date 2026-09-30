"""Critic draft acceptance scenarios. All fixtures are synthetic, no API calls."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.critic.rules import evaluate_rules


ROOT = Path(__file__).resolve().parents[1]
PACK = json.loads((ROOT / "samples/critic/rule_cases.synthetic.json").read_text(encoding="utf-8"))
BASE = json.loads((ROOT / "samples/critic/research_bundle.synthetic.json").read_text(encoding="utf-8"))


class CriticRulesTest(unittest.TestCase):
    def test_synthetic_acceptance_cases_without_mutation(self):
        self.assertEqual(PACK["data_kind"], "synthetic")
        for case in PACK["cases"]:
            with self.subTest(case=case["id"], description=case["description"]):
                before = copy.deepcopy(case["bundle"])
                report = evaluate_rules(case["bundle"])
                expected = case["expected"]
                codes = {item["code"] for item in report["findings"]}
                self.assertEqual(report["rule_status"], expected["rule_status"], report)
                self.assertEqual(report["quality_status"], expected["quality_status"])
                self.assertTrue(set(expected["required_codes"]).issubset(codes), report)
                self.assertTrue(report["preview_only"])
                self.assertNotIn("retry", report)
                self.assertEqual(case["bundle"], before)

    def test_rules_pass_never_means_quality_approval(self):
        report = evaluate_rules(BASE)
        self.assertEqual(report["rule_status"], "pass")
        self.assertEqual(report["quality_status"], "manual_review")
        self.assertTrue(report["pending_checks"])
        self.assertNotIn("status", report)  # This is not CriticResult v0.1.

    def test_semantic_contradiction_is_explicitly_out_of_scope(self):
        case = next(case for case in PACK["cases"] if case["id"] == "C17")
        report = evaluate_rules(case["bundle"])
        self.assertEqual(report["rule_status"], "pass")
        self.assertEqual(report["quality_status"], "manual_review")
        self.assertIn("원문이 주장 내용을 실제로 뒷받침하는지 확인", report["pending_checks"])

    def test_needs_fix_takes_precedence_over_missing_dates(self):
        bundle = copy.deepcopy(BASE)
        bundle["results"]["local"]["sources"][0]["published_at"] = None
        bundle["results"]["trend"]["insights"][0]["source_ids"] = ["unknown"]
        report = evaluate_rules(bundle)
        self.assertEqual(report["rule_status"], "needs_fix")
        self.assertEqual({f["level"] for f in report["findings"]}, {"info", "manual_review", "needs_fix"})

    def test_period_boundaries_are_inclusive_and_zero_day_is_explicit(self):
        for lookback, publication in ((180, "2026-04-03"), (180, "2026-09-30"), (0, "2026-09-30")):
            with self.subTest(lookback=lookback, publication=publication):
                bundle = copy.deepcopy(BASE)
                bundle["request"]["research"]["lookback_days"] = lookback
                for module in ("local", "trend"):
                    for source in bundle["results"][module]["sources"]:
                        source["published_at"] = publication
                self.assertEqual(evaluate_rules(bundle)["rule_status"], "pass")

    def test_malformed_bundle_returns_a_report_instead_of_crashing(self):
        bundles = [None, [], "text", 42, {}, {**BASE, "request": None},
                   {**BASE, "results": []}, {**BASE, "module_status": None},
                   {**BASE, "request_id": ""}, {**BASE, "schema_version": "0.2"}]
        for bundle in bundles:
            with self.subTest(bundle_type=type(bundle).__name__):
                self.assertEqual(evaluate_rules(bundle)["rule_status"], "needs_fix")

    def test_malformed_research_period_is_not_silently_defaulted(self):
        for field, value in (("reference_date", None), ("reference_date", "2026-02-30"),
                             ("reference_date", "20260930"), ("reference_date", {}),
                             ("lookback_days", -1), ("lookback_days", True),
                             ("lookback_days", "180"), ("lookback_days", 10**20)):
            with self.subTest(field=field, value=value):
                bundle = copy.deepcopy(BASE)
                bundle["request"]["research"][field] = value
                report = evaluate_rules(bundle)
                self.assertEqual(report["rule_status"], "needs_fix")
                self.assertEqual(report["findings"][0]["code"], "INVALID_RESEARCH_PERIOD")

    def test_naive_datetime_is_not_treated_as_known_timezone(self):
        for field, value, code in (("published_at", "2026-09-01T12:00:00", "INVALID_PUBLICATION_DATE"),
                                   ("collected_at", "2026-09-01", "INVALID_COLLECTION_TIME")):
            with self.subTest(field=field):
                bundle = copy.deepcopy(BASE)
                bundle["results"]["local"]["sources"][0][field] = value
                self.assertIn(code, {f["code"] for f in evaluate_rules(bundle)["findings"]})

    def test_quant_api_unknown_publication_date_is_not_a_recency_failure(self):
        report = evaluate_rules(BASE)
        self.assertFalse(any(f["module"] == "quant" and f["rule_id"] == "R05" for f in report["findings"]))
        self.assertIsNone(report["counts"]["quant"]["recent_cited_sources"])

    def test_uncited_recent_source_does_not_rescue_old_evidence(self):
        bundle = copy.deepcopy(BASE)
        local = bundle["results"]["local"]
        recent = copy.deepcopy(local["sources"][0])
        recent.update(source_id="S-L-UNUSED", source_url="https://example.invalid/local/unused")
        local["sources"][0]["published_at"] = "2026-01-01"
        local["sources"].append(recent)
        report = evaluate_rules(bundle)
        self.assertEqual(report["counts"]["local"]["recent_cited_sources"], 0)
        self.assertIn("NO_RECENT_CITED_SOURCE", {f["code"] for f in report["findings"]})

    def test_source_reference_cannot_resolve_against_another_module(self):
        bundle = copy.deepcopy(BASE)
        bundle["results"]["local"]["insights"][0]["source_ids"] = ["S-T-001"]
        self.assertIn("BROKEN_SOURCE_REFERENCE", {f["code"] for f in evaluate_rules(bundle)["findings"]})

    def test_duplicate_pattern_case_cannot_inflate_evidence_count(self):
        bundle = copy.deepcopy(BASE)
        pattern = bundle["results"]["trend"]["patterns"][0]
        pattern["example_case_ids"] = ["T-001", "T-001"]
        report = evaluate_rules(bundle)
        codes = {f["code"] for f in report["findings"]}
        self.assertIn("PATTERN_COUNT_MISMATCH", codes)
        self.assertIn("PATTERN_NOT_REPEATED", codes)

    def test_malformed_module_extensions_have_explicit_findings(self):
        for field, value, code in (("patterns", [None], "INVALID_PATTERN"),
                                  ("patterns", {}, "PATTERN_UNAVAILABLE")):
            with self.subTest(value=value):
                bundle = copy.deepcopy(BASE)
                bundle["results"]["trend"][field] = value
                self.assertIn(code, {f["code"] for f in evaluate_rules(bundle)["findings"]})
        for value in (True, -1, "2", None):
            bundle = copy.deepcopy(BASE)
            bundle["results"]["trend"]["patterns"][0]["evidence_count"] = value
            self.assertIn("INVALID_PATTERN_COUNT", {f["code"] for f in evaluate_rules(bundle)["findings"]})

    def test_output_is_deterministic_and_pending_checks_do_not_share_state(self):
        first = evaluate_rules(BASE)
        second = evaluate_rules(BASE)
        self.assertEqual(first, second)
        first["pending_checks"].clear()
        self.assertTrue(evaluate_rules(BASE)["pending_checks"])

    def test_cli_exit_codes_and_quality_status(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "bundle.json"
            command = [sys.executable, "-m", "src.critic.rules", str(sample)]
            for content, code in ((json.dumps(BASE), 0), ("{}", 1), ("not json", 2)):
                with self.subTest(code=code):
                    sample.write_text(content, encoding="utf-8")
                    completed = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
                    self.assertEqual(completed.returncode, code, completed.stderr)
                    if code != 2:
                        self.assertEqual(json.loads(completed.stdout)["quality_status"], "manual_review")
            sample.unlink()
            self.assertEqual(subprocess.run(command, capture_output=True, cwd=ROOT).returncode, 2)
