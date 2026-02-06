from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_classic.memory import ConversationBufferWindowMemory

from IMH.IMH_no_api.IMH_no_api.core.config import settings
from IMH.IMH_no_api.IMH_no_api.services.llm import ollama_service
from IMH.IMH_no_api.IMH_no_api.services.persona_service import persona_service
from IMH.IMH_no_api.IMH_no_api.schemas.interview_schemas import InterviewerPersona, InterviewQuestionOut, InterviewQuestionIntent, InterviewQuestionMeta
from IMH.IMH_no_api.IMH_no_api.common.redis import redis_client # Redis 클라이언트 (가정)


class InterviewEngine:
    """LangChain 기반 면접 엔진 (최적화 버전)."""

    def __init__(self):
        self.llm = ollama_service.get_llm()
        self.tavily = None
        if settings.TAVILY_API_KEY:
            self.tavily = TavilySearchResults(api_key=settings.TAVILY_API_KEY)
        
        self.parser = JsonOutputParser(pydantic_object=InterviewQuestionOut)

    def _extract_json(self, text: str) -> str:
        """Ollama의 응답에서 JSON 블록만 추출합니다."""
        # 가장 바깥쪽 { } 또는 [ ]를 찾습니다.
        json_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return text

    async def get_initial_research(self, company_name: str, job_title: str) -> str:
        """Tavily를 사용하여 기업 및 직무 관련 최신 정보를 검색합니다."""
        if not self.tavily:
            return "최신 뉴스 정보를 사용할 수 없습니다."
        
        query = f"{company_name} {job_title} 최신 뉴스 및 업계 동향"
        try:
            results = await self.tavily.ainvoke(query)
            return "\n".join([r['content'] for r in results[:3]])
        except Exception:
            return "기업 정보를 검색하는 중 오류가 발생했습니다."

    def create_interview_chain(self, system_prompt: str):
        """면접 질문 생성을 위한 LangChain을 구축합니다."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # JSON 보장을 위해 parser를 직접 연결하지 않고 Raw Output을 받아 후처리 (Resilience 강화)
        chain = prompt | self.llm
        return chain

    async def generate_question(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
        memory: ConversationBufferWindowMemory,
        model_name: Optional[str] = None
    ) -> InterviewQuestionOut:
        """사용자 입력에 기반하여 다음 면접 질문을 생성합니다."""
        llm = ollama_service.get_llm(model_name)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        chain = prompt | llm
        
        # 메모리 로드
        history = memory.load_memory_variables({})["history"]
        current_user_input = user_input
        
        for attempt in range(settings.MAX_RETRY_JSON):
            try:
                response = await chain.ainvoke({
                    "input": current_user_input,
                    "history": history
                })
                
                content = response.content
                clean_json = self._extract_json(content)
                
                try:
                    parsed = self.parser.parse(clean_json)
                except Exception as parse_err:
                    # 파싱 실패 시 모델에게 형식을 다시 지키라고 피드백하며 재시도 유도
                    print(f"[RETRY {attempt+1}] Parsing failed, requesting correction...")
                    current_user_input = (
                        f"{user_input}\n\n"
                        f"(참고: 이전 응답이 JSON 형식이 아니었습니다. 반드시 오직 유효한 JSON 코드 블록만 출력하십시오. "
                        f"에러 내용: {str(parse_err)})"
                    )
                    continue

                # 가끔 모델이 결과를 특정 키로 감싸는 경우 대응
                if isinstance(parsed, dict) and "question" not in parsed:
                    for value in parsed.values():
                        if isinstance(value, dict) and "question" in value:
                            parsed = value
                            break

                if isinstance(parsed, dict) and "question" in parsed:
                    return InterviewQuestionOut(**parsed)
                
                raise ValueError("JSON 내에 'question' 필드가 누락되었습니다.")
                
            except Exception as e:
                print(f"[RETRY {attempt+1}] 질문 생성 도중 오류: {e}")
                if attempt == settings.MAX_RETRY_JSON - 1:
                    return InterviewQuestionOut(
                        question="시스템 일시적 오류로 질문을 생성하지 못했습니다. 다시 시도해 주시겠습니까?",
                        intent=InterviewQuestionIntent(type="RETRY_ERROR", detail=str(e)),
                        meta=InterviewQuestionMeta(research_needed=False, focus_area="SYSTEM_ERROR")
                    )
                continue

    async def clear_session(self, session_id: str):
        """Redis 세션 및 관련 데이터를 모두 삭제합니다 (Final Cleanup)."""
        try:
            # 세션 삭제 로직: 관련 키 패턴 'interview:{session_id}:*' 모두 삭제
            keys = await redis_client.keys(f"interview:{session_id}:*")
            if keys:
                await redis_client.delete(*keys)
            print(f"Session {session_id} cleaned up from Redis.")
        except Exception as e:
            print(f"[WARNING] Redis 세션 삭제 실패 (무시됨): {e}")

    async def _acquire_lock(self, session_id: str) -> bool:
        """동일 세션에 대한 동시 요청 방지를 위한 분산 락 (Advisory Lock)."""
        try:
            lock_key = f"lock:interview:{session_id}"
            # 10초 동안 유지되는 NX (Not Exist) 락 시도
            return await redis_client.set(lock_key, "locked", ex=10, nx=True)
        except Exception as e:
            print(f"[WARNING] Redis 락 획득 실패 (무시됨): {e}")
            return True # 락 실패 시에도 서비스는 가능하도록 true 반환

    async def _release_lock(self, session_id: str):
        """락 해제."""
        try:
            lock_key = f"lock:interview:{session_id}"
            await redis_client.delete(lock_key)
        except Exception:
            pass

# 싱글톤 인스턴스
interview_engine = InterviewEngine()
