"""Synthetic cases only: status success does not imply real evidence."""

import copy
import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from src.contracts import mock_scout_result
from src.validation import validate_scout_result


class ValidationTest(unittest.TestCase):
    def check_result(self, result):
        return validate_scout_result(result, expected_module="quant", request_id="test-001")

    def test_all_modules_and_statuses(self):
        for module in ("quant", "local", "trend"):
            for status in ("success", "partial", "failed"):
                with self.subTest(module=module, status=status):
                    result = mock_scout_result(module, "test-001")
                    result["status"] = status
                    self.assertEqual(validate_scout_result(
                        result, expected_module=module, request_id="test-001"), [])

    def test_each_required_field(self):
        base = mock_scout_result("quant", "test-001")
        for field in base:
            with self.subTest(field=field):
                result = copy.deepcopy(base)
                del result[field]
                self.assertIn(f"{field}: missing required field", self.check_result(result))

    def test_each_field_wrong_type(self):
        base = mock_scout_result("quant", "test-001")
        for field in base:
            with self.subTest(field=field):
                result = copy.deepcopy(base)
                result[field] = 123
                self.assertIn(f"{field}: invalid type", self.check_result(result))

    def test_invalid_values_and_nested_items(self):
        for field, value in (("schema_version", "0.2"), ("module", "local"),
                             ("module", "unknown"), ("status", "ok"),
                             ("status", []), ("request_id", "another-request"),
                             ("insights", ["text"]), ("sources", [None])):
            with self.subTest(field=field, value=value):
                result = mock_scout_result("quant", "test-001")
                result[field] = value
                self.assertTrue(self.check_result(result))

    def test_non_object(self):
        for result in (None, [], "text", 42):
            self.assertEqual(self.check_result(result), ["result: expected object"])

    def test_extensions_and_non_mutation(self):
        result = mock_scout_result("quant", "test-001")
        result.update(metrics={"count": 0}, started_at="2026-09-22T12:00:00+09:00")
        before = copy.deepcopy(result)
        self.assertEqual(self.check_result(result), [])
        self.assertEqual(result, before)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.json"
            command = [sys.executable, "-m", "src.validation", str(sample),
                       "--module", "quant", "--request-id", "test-001"]
            for contents, code in ((json.dumps(mock_scout_result("quant", "test-001")), 0),
                                   ("{}", 1), ("not json", 2)):
                with self.subTest(code=code):
                    sample.write_text(contents, encoding="utf-8")
                    completed = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(completed.returncode, code, completed.stderr)
                    if code != 2:
                        self.assertEqual(json.loads(completed.stdout)["valid"], code == 0)
            missing_command = command.copy()
            missing_command[3] = str(Path(directory) / "missing.json")
            self.assertEqual(subprocess.run(missing_command, capture_output=True).returncode, 2)
