"""Exports use completed, owned jobs and never submit fresh research."""
import unittest
import os
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import httpx
from pypdf import PdfReader
from fastapi.testclient import TestClient
from src.web.app import create_app
from src.brief.pdf import render_pdf
from src.brief.handoff import render_handoff
from tests.test_web import TOKEN, JOB, PAYLOAD

from src.brief.generator import generate_brief
from tests.test_research_brief import fixture

BRIEF = {**generate_brief(fixture()),'source_count':1,'overview':{'area_summary':'저장된 광화문 조사 자료','primary_customer_signal':None},
 'unique_local_signals':[], 'local_changes':[{'module':'local','title':'지역 문화행사 보도','evidence':'예정 자료 & 확인 <필요>',
 'scope':'합성 테스트 지역','published_at':'2026-10-01',
 'sources':[{'source_id':'test-source','source_url':'https://news.example/a','title':'공식 원문'}]}],
 'trend_patterns':[], 'needs_manual_check':['정량 자료 미확보']}

class ExportTests(unittest.TestCase):
    @unittest.skipUnless(any(Path(p).is_file() for p in (os.getenv('SPOT_PDF_FONT_PATH','/no-font'),
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf','/mnt/c/Windows/Fonts/malgun.ttf','C:/Windows/Fonts/malgun.ttf')),
        'Korean font required for PDF rendering')
    def test_report_sections_and_observations_preserve_zero_and_sources(self):
        import copy
        brief=copy.deepcopy(BRIEF)
        brief['unique_local_signals']=[{'module':'quant','title':'유동인구 요일별 비중','shares':{'mon':{'share_pct':0},'tue':{'share_pct':75}},'sources':[{'source_url':'https://public.example/data','title':'공공 관측'}]}]
        brief['needs_manual_check']=['local: RADIUS_NOT_VERIFIED']
        before=copy.deepcopy(brief)
        reader=PdfReader(BytesIO(render_pdf(brief,PAYLOAD)))
        text='\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('REPORT GUIDE',text)
        self.assertIn('75%',text)
        self.assertIn('0%',text)
        self.assertIn('매장 조사 반경',text)
        self.assertNotIn('RADIUS_NOT_VERIFIED',text)
        self.assertIn('https://public.example/data',text)
        self.assertEqual(brief,before)
        self.assertGreaterEqual(len(reader.pages),6)

    @unittest.skipUnless(any(Path(p).is_file() for p in (os.getenv('SPOT_PDF_FONT_PATH','/no-font'),
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf','/mnt/c/Windows/Fonts/malgun.ttf','C:/Windows/Fonts/malgun.ttf')),
        'Korean font required for PDF rendering; install fonts-nanum')
    def test_pdf_korean_empty_quant_and_clickable_sources(self):
        content=render_pdf(BRIEF,PAYLOAD)
        reader=PdfReader(BytesIO(content))
        text='\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('저장된 광화문',text)
        self.assertIn('정량 자료 미확보',text)
        self.assertIn('예정 자료 & 확인 <필요>',text)
        self.assertTrue(any(page.get('/Annots') for page in reader.pages))
        self.assertNotIn('Instagram 공개 게시물',text)

    @patch('src.brief.pdf.render_pdf',return_value=b'%PDF-1.4\nsynthetic-renderer')
    def test_owned_cached_exports_do_not_resubmit_or_fetch(self, formatter):
        calls=[]
        def handler(request):
            calls.append(request.method)
            return httpx.Response(202 if request.method=='POST' else 200,json={
                'job_id':JOB,'status':'queued' if request.method=='POST' else 'completed',
                'result':{'research_brief':BRIEF}})
        app=create_app(token=TOKEN,n8n_base='https://n8n.example',transport=httpx.MockTransport(handler))
        with TestClient(app,base_url='http://localhost') as c:
            c.get('/')
            c.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            c.get('/api/research/'+JOB)
            pdf=c.get('/api/research/'+JOB+'/pdf')
            self.assertEqual(pdf.status_code,200)
            self.assertTrue(pdf.content.startswith(b'%PDF'))
            handoff=c.get('/api/research/'+JOB+'/handoff')
            self.assertIn('흥부장',handoff.text)
            self.assertIn('스마트폰',handoff.text)
            self.assertEqual(calls,['POST','GET'])
            formatter.assert_called_once()
            c.cookies.clear();c.get('/')
            self.assertEqual(c.get('/api/research/'+JOB+'/pdf').status_code,404)
            self.assertEqual(c.get('/api/research/'+JOB+'/handoff').status_code,404)

    def test_incomplete_export_is_not_research_and_errors_do_not_echo(self):
        calls=[]
        def handler(r):
            calls.append(r.method)
            return httpx.Response(200,json={'job_id':JOB,'status':'running'})
        with TestClient(create_app(token=TOKEN,n8n_base='https://n8n.example',transport=httpx.MockTransport(handler)),base_url='http://localhost') as c:
            self.assertEqual(c.get('/api/research/'+JOB+'/pdf').status_code,401)
            c.get('/');c.post('/api/research',json=PAYLOAD,headers={'Origin':'http://localhost'})
            self.assertEqual(c.get('/api/research/'+JOB+'/pdf').status_code,409)
            self.assertEqual(calls,['POST','GET'])
        self.assertIn('인구 구성',render_handoff(BRIEF,PAYLOAD))

    def test_public_origin_secure_cookie_and_exact_origin(self):
        with patch.dict('os.environ',{'SPOT_WEB_PUBLIC_ORIGIN':'https://spot.example'}):
            app=create_app(token=TOKEN,n8n_base='https://n8n.example',transport=httpx.MockTransport(lambda r:httpx.Response(202,json={'job_id':JOB,'status':'queued'})))
            with TestClient(app,base_url='https://spot.example') as c:
                self.assertIn('Secure',c.get('/').headers['set-cookie'])
                self.assertEqual(c.post('/api/research',json=PAYLOAD,headers={'Origin':'https://evil.example'}).status_code,403)
                self.assertEqual(c.post('/api/research',json=PAYLOAD,headers={'Origin':'https://spot.example'}).status_code,202)
