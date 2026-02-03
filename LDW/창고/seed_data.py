import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine, Column, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from pgvector.sqlalchemy import Vector # pgvector 전용 타입

# 1. .env 파일 로드
load_dotenv()

# 2. 환경 변수 읽기
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# 제공하신 DATABASE_URL 또는 POSTGRES_CONNECTION_STRING 사용
DB_URL = os.getenv("POSTGRES_CONNECTION_STRING") 

# 3. 클라이언트 및 DB 설정
client = OpenAI(api_key=OPENAI_API_KEY)
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

# 4. 테이블 모델 정의
class InterviewData(Base):
    __tablename__ = 'interview_questions'
    id = Column(Integer, primary_key=True)
    question = Column(Text)
    answer = Column(Text)
    embedding = Column(Vector(1536)) # OpenAI text-embedding-3-small 모델 규격

# 테이블 생성
Base.metadata.create_all(engine)

def get_embedding(text):
    """텍스트를 1536차원의 벡터로 변환"""
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def seed_data():
    session = Session()
    
    # 윈도우 절대 경로 설정 (r을 붙여서 이스케이프 문자 문제를 방지합니다)
    file_path = r'C:\big20\big20_AI_Interview_simulation\LDW\data\data.json'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"📂 파일을 성공적으로 불러왔습니다: {file_path}")
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다. 경로를 확인해주세요: {file_path}")
        return
    except json.JSONDecodeError:
        print("❌ JSON 파일 형식이 올바르지 않습니다.")
        return

    print(f"🚀 총 {len(data)}개의 데이터를 적재 시작합니다.")

    for item in data:
        # 이미 존재하는 ID인지 확인 (중복 방지)
        exists = session.query(InterviewData).filter_by(id=item['id']).first()
        if exists:
            print(f"⏭️ ID {item['id']}는 이미 존재하여 건너뜁니다.")
            continue

        print(f"📡 Embedding 생성 중 (ID: {item['id']}): {item['question'][:15]}...")
        
        try:
            vector = get_embedding(item['question'])
            new_row = InterviewData(
                id=item['id'],
                question=item['question'],
                answer=item['answer'],
                embedding=vector
            )
            session.add(new_row)
        except Exception as e:
            print(f"❌ ID {item['id']} 처리 중 오류 발생: {e}")
            session.rollback()
            continue
    
    session.commit()
    print("✅ 모든 데이터 적재가 완료되었습니다!")

if __name__ == "__main__":
    seed_data()