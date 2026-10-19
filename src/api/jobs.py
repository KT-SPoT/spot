"""Bounded single-process job registry with duplicate-request protection."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import Lock
from time import monotonic
from uuid import uuid4


class JobError(Exception):
    def __init__(self, code, status):
        self.code, self.status = code, status


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class JobRegistry:
    def __init__(self, runner, *, capacity=4, retention_seconds=3600, max_records=32, reports_progress=False):
        self.runner = runner
        self.reports_progress = reports_progress
        self.capacity = capacity
        self.retention_seconds = retention_seconds
        self.max_records = max_records
        # Existing offline runner patches process environment; serialize runs.
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spot-research")
        self.lock = Lock()
        self.jobs = {}

    def _prune(self):
        now = monotonic()
        expired = [jid for jid, record in self.jobs.items()
                   if record["finished_clock"] is not None
                   and now - record["finished_clock"] >= self.retention_seconds]
        for jid in expired:
            del self.jobs[jid]

    def submit(self, request):
        payload = deepcopy(request)
        fingerprint = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            self._prune()
            for jid, record in self.jobs.items():
                if record["public"]["request_id"] == payload["request_id"]:
                    if record["fingerprint"] != fingerprint:
                        raise JobError("REQUEST_ID_CONFLICT", 409)
                    return deepcopy(record["public"]), False
            active = sum(r["public"]["status"] in ("queued", "running") for r in self.jobs.values())
            if active >= self.capacity:
                raise JobError("RESEARCH_QUEUE_FULL", 429)
            if len(self.jobs) >= self.max_records:
                finished = [(r["finished_clock"], jid) for jid, r in self.jobs.items() if r["finished_clock"] is not None]
                if not finished:
                    raise JobError("RESEARCH_QUEUE_FULL", 429)
                del self.jobs[min(finished)[1]]
            jid = uuid4().hex
            public = {"job_id": jid, "request_id": payload["request_id"], "status": "queued",
                      "created_at": timestamp(), "started_at": None, "finished_at": None,
                      "status_path": f"/v1/research/jobs/{jid}", "poll_after_seconds": 5,
                      "progress": {"stages": {}, "updated_at": timestamp()}}
            self.jobs[jid] = {"public": public, "fingerprint": fingerprint, "finished_clock": None}
            self.pool.submit(self._run, jid, payload)
            return deepcopy(public), True

    def _run(self, jid, request):
        with self.lock:
            self.jobs[jid]["public"].update(status="running", started_at=timestamp())
        try:
            def report(stage, status):
                if stage not in ("quant", "local", "trend", "merge", "critic", "semantic", "retry", "brief") or status not in ("running", "completed", "success", "partial", "failed"):
                    return
                with self.lock:
                    progress = self.jobs[jid]["public"]["progress"]
                    progress["stages"][stage] = status
                    progress["updated_at"] = timestamp()
            result = self.runner(request, report) if self.reports_progress else self.runner(request)
            update = {"status": "completed", "result": result}
        except Exception:
            # No provider exception/body/credential is returned or logged.
            update = {"status": "failed", "error": {"code": "RESEARCH_EXECUTION_FAILED"}}
        with self.lock:
            self.jobs[jid]["public"].update(update, finished_at=timestamp())
            self.jobs[jid]["finished_clock"] = monotonic()

    def get(self, jid):
        with self.lock:
            self._prune()
            if jid not in self.jobs:
                raise JobError("JOB_NOT_FOUND_OR_EXPIRED", 404)
            return deepcopy(self.jobs[jid]["public"])

    def close(self):
        self.pool.shutdown(wait=True)
