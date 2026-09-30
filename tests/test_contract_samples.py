"""Validate captured Scout output envelopes without executing Scout APIs in CI."""

import copy
import json
from pathlib import Path
import unittest

from src.validation import validate_scout_result


class ContractSamplesTest(unittest.TestCase):
    def test_captured_scout_samples(self):
        root = Path(__file__).resolve().parents[1] / 'samples' / 'contracts'
        paths = sorted(root.glob('*.cases.json'))
        self.assertTrue(paths, 'No contract acceptance samples supplied')
        for path in paths:
            pack = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(pack['source_commit'])
            self.assertTrue(pack['cases'])
            for case in pack['cases']:
                with self.subTest(file=path.name, case=case['name']):
                    before = copy.deepcopy(case)
                    expected = case['expected']
                    result = case['result']
                    self.assertEqual(validate_scout_result(
                        result, expected_module=expected['module'],
                        request_id=case['input']['request_id']), [])
                    self.assertEqual(result['status'], expected['status'])
                    self.assertEqual(len(result['insights']), expected['insights'])
                    self.assertEqual(len(result['sources']), expected['sources'])
                    self.assertEqual(case, before)
