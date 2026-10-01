"""HTTP intake, queue/idempotency and secret boundaries; no live providers."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.app import create_app, research_result
from src.api.configure import configure
from src.api.jobs import JobRegistry, JobError
from tests.test_research_brief import fixture

TOKEN = "synthetic-test-token-not-a-real-credential"
HEADERS = {"X-SPOT-API-Key": TOKEN}


def request():
    return {"schema_version":"0.1", "request_id":"api-test-001",
            "store":{"name":"Synthetic store", "address":"Synthetic address"},
            "campaign":{"purpose":"Synthetic research", "product":"Synthetic product"},
            "research":{"reference_date":"2026-10-01", "lookback_days":0}}


def await_job(client, jid):
    for _ in range(100):
        job = client.get('/v1/research/jobs/'+jid,headers=HEADERS).json()
        if job['status'] in ('completed','failed'):
            return job
        time.sleep(.01)
    raise AssertionError('job did not finish')


class ApiTests(unittest.TestCase):
    def test_health_auth_and_submit_poll(self):
        captured=[]
        def runner(payload):
            captured.append(payload)
            return {'research_brief':{'status':'manual_review'}, 'critic_is_mock':True}
        with TestClient(create_app(token=TOKEN,runner=runner)) as client:
            self.assertEqual(client.get('/health').status_code,200)
            self.assertEqual(client.post('/v1/research/jobs',json=request()).status_code,401)
            submitted=client.post('/v1/research/jobs',json=request(),headers=HEADERS)
            self.assertEqual(submitted.status_code,202)
            job=await_job(client,submitted.json()['job_id'])
            self.assertEqual(job['status'],'completed')
            self.assertTrue(job['result']['critic_is_mock'])
            self.assertEqual(captured[0]['research']['lookback_days'],0)
            self.assertEqual(client.get(submitted.json()['status_path']).status_code,401)
            self.assertEqual(client.get('/v1/research/jobs/unknown',headers=HEADERS).status_code,404)

    def test_invalid_input_rejected_without_echoing_body_or_running(self):
        cases=[]
        for field,value in [('radius_m',True),('lookback_days',-1),('reference_date','bad-'+TOKEN)]:
            payload=request(); payload['research'][field]=value; cases.append(payload)
        payload=request();payload['store']['lat']=float(35);cases.append(payload)
        payload=request();payload['campaign']['product']=' ';cases.append(payload)
        payload=request();payload['api_key']=TOKEN;cases.append(payload)
        with patch('src.api.app.research_result') as run, TestClient(create_app(token=TOKEN)) as client:
            for payload in cases:
                response=client.post('/v1/research/jobs',json=payload,headers=HEADERS)
                self.assertEqual(response.status_code,422)
                self.assertNotIn(TOKEN,response.text)
            run.assert_not_called()

    def test_idempotent_retry_and_conflict(self):
        count=[]
        with TestClient(create_app(token=TOKEN,runner=lambda p:count.append(p) or {})) as client:
            first=client.post('/v1/research/jobs',json=request(),headers=HEADERS)
            await_job(client,first.json()['job_id'])
            second=client.post('/v1/research/jobs',json=request(),headers=HEADERS)
            self.assertEqual(second.status_code,200)
            self.assertEqual(first.json()['job_id'],second.json()['job_id'])
            payload=request();payload['campaign']['product']='different'
            self.assertEqual(client.post('/v1/research/jobs',json=payload,headers=HEADERS).status_code,409)
            self.assertEqual(len(count),1)

    def test_exception_is_failed_job_without_exception_text(self):
        def runner(payload):
            raise RuntimeError(TOKEN)
        with TestClient(create_app(token=TOKEN,runner=runner)) as client:
            response=client.post('/v1/research/jobs',json=request(),headers=HEADERS)
            job=await_job(client,response.json()['job_id'])
            self.assertEqual(job['status'],'failed')
            self.assertNotIn(TOKEN,json.dumps(job))

    def test_bounded_queue_and_serial_execution(self):
        started=threading.Event(); release=threading.Event()
        def runner(payload):
            started.set();release.wait(3);return {}
        jobs=JobRegistry(runner,capacity=1)
        try:
            jobs.submit(request());self.assertTrue(started.wait(2))
            different=request();different['request_id']='different'
            with self.assertRaises(JobError) as error:
                jobs.submit(different)
            self.assertEqual(error.exception.status,429)
        finally:
            release.set();jobs.close()

    def test_expiry_and_eviction(self):
        jobs=JobRegistry(lambda p:{},retention_seconds=0)
        job,_=jobs.submit(request());jobs.close()
        with self.assertRaises(JobError): jobs.get(job['job_id'])
        jobs=JobRegistry(lambda p:{},max_records=1)
        try:
            first,_=jobs.submit(request())
            for _ in range(100):
                if jobs.get(first['job_id'])['status']=='completed':break
                time.sleep(.01)
            second=request();second['request_id']='second';jobs.submit(second)
            with self.assertRaises(JobError):jobs.get(first['job_id'])
        finally:jobs.close()

    def test_live_result_redacts_credentials_in_brief_and_markdown(self):
        bundle=fixture(); brief={'schema_version':'0.1','request_id':bundle['request_id'],
            'status':'manual_review','source_count':0,'overview':{'area_summary':TOKEN,'primary_customer_signal':None},
            'unique_local_signals':[],'local_changes':[],'trend_patterns':[],
            'why_here_now':'draft','research_implications':[],
            'needs_manual_check':['https://example.org/?certKey='+TOKEN]}
        run={'all_contracts_valid':True,'module_status':{},'state':{'research_brief':brief,
             'critic_result':{'status':'manual_review','warnings':[TOKEN]}}}
        with patch('src.integration_smoke.run_smoke',return_value=run),patch.dict('os.environ',{'SPOT_API_TOKEN':TOKEN}):
            result=research_result(bundle['request'],mode='live')
        self.assertNotIn(TOKEN,json.dumps(result))
        self.assertIn('REDACTED',json.dumps(result))

    def test_real_graph_offline_over_http(self):
        with TestClient(create_app(token=TOKEN,mode='offline')) as client:
            response=client.post('/v1/research/jobs',json=request(),headers=HEADERS)
            job=await_job(client,response.json()['job_id'])
            self.assertEqual(job['status'],'completed')
            self.assertEqual(job['result']['mode'],'offline')
            self.assertFalse(job['result']['critic_is_mock'])
            self.assertEqual(job['result']['critic_result']['status'], 'failed')
            self.assertEqual(job['result']['research_brief']['status'],'failed')
            self.assertEqual(job['result']['research_brief']['source_count'],0)

    def test_missing_token_and_bad_mode_fail_startup(self):
        with self.assertRaises(RuntimeError):create_app(token='')
        with self.assertRaises(RuntimeError):create_app(token=TOKEN,mode='invalid')

    def test_local_configuration_preserves_existing_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';path.write_text('YOUTUBE_API_KEY=synthetic-provider\n',encoding='utf-8')
            configure(path);first=path.read_text();configure(path)
            self.assertEqual(path.read_text(),first)
            self.assertIn('YOUTUBE_API_KEY=synthetic-provider',first)
            self.assertIn('SPOT_API_MODE=offline',first)
