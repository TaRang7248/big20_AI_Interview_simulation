from abc import ABC, abstractmethod
from typing import Optional, List
from packages.imh_core.dto import LLMMessageDTO, LLMResponseDTO

class ILLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[LLMMessageDTO], system_prompt: Optional[str] = None) -> LLMResponseDTO:
        """
        Chat with LLM.
        Args:
            messages: List of LLMMessageDTO
            system_prompt: Optional system prompt override
        Returns:
            LLMResponseDTO
        """
        pass
