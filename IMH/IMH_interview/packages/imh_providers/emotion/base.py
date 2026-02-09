from abc import ABC, abstractmethod
from packages.imh_core.dto import EmotionResultDTO

class IEmotionProvider(ABC):
    @abstractmethod
    async def analyze_face(self, image_path: str) -> EmotionResultDTO:
        """
        Analyze face emotion from image path.
        Returns EmotionResultDTO.
        """
        pass
