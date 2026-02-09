import asyncio
from packages.imh_providers.emotion.base import IEmotionProvider
from packages.imh_core.dto import EmotionResultDTO
from packages.imh_core.config import IMHConfig

class MockEmotionProvider(IEmotionProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def analyze_face(self, image_path: str) -> EmotionResultDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return EmotionResultDTO(
            dominant_emotion="neutral",
            scores={"neutral": 0.8, "happy": 0.1, "surprise": 0.1},
            region={"x": 10, "y": 10, "w": 100, "h": 100}
        )
