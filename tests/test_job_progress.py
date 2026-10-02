import unittest
from threading import Event
from src.api.jobs import JobRegistry


class ProgressTests(unittest.TestCase):
    def test_live_progress_is_observable_before_completion(self):
        started,release=Event(),Event()
        def runner(request,report):
            report('quant','running');report('local','partial')
            report('private-secret','running')
            started.set();release.wait(5)
            report('quant','success');report('brief','completed')
            return {'ok':True}
        jobs=JobRegistry(runner,reports_progress=True)
        try:
            job,_=jobs.submit({'request_id':'progress-test'})
            self.assertTrue(started.wait(5))
            current=jobs.get(job['job_id'])
            self.assertEqual(current['status'],'running')
            self.assertEqual(current['progress']['stages'],{'quant':'running','local':'partial'})
            current['progress']['stages']['quant']='tampered'
            self.assertEqual(jobs.get(job['job_id'])['progress']['stages']['quant'],'running')
        finally:
            release.set();jobs.close()
        self.assertEqual(jobs.get(job['job_id'])['status'],'completed')


if __name__=='__main__': unittest.main()
