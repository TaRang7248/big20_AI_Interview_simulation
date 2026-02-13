import logging
import time
from typing import Optional
from .state import SessionStatus, SessionEvent, TerminationReason
from .dto import SessionConfig, SessionContext
from .policy import get_policy, InterviewMode
from .repository import SessionStateRepository, SessionHistoryRepository

# Logger setup
logger = logging.getLogger("imh.session")

class InterviewSessionEngine:
    """
    Core Logic for Interview Session.
    Orchestrates state transitions and policy enforcement.
    Strict compliance with TASK-017_PLAN.md.
    """
    def __init__(
        self,
        session_id: str,
        config: SessionConfig,
        state_repo: SessionStateRepository,
        history_repo: SessionHistoryRepository
    ):
        self.session_id = session_id
        self.config = config
        self.state_repo = state_repo
        self.history_repo = history_repo
        
        # Initialize Policy
        self.policy = get_policy(self.config.mode)
        
        # Initialize or load context
        self.context = self._load_or_initialize_context()

    def _load_or_initialize_context(self) -> SessionContext:
        """Load from Hot Storage or create new."""
        existing = self.state_repo.get_state(self.session_id)
        if existing:
            return existing
        return SessionContext(
            session_id=self.session_id,
            status=SessionStatus.APPLIED
        )

    def start_session(self):
        """Transition from APPLIED to IN_PROGRESS."""
        if self.context.status != SessionStatus.APPLIED:
            logger.warning(f"Session {self.session_id} cannot start from {self.context.status}")
            return
        
        logger.info(f"Starting session {self.session_id}")
        self._update_status(SessionStatus.IN_PROGRESS)
        self.context.current_step = 1  # 1-indexed for user facing, or 0? 
        # Plan says "First question start". Let's assume 1-based index for step count.
        self._commit_state()

    def process_answer(self, duration_sec: float):
        """
        Trigger 1: User clicked 'Answer Completed'.
        """
        self._complete_current_step(is_no_answer=False, termination_trigger="USER_ACTION")

    def handle_silence_timeout(self, is_no_answer: bool):
        """
        Trigger 3: Silence Timeout.
        Policy: 
          - Post-Answer Silence -> is_no_answer=False
          - No-Answer Silence -> is_no_answer=True
        """
        logger.info(f"Silence timeout for {self.session_id}. No Answer: {is_no_answer}")
        
        # Policy: Must emit SILENCE_TIMEOUT event (Log for now, in real impl transmit to socket)
        # Note: warning event should have been emitted by client/socket layer BEFORE calling this.
        # But engine must record it.
        
        self._complete_current_step(is_no_answer=is_no_answer, termination_trigger="SILENCE_TIMEOUT")

    def handle_question_timeout(self):
        """
        Trigger 2: Question Time Limit Exceeded.
        """
        logger.warning(f"Question timeout for {self.session_id}")
        self._complete_current_step(is_no_answer=False, termination_trigger="QUESTION_TIMEOUT") # Treat as answer given but cut off? 
        # Policy doesn't explicitly say if timeout is no-answer. 
        # Usually implies partial answer. Let's assume is_no_answer=False unless specified otherwise.

    def _complete_current_step(self, is_no_answer: bool, termination_trigger: str):
        """
        Internal: Finalize the current step/question.
        """
        if self.context.status != SessionStatus.IN_PROGRESS:
            logger.error(f"Cannot complete step in status {self.context.status}")
            return

        # 1. Update counters
        self.context.completed_questions_count += 1
        
        # 2. Log/Record Step (In real logic, we'd save the actual Q&A text here)
        logger.info(f"Step {self.context.current_step} completed. Trigger: {termination_trigger}, NoAns: {is_no_answer}")
        
        # 3. Request Asynchronous Evaluation (Placeholder - TASK-011/012 interaction)
        # self.eval_engine.evaluate_async(...)
        
        # 4. Check Termination Conditions
        config = self.config
        current_completed = self.context.completed_questions_count
        
        # Condition 1: Total questions reached
        if current_completed >= config.total_question_limit:
            self.terminate_session(TerminationReason.MAX_QUESTIONS_REACHED)
            return

        # Condition 2: Early Exit
        # Policy Check: Requires Min Questions?
        can_check_early_exit = True
        if self.policy.requires_min_questions_for_early_exit():
            if current_completed < config.min_question_count:
                can_check_early_exit = False
                
        if can_check_early_exit:
            if self._check_early_exit_signal():
                self.terminate_session(TerminationReason.EARLY_EXIT_SIGNAL)
                return

        # Continue to next step
        self.context.current_step += 1
        self._commit_state()

    def _check_early_exit_signal(self) -> bool:
        """
        Check if Evaluation Layer has sent an early exit signal.
        For Plan/Verification, we check the flag in context.
        """
        return self.context.early_exit_signaled

    def terminate_session(self, reason: TerminationReason):
        """
        Transition to COMPLETED.
        """
        logger.info(f"Terminating session {self.session_id}. Reason: {reason}")
        self._update_status(SessionStatus.COMPLETED)
        self._finalize_persistence() # Sync to PostgreSQL

    def interrupt_session(self, reason: TerminationReason):
        """
        Transition to INTERRUPTED.
        Policy dictates if this is final or resumable (handled by resume_session).
        """
        logger.warning(f"Interrupting session {self.session_id}. Reason: {reason}")
        
        # Policy Check: If terminate on interruption is required, we might treat it differently?
        # Actually state is INTERRUPTED in both cases.
        # But for Actual Mode, it effectively means "Stop", for Practice "Pause".
        
        self._update_status(SessionStatus.INTERRUPTED)
        self._finalize_persistence()

    def resume_session(self):
        """
        Attempt to resume an INTERRUPTED session.
        Allowed only if Policy permits.
        """
        if self.context.status != SessionStatus.INTERRUPTED:
             logger.warning(f"Cannot resume session {self.session_id} from {self.context.status}")
             return

        if not self.policy.can_resume_from_interruption():
            logger.error(f"Policy Violation: Cannot resume session {self.session_id} in {self.policy.mode} mode.")
            return

        logger.info(f"Resuming session {self.session_id}")
        self._update_status(SessionStatus.IN_PROGRESS)
        self._commit_state()

    def _update_status(self, new_status: SessionStatus):
        self.context.status = new_status
        # Sync Hot State
        self.state_repo.update_status(self.session_id, new_status)
        # Sync Cold State (Immediate consistency required for State Transition)
        self.history_repo.update_interview_status(self.session_id, new_status)

    def _commit_state(self):
        """Save context to Hot Storage."""
        self.state_repo.save_state(self.session_id, self.context)

    def _finalize_persistence(self):
        """
        End of Session: Finalize data to Cold Storage.
        """
        # Save aggregated results
        # In reality, this aggregates data from Redis/Hot and flushes to Postgres.
        self.history_repo.save_interview_result(self.session_id, {
            "final_status": self.context.status,
            "completed_questions": self.context.completed_questions_count
        })
        # After this, background worker might pick up for EVALUATED transition.

    # Event Helper
    def emit_silence_warning(self):
        """
        Execute Policy: MUST emit SILENCE_WARNING.
        """
        logger.info(f"Event: {SessionEvent.SILENCE_WARNING} for {self.session_id}")
        # In real impl, send to WebSocket/Client
