from collections import deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
import time

def now():
    return datetime.now(timezone.utc).isoformat()

class ExecutionManager:
    def __init__(self):
        self.lock = RLock()
        self.queues = {}
        self.jobs = {}
        self.in_flight = {}
        self.deadlines = {}

    def expire(self):
        # Never retry an action whose browser outcome is unknown.
        with self.lock:
            for tab_id, deadline in list(self.deadlines.items()):
                if time.monotonic() > deadline:
                    self.record_result(self.in_flight[tab_id], tab_id, {
                        "status":"FAILED", "verified":False,
                        "error":"Browser result timeout; action was not replayed. Inspect browser before retry."})

    def busy(self, tab_id):
        self.expire()
        return tab_id in self.in_flight or bool(self.queues.get(tab_id))

    def cancel_tab(self,tab_id):
        with self.lock:
            self.queues.pop(tab_id,None);self.in_flight.pop(tab_id,None);self.deadlines.pop(tab_id,None)
            for job in self.jobs.values():
                if job['tab_id']==tab_id and job['status'] in ('QUEUED','RUNNING'):
                    job['status']='CANCELLED';job['error']='Website permission revoked';job['updated_at']=now()
                    for action in job['actions']:
                        if action['status'] in ('PENDING','RUNNING'):action['status']='CANCELLED'

    def submit(self, tab_id, validated):
        if not validated.get("valid") or not validated.get("execution_ready"):
            raise ValueError("Plan is invalid or awaiting confirmation.")
        steps = validated.get("validated_steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("No validated steps to execute.")
        job_id = "job-" + uuid4().hex[:12]
        actions = []
        for i, step in enumerate(steps, 1):
            actions.append({
                "action_id": "action-" + uuid4().hex[:12],
                "expected_url": validated.get("context_url"),
                "job_id": job_id, "tab_id": tab_id,
                "step_number": i, "total_steps": len(steps),
                "action": step["action"], "target": step.get("target"),
                "parameters": step.get("parameters", {}),
                "requires_confirmation": step.get("requires_confirmation", False),
                "status": "PENDING"
            })
        with self.lock:
            self.jobs[job_id] = {
                "job_id": job_id, "tab_id": tab_id, "status": "QUEUED",
                "created_at": now(), "updated_at": now(),
                "total_steps": len(actions), "completed_steps": 0,
                "actions": actions, "results": []
            }
            self.queues.setdefault(tab_id, deque()).extend(actions)
        return self.get_job(job_id)

    def claim_next(self, tab_id):
        self.expire()
        with self.lock:
            if tab_id in self.in_flight:
                return None
            q = self.queues.setdefault(tab_id, deque())
            if not q:
                return None
            action = q.popleft()
            action["status"] = "RUNNING"
            self.in_flight[tab_id] = action["action_id"]
            self.deadlines[tab_id] = time.monotonic()+30
            job = self.jobs[action["job_id"]]
            job["status"] = "RUNNING"
            job["updated_at"] = now()
            return dict(action)

    def record_result(self, action_id, tab_id, result):
        with self.lock:
            job = next((j for j in self.jobs.values()
                        if any(a["action_id"] == action_id for a in j["actions"])), None)
            if not job:
                raise KeyError("Unknown action_id.")
            if job["tab_id"] != tab_id:
                raise ValueError("Wrong tab_id.")
            action = next(a for a in job["actions"] if a["action_id"] == action_id)
            previous = next((r for r in job["results"] if r["action_id"] == action_id), None)
            if previous is not None:
                return dict(previous)  # Idempotent result upload, never increment twice.
            if action["status"] != "RUNNING" or self.in_flight.get(tab_id) != action_id:
                raise ValueError("Action is not awaiting a result.")
            status = str(result.get("status", "FAILED")).upper()
            if status not in ("SUCCESS", "FAILED", "UNVERIFIED"):
                status = "FAILED"
            verified = result.get("verified") is True
            if status == "SUCCESS" and not verified:
                status = "UNVERIFIED"
            saved = {
                "action_id": action_id, "action": action["action"],
                "status": status, "verified": verified,
                "result": result.get("result", {}),
                "error": result.get("error"), "received_at": now()
            }
            action["status"] = status
            job["results"].append(saved)
            job["completed_steps"] += 1
            job["updated_at"] = now()
            self.in_flight.pop(tab_id, None)
            self.deadlines.pop(tab_id, None)
            if status in ("FAILED", "UNVERIFIED"):
                self.queues[tab_id] = deque(
                    a for a in self.queues.get(tab_id, ()) if a["job_id"] != job["job_id"]
                )
                for a in job["actions"]:
                    if a["status"] == "PENDING":
                        a["status"] = "CANCELLED"
                job["status"] = "FAILED" if status == "FAILED" else "NEEDS_REVIEW"
            elif job["completed_steps"] == job["total_steps"]:
                job["status"] = "COMPLETED" if all(
                    r["status"] == "SUCCESS" and r["verified"] for r in job["results"]
                ) else "NEEDS_REVIEW"
            return dict(saved)

    def get_job(self, job_id):
        self.expire()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise KeyError("Unknown job_id.")
            return {**job, "actions": [dict(a) for a in job["actions"]],
                    "results": [dict(r) for r in job["results"]]}

execution_manager = ExecutionManager()
