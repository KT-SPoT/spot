"""Brief safety/grounding scenarios, synthetic data, no live API calls."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.contracts import mock_scout_result


def fixture():
    request = {"schema_version": "0.1", "request_id": "brief-synthetic",
               "store": {"address": "합성 조사 주소"},
               "research": {"reference_date": "2026-09-30", "lookback_days": 180}}
    results = {}
    for module in ("quant", "local", "trend"):
        result = mock_scout_result(module, request["request_id"])
        result.update(status="success", warnings=[], summary="Synthetic evidence",
                      sources=[{"source_id": f"{module}-source", "source_name": "Synthetic source",
                                "source_url": f"https://example.com/{module}", "published_at": "2026-06-01",
                                "collected_at": "2026-10-01T00:00:00+09:00"}])
        results[module] = result
    results["quant"].update(metrics={"telecom_store_count": 2, "monthly_avg_sales_10k_krw": 500,
                                    "daily_avg_floating_population": 1000},
                             query_context={"lat": 35.0, "lng": 129.0, "radius_m": 1000,
                                            "upjong_cd": "G20802", "analysis_date": "20261001"})
    results["local"]["insights"] = [{"title": "미래 사업 선정", "evidence": "2029년 준공 목표",
                                     "source_ids": ["local-source"], "change_state": "selected_future_project",
                                     "published_at": "2026-06-01"}]
    results["trend"]["insights"] = [{"case_id": "case-1", "source_ids": ["trend-source"]}]
    results["trend"]["patterns"] = [{"pattern_id": "pattern-1", "name": "합성 체험 패턴",
                                     "description": "가상 사례", "evidence_count": 900,
                                     "example_case_ids": ["case-1", "case-1"],
                                     "example_source_ids": ["trend-source"]}]
    return {"schema_version": "0.1", "request_id": request["request_id"], "request": request,
            "results": results, "module_status": {name: "success" for name in results}}


class ResearchBriefTest(unittest.TestCase):
    def test_checked_but_uncorroborated_local_candidate_is_excluded(self):
        bundle = fixture()
        item = bundle["results"]["local"]["insights"][0]
        item.update(article_checked=True, verification_status="unconfirmed")
        brief = generate_brief(bundle)
        self.assertEqual(brief["local_changes"], [])
        self.assertIn("Local 원문", " ".join(brief["needs_manual_check"]))
        item["verification_status"] = "text_corroborated"
        self.assertEqual(len(generate_brief(bundle)["local_changes"]), 1)

    def test_grounded_draft_does_not_mutate_or_claim_approval(self):
        bundle = fixture()
        before = copy.deepcopy(bundle)
        brief = generate_brief(bundle, {"status": "pass", "warnings": []})
        self.assertEqual(bundle, before)
        self.assertEqual(brief["status"], "manual_review")
        self.assertEqual(brief["source_count"], 3)
        self.assertEqual(brief["local_changes"][0]["change_state"], "selected_future_project")
        self.assertEqual(brief["trend_patterns"][0]["evidence_count"], 1)
        self.assertTrue(all(card["sources"] for card in brief["unique_local_signals"]))
        self.assertIn("품질 최종 승인", " ".join(brief["needs_manual_check"]))
        brief["local_changes"][0]["sources"][0]["source_name"] = "changed"
        self.assertEqual(bundle, before)

    def test_missing_dates_and_demographics_are_not_invented(self):
        brief = generate_brief(fixture())
        self.assertTrue(all(card["reference_period"] is None for card in brief["unique_local_signals"]))
        self.assertNotIn("shares", json.dumps(brief))
        markdown = render_markdown(brief)
        self.assertIn("확인 필요", markdown)
        self.assertIn("성별·연령 비율을 확인할 원문 보조자료가 없습니다", markdown)

    def test_failed_and_mock_scouts_cannot_contribute_evidence(self):
        bundle = fixture()
        for result in bundle["results"].values():
            result["status"] = "failed"
        brief = generate_brief(bundle)
        self.assertEqual(brief["status"], "failed")
        self.assertIsNone(brief["overview"]["primary_customer_signal"])
        self.assertEqual(brief["source_count"], 0)
        bundle["results"]["quant"].update(status="success", warnings=["MOCK_ONLY_NOT_REAL_DATA"])
        self.assertEqual(generate_brief(bundle)["source_count"], 0)

    def test_zero_is_preserved_and_booleans_are_not_numbers(self):
        bundle = fixture()
        bundle["results"]["quant"]["metrics"] = {"telecom_store_count": 0, "household_count": True}
        facts = generate_brief(bundle)["unique_local_signals"]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["value"], 0)

    def test_unresolved_and_cross_module_sources_are_excluded(self):
        bundle = fixture()
        bundle["results"]["local"]["insights"][0]["source_ids"] = ["trend-source"]
        bundle["results"]["trend"]["patterns"][0]["example_case_ids"] = ["missing"]
        brief = generate_brief(bundle)
        self.assertEqual(brief["local_changes"], [])
        self.assertEqual(brief["trend_patterns"], [])
        self.assertEqual(brief["source_count"], 1)

    def test_contract_mismatch_cannot_leak_into_summary(self):
        bundle = fixture()
        bundle["results"]["quant"]["request_id"] = "other-request"
        self.assertEqual(generate_brief(bundle)["unique_local_signals"], [])
        bundle["request"]["request_id"] = "other-request"
        with self.assertRaises(ValueError):
            generate_brief(bundle)

    def test_source_count_deduplicates_urls_and_redacts_url_credentials(self):
        bundle = fixture()
        for result in bundle["results"].values():
            result["sources"][0]["source_url"] = "https://example.com/shared?certKey=synthetic-secret"
        brief = generate_brief(bundle)
        self.assertEqual(brief["source_count"], 1)
        self.assertNotIn("synthetic-secret", json.dumps(brief))

    def test_provider_archive_matches_location_and_metric_before_enrichment(self):
        bundle = fixture()
        archive = {"analysis": copy.deepcopy(bundle["results"]["quant"]["query_context"]),
                   "analy_date": "20261001", "reports": {"2": {"html": "synthetic"}}}
        section = {"derived_selected_area": {"latest_store_count": 2, "latest_period": "26.06"}}
        with patch("src.brief.quant_evidence.parse_industry_report", return_value=section):
            brief = generate_brief(bundle, quant_evidence=archive)
            self.assertEqual(brief["unique_local_signals"][0]["reference_period"], "2026년 06월")
            archive["analysis"]["lat"] = 36.0
            with self.assertRaisesRegex(ValueError, "좌표"):
                generate_brief(bundle, quant_evidence=archive)
            archive["analysis"]["lat"] = 35.0
            section["derived_selected_area"]["latest_store_count"] = 99
            with self.assertRaisesRegex(ValueError, "telecom_store_count"):
                generate_brief(bundle, quant_evidence=archive)

    def test_population_shares_keep_separate_populations_and_counts(self):
        bundle = fixture()
        archive = {"analysis": copy.deepcopy(bundle["results"]["quant"]["query_context"]),
                   "analy_date": "20261001", "reports": {"4": {"html": "synthetic"}}}
        section = {"derived_selected_area": {"latest_monthly_daily_flow_population": 1000},
                   "floating_population": {"monthly_daily_average": {"periods": ["26.06"]},
                                           "demographics": {"regions": {"선택 영역": {
                                               "male": {"count": 600, "share_pct": 60},
                                               "female": {"count": 400, "share_pct": 40},
                                               "40s": {"count": 200, "share_pct": 20}}}}}}
        with patch("src.brief.quant_evidence.parse_population_report", return_value=section):
            brief = generate_brief(bundle, quant_evidence=archive)
        card = next(card for card in brief["unique_local_signals"] if "shares" in card)
        self.assertEqual(card["population_kind"], "floating_population")
        self.assertEqual(card["shares"]["male"], {"count": 600, "share_pct": 60})
        self.assertIn("| 남성 | 600 | 60% |", render_markdown(brief))

    def test_cli_exports_without_provider_calls_and_marks_empty_output_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / "bundle.json"
            bundle = fixture()
            path.write_text(json.dumps(bundle), encoding="utf-8")
            completed = subprocess.run([sys.executable, "-m", "src.brief", str(path), "--output", str(folder / "out")], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((folder / "out/RESEARCH_BRIEF.md").exists())
            for result in bundle["results"].values():
                result["status"] = "failed"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            completed = subprocess.run([sys.executable, "-m", "src.brief", str(path), "--output", str(folder / "empty")], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 1)


if __name__ == "__main__":
    unittest.main()
