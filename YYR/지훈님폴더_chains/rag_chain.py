# PostgreSQL 기반 RAG 체인 구축

import os
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document

# 환경 변수 로드 (.env에 POSTGRES_CONNECTION_STRING 정의 필요)
# 예: "postgresql+psycopg2://user:password@localhost:5432/interview_db"
CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+psycopg2://postgres:password@localhost:5432/interview_db")
COLLECTION_NAME = "interview_questions"  # 벡터 테이블 이름

def get_vectorstore():
    """PostgreSQL PGVector 인스턴스를 반환합니다."""
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # langchain_community의 PGVector 사용
    vectorstore = PGVector(
        collection_name=COLLECTION_NAME,
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings,
    )
    return vectorstore

def retrieve_interview_context(query: str, k: int = 3) -> str:
    """
    쿼리와 관련된 면접 질문 및 평가 루브릭을 검색하여 텍스트로 반환합니다.
    REQ-F-001: 적응형 질문 생성을 위한 맥락 제공
    """
    try:
        vectorstore = get_vectorstore()
        
        # MMR(Maximal Marginal Relevance) 검색을 통해 질문의 다양성 확보 [cite: 203]
        docs = vectorstore.as_retriever(
            search_type="mmr", 
            search_kwargs={"k": k, "fetch_k": 10}
        ).invoke(query)
        
        # 검색된 문서들을 하나의 문자열로 포맷팅
        context_text = "\n\n".join([f"- 참고 질문: {doc.page_content}" for doc in docs])
        return context_text
        
    except Exception as e:
        # DB 연결 실패 등의 경우 에러를 터뜨리지 않고 빈 컨텍스트 반환 (면접 중단 방지)
        print(f"[RAG Error] PostgreSQL 검색 실패: {e}")
        return "관련된 추천 질문이 없습니다. 일반적인 기술 질문을 진행하세요."

# (참고용) 초기 데이터 적재 함수
def add_documents(texts: List[str]):
    vectorstore = get_vectorstore()
    vectorstore.add_texts(texts)