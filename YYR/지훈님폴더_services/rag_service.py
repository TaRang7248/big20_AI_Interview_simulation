# "이력서 처리 엔진"
# 이력서를 텍스트로 변환하고, 검색 가능한 형태로 저장

import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# [메모리 저장소] 세션별 벡터 스토어를 임시 저장 (실무에선 Redis나 파일 저장 권장)
# 구조: { "session_id": vectorstore_object }
vector_store_memory = {}

def process_resume_pdf(thread_id: str, file_path: str):
    """
    PDF 이력서를 읽어서 청크로 나누고, 벡터 DB(FAISS)에 저장합니다.
    """
    try:
        # 1. PDF 로드
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        # 2. 텍스트 분할 (청크 단위로 쪼개기)
        # 이력서는 구조가 중요하므로 청크 사이즈를 적절히 조절
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        splits = text_splitter.split_documents(documents)
        
        # 3. 임베딩 및 벡터 저장소 생성 (FAISS)
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(splits, embeddings)
        
        # 4. 메모리에 저장 (세션 ID 키값)
        vector_store_memory[thread_id] = vectorstore
        
        print(f"📄 [RAG] 이력서 처리 완료: {len(splits)}개 청크 생성 (Session: {thread_id})")
        return True

    except Exception as e:
        print(f"❌ [RAG Error] 이력서 처리 실패: {e}")
        return False

def get_relevant_context(thread_id: str, query: str) -> str:
    """
    사용자의 질문이나 현재 대화 주제와 관련된 이력서 내용을 검색합니다.
    """
    if thread_id not in vector_store_memory:
        return "" # 등록된 이력서 없음
    
    try:
        vectorstore = vector_store_memory[thread_id]
        # 유사도 검색 (상위 3개 청크 추출)
        results = vectorstore.similarity_search(query, k=3)
        
        # 검색된 텍스트 합치기
        context_text = "\n\n".join([doc.page_content for doc in results])
        return context_text
        
    except Exception as e:
        print(f"❌ [Retrieval Error]: {e}")
        return ""