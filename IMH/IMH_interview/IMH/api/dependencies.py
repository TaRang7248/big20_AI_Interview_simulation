from functools import lru_cache
from typing import AsyncGenerator

from packages.imh_core.config import IMHConfig
from packages.imh_providers.stt.base import ISTTProvider
from packages.imh_providers.stt.mock import MockSTTProvider

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
