import argparse
import time
from collections.abc import Callable, Sequence

from b2b_domain.db import SessionLocal
from b2b_domain.jobs import JobOutcome, claim_next_job, process_job, record_outcome
from b2b_domain.models import ImportJob, JobStatus
from b2b_domain.settings import get_settings
from sqlalchemy.orm import Session


def run_once(session_factory: Callable[[], Session] = SessionLocal) -> bool:
    with session_factory() as session:
        job = claim_next_job(session)
        if job is None:
            return False
        try:
            outcome = process_job(session, job)
        except Exception as error:
            session.rollback()
            job = session.get(ImportJob, job.id)
            if job is None:
                raise
            outcome = JobOutcome(JobStatus.FAILED, str(error))
        record_outcome(session, job, outcome)
        return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PostgreSQL import-job worker")
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.once:
        run_once()
        return 0
    poll_seconds = get_settings().worker_poll_seconds
    while True:
        if not run_once():
            time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
