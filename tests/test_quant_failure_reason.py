"""Provider failure privacy and Brief/UI failure explanations; no real requests."""
import io
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from src.scouts.quant_sbiz365 import collect_sbiz365_reports, Sbiz365Error
from src.brief.failures import failure_summary
from src.brief.generator import generate_brief
from test_research_brief import fixture


class QuantFailureTest(unittest.TestCase):
    def test_each_http_stage_reports_status_without_url_body_or_key(self):
        # Include a secret in every exception surface that used to be forwarded.
        secret = 'synthetic-private-value'
        ready = [(200, 'text/html', ''),
                 (200, 'application/json', '{"analyNo":"1","analyDate":"20261003"}'),
                 (200, 'text/html', 'var aACd = "123"; var aANm = "합성동";')]
        for stage in range(4):
            with self.subTest(stage=stage):
                error = HTTPError('https://example.com/?certKey='+secret,503,
                                  secret,None,io.BytesIO(secret.encode()))
                with patch('src.scouts.quant_sbiz365._request_text',side_effect=ready[:stage]+[error]):
                    with self.assertRaises(Sbiz365Error) as raised:
                        collect_sbiz365_reports(lat=35.2,lng=129.08,radius_m=1000,cert_key=secret)
                self.assertIn('HTTP 503',str(raised.exception))
                self.assertNotIn(secret,str(raised.exception))
                self.assertNotIn('https://',str(raised.exception))

    def test_network_and_timeout_messages_are_safe(self):
        for error in (URLError('synthetic-private-value'), TimeoutError('synthetic-private-value')):
            with patch('src.scouts.quant_sbiz365._request_text',side_effect=error):
                with self.assertRaises(Sbiz365Error) as raised:
                    collect_sbiz365_reports(lat=35.2,lng=129.08,radius_m=1000,cert_key='synthetic')
            self.assertIn('네트워크',str(raised.exception))
            self.assertNotIn('synthetic-private-value',str(raised.exception))

    def test_failed_quant_reason_survives_brief_without_evidence_or_raw_error(self):
        bundle=fixture()
        bundle['results']['quant'].update(status='failed', errors=[{
            'code':'SBIZ365_COLLECTION_ERROR',
            'message':'상세분석 페이지 진입 실패: HTTP Error 503: https://example.com/?certKey=synthetic-secret'}])
        bundle['module_status']['quant']='failed'
        brief=generate_brief(bundle)
        self.assertTrue(any('quant: 소상공인365' in text and 'HTTP 503' in text
                            for text in brief['needs_manual_check']))
        self.assertFalse(any(c.get('module')=='quant' for c in brief['unique_local_signals']))
        self.assertIsNone(brief['overview']['primary_customer_signal'])
        self.assertNotIn('synthetic-secret',str(brief))
        self.assertEqual(brief['source_count'],2)

    def test_unknown_or_auth_errors_do_not_claim_outage_or_echo_raw_text(self):
        for code, message, expected in [
            ('SBIZ365_COLLECTION_ERROR','HTTP 403: secret','권한'),
            ('SBIZ365_COLLECTION_ERROR','HTTP 429: secret','호출 제한'),
            ('SBIZ365_COLLECTION_ERROR','secret','연결에 실패'),
            ('MISSING_SBIZ365_CERT_KEY','secret','설정되지'),
            ('UNEXPECTED','secret','오류가 발생')]:
            summary=failure_summary('quant',[{'code':code,'message':message}])
            self.assertIn(expected,summary)
            self.assertNotIn('secret',summary)
            self.assertNotIn('HTTP 503',summary)


if __name__=='__main__':
    unittest.main()
