import os
import json
from typing import List, Dict

# LangChain 관련 라이브러리 임포트
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일이 있는 경로를 확인하세요)
load_dotenv()

# DB 연결 정보 가져오기
CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+psycopg2://postgres:password@localhost:5432/interview_db")
COLLECTION_NAME = "interview_questions_yyr_test"

def load_json_data(file_path: str) -> List[Dict]:
    """JSON 파일을 읽어서 리스트로 반환합니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 입력 데이터가 이중 리스트([[...]])인 경우 평탄화(Flatten) 처리
    if isinstance(data[0], list):
        return [item for sublist in data for item in sublist]
    return data

def seed_database(json_data: List[Dict]):
    """데이터를 벡터화하여 PostgreSQL에 저장합니다."""
    
    print(f"🔄 데이터 적재 시작... (총 {len(json_data)}개)")
    
    # 2. 임베딩 모델 초기화
    # text-embedding-3-small은 가성비와 성능이 뛰어납니다.
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # 3. Document 객체로 변환
    documents = []
    for item in json_data:
        question = item.get("질문", "")
        answer = item.get("답변", "")
        
        # 검색에 사용될 핵심 텍스트 구성
        # AI가 질문과 답변의 관계를 학습하도록 명시적으로 포맷팅합니다.
        page_content = f"Question: {question}\nAnswer: {answer}"
        
        # 메타데이터 구성 (추후 필터링을 위해 확장 가능)
        metadata = {
            "category": "Deep Learning", # 필요 시 JSON에 카테고리 필드 추가 권장
            "original_question": question
        }
        
        doc = Document(page_content=page_content, metadata=metadata)
        documents.append(doc)

    # 4. PGVector를 통해 DB에 저장 (Upsert 개념은 없으므로 중복 실행 주의)
    # pre_delete_collection=True로 설정하면 기존 데이터를 싹 지우고 새로 넣습니다. (개발 단계 추천)
    PGVector.from_documents(
        embedding=embeddings,
        documents=documents,
        collection_name=COLLECTION_NAME,
        connection_string=CONNECTION_STRING,
        pre_delete_collection=True 
    )
    
    print("✅ 데이터 적재 완료! PostgreSQL에 벡터가 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    # 공유해주신 데이터 샘플 (실제로는 파일에서 읽어오거나 이 리스트를 확장해서 사용)
    sample_data = [
        [
          {
            "질문": "딥러닝이란 무엇인가요?",
            "답변": "딥러닝은 비선형적 특성을 가진 다층의 인공신경망을 활용하여 데이터 속에 내재된 고차원적 패턴을 계층적으로 학습함으로써 복잡한 의사결정 문제를 해결하는 머신러닝의 한 분야입니다. 단순한 선형 회귀나 얕은 모델로는 해결할 수 없는 이미지 인식, 자연어 이해와 같은 비정형 데이터의 추상적 특징 추출을 자동화하기 위해 모델의 깊이를 확장하는 방식을 취합니다. 층이 깊어질수록 하위 층에서는 저수준의 특징을, 상위 층에서는 고수준의 의미론적 정보를 결합하여 인간의 인지 체계와 유사한 계층적 표현을 학습하게 됩니다. 현실적인 관점에서 딥러닝은 막대한 데이터량과 연산 자원을 필요로 하지만, 특징 추출 과정을 사람이 직접 설계(Feature Engineering)해야 하는 기존 방식의 한계를 극복하고 모델의 범용성을 극대화했다는 점에서 기술적 가치가 큽니다. 결국 딥러닝은 데이터로부터 최적의 표현을 스스로 찾아내어 예측 오차를 최소화하는 최적화 구조를 구축하는 과정이라 정의할 수 있습니다."
          },
          {
            "질문": "딥러닝과 머신러닝의 차이를 설명해주시겠습니까?",
            "답변": "딥러닝과 머신러닝의 가장 핵심적인 차이는 문제 해결을 위해 데이터의 특징을 추출하는 주체와 그 표현의 깊이에 있습니다. 머신러닝은 도메인 전문가가 직접 유의미한 변수를 선택하고 가공하는 엔지니어링 과정이 선행되어야 하며, 모델은 정제된 데이터 안에서 최적의 파라미터를 찾는 비교적 명시적인 구조를 가집니다. 반면 딥러닝은 신경망 구조를 통해 데이터로부터 직접 특징을 학습하는 '엔드 투 엔드' 방식을 지향하며, 이는 인간이 인지하지 못하는 미세한 패턴까지 포착하여 복잡한 비정형 데이터를 처리하기 위함입니다. 이러한 차이는 데이터의 규모와 하드웨어 제약 조건에 따른 의사결정 기준으로 작용하는데, 데이터가 적고 해석 가능성이 중요한 경우에는 일반 머신러닝이 유리하고 데이터가 방대하며 고성능 GPU 자원이 확보된 경우에는 딥러닝이 압도적인 성능을 보입니다. 따라서 엔지니어는 데이터의 복잡도와 가용 자원이라는 현실적 한계를 고려하여 두 방법론 중 최적의 아키텍처를 선택하게 됩니다."
          }
        ]
    ]

    # 이중 리스트 구조 평탄화 (Flatten)
    flat_data = [item for sublist in sample_data for item in sublist]
    
    # 실행
    seed_database(flat_data)