import unittest
import httpx
from fastapi.testclient import TestClient
from src.web.app import create_app

TOKEN='test-server-only-token-123456789'
JOB='a'*32
PAYLOAD={'schema_version':'0.1','request_id':'web-demo','store':{'name':'테스트점','address':'부산광역시 강서구 명지국제신도시'},'campaign':{'purpose':'체험 리서치','product':'스마트폰'}}


class WebTests(unittest.TestCase):
    def client(self, handler):
        return TestClient(create_app(token=TOKEN,n8n_base='https://n8n.example',transport=httpx.MockTransport(handler)),base_url='http://localhost')

    def test_intake_poll_and_secret_boundary(self):
        calls=[]
        def handler(request):
            calls.append(request)
            self.assertEqual(request.headers['X-SPOT-API-Key'],TOKEN)
            return httpx.Response(202 if request.method=='POST' else 200,json={'job_id':JOB,'status':'queued' if request.method=='POST' else 'completed','result':{'research_brief_markdown':TOKEN}})
        with self.client(handler) as client:
            page=client.get('/')
            self.assertIn('HttpOnly',page.headers['set-cookie'])
            self.assertIn("frame-ancestors 'none'",page.headers['content-security-policy'])
            self.assertNotIn(TOKEN,page.text)
            response=client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            self.assertEqual(response.status_code,202)
            result=client.get('/api/research/'+JOB)
            self.assertEqual(result.status_code,200)
            self.assertNotIn(TOKEN,result.text)
            self.assertEqual(len(calls),2)

    def test_other_browser_cannot_read_job(self):
        def handler(request): return httpx.Response(202,json={'job_id':JOB,'status':'queued'})
        with self.client(handler) as client:
            client.get('/')
            client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            client.cookies.clear();client.get('/')
            self.assertEqual(client.get('/api/research/'+JOB).status_code,404)

    def test_origin_and_validation_prevent_upstream(self):
        def handler(request): self.fail('Must not call n8n')
        with self.client(handler) as client:
            client.get('/')
            self.assertEqual(client.post('/api/research',json=PAYLOAD,headers={'Origin':'https://evil.example'}).status_code,403)
            self.assertEqual(client.post('/api/research',json={},headers={'Origin':'http://localhost'}).status_code,422)
            self.assertEqual(client.post('/api/research',content=b'x'*17000,headers={'Origin':'http://localhost'}).status_code,413)
            self.assertEqual(client.get('/',headers={'Host':'evil.example'}).status_code,400)

    def test_manual_retry_preserves_upstream_id_and_changes_conflict(self):
        calls=[]
        def handler(request):
            calls.append(__import__('json').loads(request.content))
            if len(calls)==1: raise httpx.ReadTimeout('private '+TOKEN)
            return httpx.Response(200,json={'job_id':JOB,'status':'queued'})
        with self.client(handler) as client:
            client.get('/')
            first=client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            self.assertEqual(first.status_code,503);self.assertNotIn(TOKEN,first.text)
            self.assertEqual(client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'}).status_code,200)
            self.assertEqual(calls[0],calls[1])
            self.assertNotEqual(calls[0]['request_id'],PAYLOAD['request_id'])
            changed={**PAYLOAD,'campaign':{'purpose':'새 목적','product':'스마트폰'}}
            self.assertEqual(client.post('/api/research',json=changed,headers={'Origin':'http://localhost'}).status_code,409)
            self.assertEqual(len(calls),2)

    def test_n8n_errors_are_safe(self):
        for upstream_status,expected in ((403,403),(422,422),(429,429),(500,503),(302,503)):
            with self.subTest(status=upstream_status):
                with self.client(lambda request:httpx.Response(upstream_status,text=TOKEN)) as client:
                    client.get('/')
                    response=client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
                    self.assertEqual(response.status_code,expected)
                    self.assertNotIn(TOKEN,response.text)

    def test_malformed_upstream_not_exposed(self):
        with self.client(lambda request:httpx.Response(200,json={'job_id':'bad','status':'completed','private':TOKEN})) as client:
            client.get('/')
            response=client.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            self.assertEqual(response.status_code,502);self.assertNotIn(TOKEN,response.text)

    def test_session_limits_submission(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(202,json={'job_id':JOB,'status':'queued'})
        with self.client(handler) as client:
            client.get('/')
            for index in range(4):
                self.assertEqual(client.post('/api/research',json={**PAYLOAD,'request_id':str(index)},headers={'Origin':'http://localhost'}).status_code,202)
            self.assertEqual(client.post('/api/research',json={**PAYLOAD,'request_id':'fifth'},headers={'Origin':'http://localhost'}).status_code,429)
            self.assertEqual(len(calls),4)

    def test_reject_credentials_in_origin(self):
        with self.assertRaises(RuntimeError): create_app(token=TOKEN,n8n_base='https://user:secret@n8n.example')


if __name__=='__main__': unittest.main()
