import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")
COLLECTION_NAME = "interview_questions"

def test_query(query_text: str):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # DB 연결
    store = PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )

    # 유사도 검색 (상위 2개)
    docs = store.similarity_search(query_text, k=2)

    print(f"\n🔍 질문: {query_text}")
    for i, doc in enumerate(docs):
        print(f"\n[{i+1}번째 결과]")
        print(doc.page_content)

if __name__ == "__main__":
    test_query("딥러닝")