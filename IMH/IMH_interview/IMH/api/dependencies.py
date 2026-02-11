from functools import lru_cache
from typing import AsyncGenerator

from packages.imh_core.config import IMHConfig
from packages.imh_providers.stt.base import ISTTProvider
from packages.imh_providers.stt.mock import MockSTTProvider
from packages.imh_providers.pdf.base import IPDFProvider
from packages.imh_providers.pdf.local_provider import LocalPDFProvider
from packages.imh_providers.embedding.base import EmbeddingProvider
from packages.imh_providers.embedding import get_embedding_provider as _get_embedding_provider_factory
from packages.imh_providers.emotion.base import IEmotionProvider
from packages.imh_providers.emotion.deepface_impl import DeepFaceEmotionProvider

@lru_cache
def get_config() -> IMHConfig:
    return IMHConfig.load()

async def get_stt_provider() -> AsyncGenerator[ISTTProvider, None]:
    """
    Dependency to get an instance of the STT Provider.
    currently returns MockSTTProvider.
    In the future, this can switch implementations based on config.
    """
    config = get_config()
    # In the future: if config.STT_PROVIDER == "whisper": return FasterWhisperProvider(...)
    provider = MockSTTProvider(config)
    yield provider

async def get_pdf_provider() -> AsyncGenerator[IPDFProvider, None]:
    """
    Dependency to get an instance of the PDF Provider.
    Currently returns LocalPDFProvider (pypdf).
    """
    # config = get_config() # Can be used for limits configuration later
    provider = LocalPDFProvider()
    yield provider

async def get_embedding_provider() -> AsyncGenerator[EmbeddingProvider, None]:
    """
    Dependency to get an instance of the Embedding Provider.
    Currently returns MockEmbeddingProvider.
    """
    # In the future: if config.EMBEDDING_PROVIDER == "local": return LocalEmbeddingProvider(...)
    provider = _get_embedding_provider_factory("mock")
    yield provider

async def get_emotion_provider() -> IEmotionProvider:
    """
    Dependency to get an instance of the Emotion Provider.
    For TASK-008, uses DeepFaceEmotionProvider.
    """
    config = get_config()
    return DeepFaceEmotionProvider(config)

async def get_voice_provider() -> "IVoiceProvider":
    """
    Dependency to get an instance of the Voice Provider.
    For TASK-009, uses ParselmouthVoiceProvider.
    """
    # config = get_config()
    from packages.imh_providers.voice.parselmouth_impl import ParselmouthVoiceProvider
    from packages.imh_providers.voice.base import IVoiceProvider
    return ParselmouthVoiceProvider()

async def get_visual_provider() -> "MediaPipeVisualProvider":
    """
    Dependency to get an instance of the Visual Provider.
    For TASK-010, uses MediaPipeVisualProvider.
    """
    # config = get_config()
    from packages.imh_providers.visual.mediapipe_impl import MediaPipeVisualProvider
    return MediaPipeVisualProvider()

def get_history_repository() -> "HistoryRepository":
    """
    Dependency to get an instance of the History Repository.
    For TASK-014, uses FileHistoryRepository.
    """
    from packages.imh_history.repository import FileHistoryRepository, HistoryRepository
    # Base dir defaults to project standard, or can comes from config
    return FileHistoryRepository()
