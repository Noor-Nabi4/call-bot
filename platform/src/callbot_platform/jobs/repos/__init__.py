"""Jobs repositories package — re-exports for import compatibility."""

from __future__ import annotations

from callbot_platform.jobs.errors import JobsError
from callbot_platform.jobs.repos.job_repo import JobRepository
from callbot_platform.jobs.repos.technician_repo import TechnicianRepository

__all__ = [
    "JobRepository",
    "JobsError",
    "TechnicianRepository",
]
