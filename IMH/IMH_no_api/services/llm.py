from __future__ import annotations

from langchain_ollama import ChatOllama, OllamaEmbeddings
from IMH.IMH_no_api.IMH_no_api.core.config import settings

class OllamaService:
    """Ollama 로컬 모델 연동을 위한 베이스 서비스."""

    def __init__(self):
        self._instances = {}
        self.default_model = settings.LLM_MODEL
        self.embeddings = OllamaEmbeddings(
            model=settings.EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )

    def get_llm(self, model_name: str | None = None) -> ChatOllama:
        """지정한 모델 명칭(또는 설정된 기본값)에 해당하는 ChatOllama 인스턴스를 반환합니다."""
        target_model = model_name or self.default_model
        
        # 모델 키워드(예: FAST, PRECISION)로 요청한 경우 실제 모델명으로 변환
        if target_model in settings.SUPPORTED_MODELS:
            target_model = settings.SUPPORTED_MODELS[target_model]["model_id"]
            
        if target_model not in self._instances:
            self._instances[target_model] = ChatOllama(
                model=target_model,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.7,
                num_ctx=settings.OLLAMA_NUM_CTX
            )
        return self._instances[target_model]

    def get_embeddings(self) -> OllamaEmbeddings:
        return self.embeddings

# 글로벌 서비스 인스턴스
ollama_service = OllamaService()
