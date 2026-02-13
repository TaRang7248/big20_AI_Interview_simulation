from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class QuestionGenerationResult:
    def __init__(self, content: str, metadata: Dict[str, Any], success: bool, error: Optional[str] = None):
        self.content = content
        self.metadata = metadata
        self.success = success
        self.error = error

class QuestionGenerator(ABC):
    @abstractmethod
    def generate_question(self, context: Dict[str, Any]) -> QuestionGenerationResult:
        """
        Generate a question based on context.
        Must return success=False on failure, never raise exception.
        """
        pass
