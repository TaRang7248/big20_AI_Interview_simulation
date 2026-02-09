import os
import json
from typing import List, Dict

# LangChain 관련 라이브러리 임포트
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()

# DB 연결 정보 및 컬렉션 설정
CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+psycopg2://postgres:password@localhost:5432/interview_db")
COLLECTION_NAME = "interview_questions"

def load_json_data(file_path: str) -> List[Dict]:
    """JSON 파일을 읽어서 리스트로 반환합니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 데이터가 리스트 안에 또 리스트가 있는 경우([[...]])만 평탄화 수행
    if data and isinstance(data, list) and isinstance(data[0], list):
        return [item for sublist in data for item in sublist]
    return data

def seed_database(json_data: List[Dict]):
    """데이터를 벡터화하여 PostgreSQL에 저장합니다."""
    
    print(f"🔄 데이터 적재 시작... (총 {len(json_data)}개)")
    
    # 2. 임베딩 모델 초기화
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # 3. Document 객체로 변환
    documents = []
    for item in json_data:
        # JSON 파일의 실제 키인 'question'과 'answer'를 사용하도록 수정
        question = item.get("question", "")
        answer = item.get("answer", "")
        
        if not question or not answer:
            continue

        # 검색 효율을 위해 질문과 답변을 결합한 텍스트 구성
        page_content = f"Question: {question}\nAnswer: {answer}"
        
        # 메타데이터 구성
        metadata = {
            "category": "Deep Learning",
            "original_question": question,
            "id": item.get("id")
        }
        
        doc = Document(page_content=page_content, metadata=metadata)
        documents.append(doc)

    if not documents:
        print("⚠️ 적재할 데이터가 없습니다.")
        return

    # 4. PGVector를 통해 DB에 저장
    # pre_delete_collection=True는 기존 데이터를 삭제하고 새로 저장함 (초기화 용도)
    PGVector.from_documents(
        embedding=embeddings,
        documents=documents,
        collection_name=COLLECTION_NAME,
        connection_string=CONNECTION_STRING,
        pre_delete_collection=True 
    )
    
    print("✅ 데이터 적재 완료! PostgreSQL에 벡터가 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    # 파일 경로 설정 (절대 경로가 맞는지 확인 필요)
    file_path = r"C:\big20\big20_AI_Interview_simulation\LDW\data\data.json"
    
    if os.path.exists(file_path):
        print(f"📂 파일 로드 중: {file_path}")
        data_to_seed = load_json_data(file_path)
        seed_database(data_to_seed)
    else:
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")