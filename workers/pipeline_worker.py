"""Drains queued/retry `process_application` jobs, e.g. ones whose BackgroundTask died with the API process.

    python -m workers.pipeline_worker
"""

import logging
import time

from apps.api.services.pipeline import pending_job_ids, run_pipeline_job

logging.basicConfig(level=logging.INFO)


def run_once() -> bool:
    ids = pending_job_ids()
    for job_id in ids:
        run_pipeline_job(job_id)
    return bool(ids)


if __name__ == "__main__":
    while True:
        if not run_once():
            time.sleep(3)
