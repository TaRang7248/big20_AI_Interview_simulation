from functools import lru_cache
from typing import AsyncGenerator

from packages.imh_core.config import IMHConfig
from packages.imh_job.repository import JobPostingRepository, MemoryJobPostingRepository
from packages.imh_session.infrastructure.memory_repo import MemorySessionRepository
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_history.repository import FileHistoryRepository
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_service.session_service import SessionService
from packages.imh_service.admin_query import AdminQueryService

# --- Providers (External Adapters) ---

@lru_cache
def get_config() -> IMHConfig:
    return IMHConfig.load()

# --- Repositories (Persistence) ---

@lru_cache
def get_job_posting_repository() -> JobPostingRepository:
    """
    Singleton Job Repository (Memory).
    Preloaded with dummy data for verification if empty.
    """
    repo = MemoryJobPostingRepository()
    return repo

@lru_cache
def get_session_state_repository() -> SessionStateRepository:
    """
    Singleton Session State Repository (Memory/Redis).
    Must be shared across requests to maintain state.
    """
    return MemorySessionRepository()

@lru_cache
def get_session_history_repository() -> SessionHistoryRepository:
    """
    Singleton History Repository (File-based).
    """
    return FileHistoryRepository()

# --- Infrastructure Services ---

@lru_cache
def get_concurrency_manager() -> ConcurrencyManager:
    """
    Singleton Concurrency Manager (File Lock).
    """
    return ConcurrencyManager()

# --- Domain Services (Application Logic) ---

def get_session_service() -> SessionService:
    """
    Transient Session Service.
    Injected with Singleton Repositories.
    """
    return SessionService(
        state_repo=get_session_state_repository(),
        history_repo=get_session_history_repository(),
        job_repo=get_job_posting_repository()
    )

def get_admin_query_service() -> AdminQueryService:
    """
    Transient Admin Query Service.
    Reads from standard Repositories (Read-Only Logic internal to Service).
    """
    return AdminQueryService(
        repository=get_session_state_repository(),
        job_repo=get_job_posting_repository()
    )
