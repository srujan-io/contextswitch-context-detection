from collections import deque
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

def now():
    return datetime.now(timezone.utc).isoformat()

class ExecutionManager:
    def __init__(self):
        self.lock = Lock()
        self.queues = {}
        self.jobs = {}
        self.in_flight = {}

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
        with self.lock:
            if tab_id in self.in_flight:
                return None
            q = self.queues.setdefault(tab_id, deque())
            if not q:
                return None
            action = q.popleft()
            action["status"] = "RUNNING"
            self.in_flight[tab_id] = action["action_id"]
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
            if status == "FAILED":
                self.queues[tab_id] = deque(
                    a for a in self.queues.get(tab_id, ()) if a["job_id"] != job["job_id"]
                )
                for a in job["actions"]:
                    if a["status"] == "PENDING":
                        a["status"] = "CANCELLED"
                job["status"] = "FAILED"
            elif job["completed_steps"] == job["total_steps"]:
                job["status"] = "COMPLETED" if all(
                    r["status"] == "SUCCESS" and r["verified"] for r in job["results"]
                ) else "NEEDS_REVIEW"
            return dict(saved)

    def get_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise KeyError("Unknown job_id.")
            return {**job, "actions": [dict(a) for a in job["actions"]],
                    "results": [dict(r) for r in job["results"]]}

execution_manager = ExecutionManager()
