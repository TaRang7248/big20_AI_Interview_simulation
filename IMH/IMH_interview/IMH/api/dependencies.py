from functools import lru_cache
from typing import AsyncGenerator

from packages.imh_core.config import IMHConfig
from packages.imh_providers.stt.base import ISTTProvider
from packages.imh_providers.stt.mock import MockSTTProvider
from packages.imh_providers.pdf.base import IPDFProvider
from packages.imh_providers.pdf.local_provider import LocalPDFProvider
from packages.imh_providers.embedding.base import EmbeddingProvider
from packages.imh_providers.embedding import get_embedding_provider as _get_embedding_provider_factory

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
