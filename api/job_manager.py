import threading
import uuid
import time
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional, Any, List

try:
    from api.redis_store import RedisStore
except Exception:
    RedisStore = None  # type: ignore


JOB_STORE_PATH = Path.home() / ".adalflow" / "job_store.json"


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Job:
    def __init__(self, repo_url: str, repo_type: str, metadata: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.repo_url = repo_url
        self.repo_type = repo_type
        self.status = JobStatus.QUEUED
        self.error: Optional[str] = None
        self.progress: Optional[str] = None
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "repo_url": self.repo_url,
            "repo_type": self.repo_type,
            "status": self.status,
            "error": self.error,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class JobManager:
    def __init__(self, max_workers: int = 4, redis_url: Optional[str] = None):
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.repo_locks: Dict[str, threading.Lock] = {}
        self.redis_store = None
        if redis_url and RedisStore:
            try:
                self.redis_store = RedisStore(redis_url)
            except Exception:
                self.redis_store = None
        self._load_store()

    def _load_store(self):
        try:
            JOB_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = []
            if self.redis_store:
                data = self.redis_store.load()
            elif JOB_STORE_PATH.exists():
                data = json.loads(JOB_STORE_PATH.read_text())
            for item in data:
                job = Job(repo_url=item.get("repo_url", ""), repo_type=item.get("repo_type", ""), metadata=item.get("metadata", {}))
                job.id = item.get("id", job.id)
                job.status = item.get("status", JobStatus.QUEUED)
                job.error = item.get("error")
                job.progress = item.get("progress")
                job.created_at = item.get("created_at", time.time())
                job.updated_at = item.get("updated_at", job.created_at)
                self.jobs[job.id] = job
        except Exception:
            # If load fails, start fresh without crashing
            self.jobs = {}

    def _persist(self):
        try:
            payload = [job.to_dict() for job in self.jobs.values()]
            if self.redis_store:
                self.redis_store.save(payload)
            else:
                JOB_STORE_PATH.write_text(json.dumps(payload))
        except Exception:
            # Ignore persistence errors to avoid breaking runtime
            pass

    def _get_repo_lock(self, repo_url: str) -> threading.Lock:
        with self.lock:
            if repo_url not in self.repo_locks:
                self.repo_locks[repo_url] = threading.Lock()
            return self.repo_locks[repo_url]

    def create_job(self, repo_url: str, repo_type: str, metadata: Dict[str, Any], task: Callable[[Job], None]) -> Job:
        job = Job(repo_url=repo_url, repo_type=repo_type, metadata=metadata)
        with self.lock:
            self.jobs[job.id] = job
            self._persist()

        def _run():
            repo_lock = self._get_repo_lock(repo_url)
            with repo_lock:
                self._update(job.id, status=JobStatus.RUNNING, progress="starting")
                try:
                    task(job)
                    self._update(job.id, status=JobStatus.SUCCESS, progress="done")
                except Exception as e:
                    self._update(job.id, status=JobStatus.FAILED, error=str(e), progress="error")

        self.executor.submit(_run)
        return job

    def _update(self, job_id: str, **kwargs):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            job.updated_at = time.time()
            self._persist()

    def update_job(self, job_id: str, **kwargs):
        self._update(job_id, **kwargs)

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [job.to_dict() for job in self.jobs.values()]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            job = self.jobs.get(job_id)
            return job.to_dict() if job else None


# Singleton job manager for the API module to import
_workers_env = os.getenv("MAX_JOB_WORKERS")
_redis_url = os.getenv("REDIS_URL")
try:
    _workers_int = int(_workers_env) if _workers_env else None
except Exception:
    _workers_int = None

default_workers = _workers_int or min(8, (os.cpu_count() or 4) * 2)
job_manager = JobManager(max_workers=default_workers, redis_url=_redis_url)
