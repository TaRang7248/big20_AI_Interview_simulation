import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from dotenv import load_dotenv

load_dotenv()

class ResumeRAG:
    """
    이력서(PDF)를 읽어 PostgreSQL(pgvector)에 저장하고,
    관련 내용을 검색(Retriever)할 수 있게 해주는 클래스.
    """
    def __init__(self, connection_string: str = None, collection_name: str = "resume_vectors"):
        # 기본값: 로컬 PostgreSQL 설정 (환경변수 또는 하드코딩)
        # 실제 운영 환경에서는 .env에서 DB 접속 정보를 가져오는 것이 좋습니다.
        self.connection = connection_string or os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/interview_db")
        self.collection_name = collection_name
        
        # 임베딩 모델: Llama 3 (Ollama)
        # 주의: 'ollama pull llama3' 및 'ollama pull nomic-embed-text' (혹은 llama3 자체) 필요
        # 검색 품질을 위해 전용 임베딩 모델(nomic-embed-text)을 권장하지만, 
        # 여기서는 편의상 llama3를 그대로 쓰거나, mxbai-embed-large 등을 쓸 수 있습니다.
        # 이번 예제에서는 'llama3'를 임베딩 모델로도 사용해 봅니다. (가능하다면 'nomic-embed-text' 추천)
        self.embeddings = OllamaEmbeddings(model="llama3") 

        # PGVector 인스턴스 초기화 (연결 자체는 나중에 이루어짐)
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=self.connection,
            use_jsonb=True,
        )

    def load_and_index_pdf(self, pdf_path: str):
        """
        PDF 파일을 읽어서 청크 단위로 자르고, DB에 벡터화하여 저장합니다.
        """
        if not os.path.exists(pdf_path):
            print(f"Error: {pdf_path} 파일이 존재하지 않습니다.")
            return

        print(f"Loading PDF: {pdf_path} ...")
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        # 텍스트 분할 (청킹)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        print(f"Created {len(splits)} chunks.")

        # DB에 저장 (add_documents)
        print("Indexing to PostgreSQL (pgvector)...")
        self.vector_store.add_documents(splits)
        print("Indexing Complete.")

    def get_retriever(self):
        """
        LangChain Retriever 객체를 반환합니다.
        """
        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3} # 상위 3개 관련 문맥 추출
        )

    def clear_collection(self):
        """
        기존 벡터 데이터를 삭제합니다 (필요 시).
        """
        self.vector_store.delete_collection()
        print(f"Collection '{self.collection_name}' cleared.")
