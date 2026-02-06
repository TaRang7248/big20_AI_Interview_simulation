import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector

# 1. 환경 변수 로드 (.env 파일이 루트에 있다고 가정)
load_dotenv()

# DB 연결 정보 (seed_data.py와 동일해야 함)
CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")
COLLECTION_NAME = "interview_questions"

def test_rag_retrieval(query: str):
    print(f"\n🔎 검색 쿼리: '{query}'")
    print("=" * 60)

    try:
        # 2. 임베딩 모델 및 벡터 저장소 연결 초기화
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        vectorstore = PGVector(
            collection_name=COLLECTION_NAME,
            connection_string=CONNECTION_STRING,
            embedding_function=embeddings,
        )

        # 3. 유사도 검색 실행 (k=2: 상위 2개 결과 반환)
        # search_with_score를 사용하면 거리(Distance) 점수도 함께 반환됩니다.
        # 유클리드 거리/코사인 거리 기준: 0에 가까울수록 정확하게 일치함
        results = vectorstore.similarity_search_with_score(query, k=2)

        if not results:
            print("❌ 검색 결과가 없습니다.")
            return

        for i, (doc, score) in enumerate(results):
            print(f"\n[결과 {i+1}] (거리 점수: {score:.4f})")
            print(f"📄 내용 요약: {doc.page_content[:100]}...") # 내용이 길면 100자까지만 출력
            print(f"🏷️  메타데이터: {doc.metadata}")
            print("-" * 30)
            
        print("\n✅ RAG 검색 테스트 성공!")

    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        print("💡 팁: .env 파일의 CONNECTION_STRING이 정확한지, DB가 켜져 있는지 확인하세요.")

if __name__ == "__main__":
    # 테스트할 질문 (적재한 데이터와 관련된 질문)
    test_query = "딥러닝이 머신러닝이랑 다른 점이 뭐야?"
    
    test_rag_retrieval(test_query)