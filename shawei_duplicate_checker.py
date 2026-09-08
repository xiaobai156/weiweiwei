"""Import-compatible access to the duplicate-admission service."""
from __future__ import annotations

from shawei.services.duplicate_check import (
    AdmissionDuplicate,
    NewSiteAdmission,
    Site,
    configured_sites,
    evaluate_new_site_admission,
    find_admission_duplicates,
    find_admission_suspicions,
    find_existing_site,
    issue_window,
    load_recent_cache_vectors,
)

__all__ = [
    "AdmissionDuplicate",
    "NewSiteAdmission",
    "Site",
    "configured_sites",
    "evaluate_new_site_admission",
    "find_admission_duplicates",
    "find_admission_suspicions",
    "find_existing_site",
    "issue_window",
    "load_recent_cache_vectors",
]
