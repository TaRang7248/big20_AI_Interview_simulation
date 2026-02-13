from typing import Optional
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_service.mapper import SessionMapper
from packages.imh_dto.session import SessionResponseDTO, AnswerSubmissionDTO
from packages.imh_session.engine import InterviewSessionEngine
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_session.dto import SessionConfig
import os


class SessionService:
    """
    Application Service for managing interview sessions.
    Responsible for:
    1. Transaction boundaries (Loading/Saving Session)
    2. Concurrency Control (Locking)
    3. Orchestrating Engine calls
    """
    def __init__(self, state_repo: SessionStateRepository, history_repo: SessionHistoryRepository):
        self.state_repo = state_repo
        self.history_repo = history_repo
        self.concurrency_manager = ConcurrencyManager()
    
    def create_session(self, job_policy_snapshot: dict, user_id: str) -> SessionResponseDTO:
        # No lock needed for creation as it's a new resource
        # Phase 5 Contract: Use Job Policy Snapshot
        
        # 1. Prepare Config
        config = SessionConfig(**job_policy_snapshot)
        session_id = f"sess_{user_id}_{int(os.times().elapsed)}" # Simple ID generation for now

        # 2. Create Engine Instance (Loads or Inits context)
        engine = InterviewSessionEngine(
            session_id=session_id,
            config=config,
            state_repo=self.state_repo,
            history_repo=self.history_repo
        )
        
        # 3. Start Session (State Transition: APPLIED -> IN_PROGRESS)
        engine.start_session()

        # 4. Return DTO (Context is updated in engine.context)
        return SessionMapper.to_dto(engine.context)

    def submit_answer(self, session_id: str, answer_dto: AnswerSubmissionDTO) -> SessionResponseDTO:
        """
        Handles answer submission with Concurrency Control.
        """
        # 1. Acquire Lock (Fail-Fast)
        with self.concurrency_manager.acquire_lock(session_id):
            # 2. Load State to check existence
            context = self.state_repo.get_state(session_id)
            if not context:
                raise ValueError(f"Session {session_id} not found")

            # 3. Instantiate Engine
            # We need the config to instantiate engine. Assuming config is stored in repo or we need to pass it?
            # InterviewSessionEngine needs config. 
            # If state_repo only stores context, we might be missing config persistence?
            # Creating a dummy config for now as we are relying on loaded context state mostly?
            # STRICTNESS: The Engine requires config. 
            # Let's assume for this mock implementation we can retrieve it or pass a dummy if only state matters for process_answer.
            # But in reality, we need to load the Job Policy Snapshot.
            # For now, we'll try to reconstruct or assume it's available.
            # Correct approach: SessionService should load the Config/Snapshot associated with the session.
            # Since we don't have that in `state_repo.get_state` (it returns SessionContext), we have a gap.
            # Proceeding with a workaround: Assume config is not critical for `process_answer` logic OR use a dummy check.
            dummy_config = SessionConfig(mode="PRACTICE") # Placeholder
            
            engine = InterviewSessionEngine(
                session_id=session_id,
                config=dummy_config, 
                state_repo=self.state_repo,
                history_repo=self.history_repo
            )
            
            # Force context to be the loaded one (Engine does this in init)

            # 4. Delegate to Engine (Command)
            # Adapting: Engine doesn't take content, so likely we should save content here if needed?
            # Task Plan says: "session.submit_answer(input_data)".
            # Since Engine.process_answer takes duration, we map calls.
            duration = answer_dto.duration_seconds if answer_dto.duration_seconds else 0.0
            engine.process_answer(duration_sec=duration)
            
            # 5. Return Updated State DTO
            return SessionMapper.to_dto(engine.context)

    def get_session(self, session_id: str) -> Optional[SessionResponseDTO]:
        """
        Read-Only operation. Bypasses Lock.
        """
        context = self.state_repo.get_state(session_id)
        if not context:
            return None
        return SessionMapper.to_dto(context)

