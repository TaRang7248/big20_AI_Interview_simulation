from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    """환경설정 로더.

    Attributes:
        POSTGRES_CONNECTION_STRING: SQLAlchemy async DB URL.
        TOKEN_TTL_MINUTES: 토큰 만료(분).
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    POSTGRES_CONNECTION_STRING: str
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "hopephoto/Qwen3-4B-Instruct-2507_q8:latest"
    EMBEDDING_MODEL: str = "hopephoto/Qwen3-4B-Instruct-2507_q8:latest"
    TOKEN_TTL_MINUTES: int = 60 * 24
    TAVILY_API_KEY: str | None = None

    # Supported Models Selection (Synced with Local Ollama List)
    SUPPORTED_MODELS: dict = {
        "A.X-4.0": {
            "model_id": "cookieshake/a.x-4.0-light-imatrix:q4_k_m",
            "name": "A.X 4.0 Light (iMatrix)",
            "description": "Custom optimized model (4.4GB)"
        },
        "QWEN3": {
            "model_id": "hopephoto/Qwen3-4B-Instruct-2507_q8:latest", 
            "name": "Qwen3 4B Instruct",
            "description": "Quantized Qwen3 variant (4.3GB)"
        },
        "EXAONE-DEEP": {
            "model_id": "exaone-deep:7.8b",
            "name": "EXAONE Deep 7.8B",
            "description": "Large Korean-focused model (4.8GB)"
        },
        "LLAMA3.1-KO": {
            "model_id": "benedict/linkbricks-llama3.1-korean:8b",
            "name": "Llama 3.1 Korean (Linkbricks)",
            "description": "Korean-fine-tuned Llama 3.1 (8.5GB)"
        }
    }

    # Redis & LLM Resilience
    REDIS_SESSION_TTL: int = 3600  # 1 hour default
    MAX_RETRY_JSON: int = 3
    OLLAMA_NUM_CTX: int = 2048              # 컨텍스트 윈도우 크기 캐핑 (VRAM 보호)
    MEMORY_WINDOW_K: int = 5                # Sliding Window Memory 유지 턴 수 (k)


settings: Settings = Settings()
