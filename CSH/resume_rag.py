# RAG(검색 증강 생성) 시스템을 구축하기 위해 필요한 라이브러리를 불러오고 환경 설정을 준비
import os # 운영체제와 상호작용하기 위해 사용. 시스템의 환경 변수에 접근하거나, 파일 경로를 다룰 때 필요
from langchain_community.document_loaders import PyPDFLoader # PDF 파일을 읽어오기 위한 도구
from langchain_text_splitters import RecursiveCharacterTextSplitter # 텍스트를 적절한 크기로 자르는 도구
from langchain_core.documents import Document # 문서 객체 타입

# 임베딩 도구: nomic-embed-text 모델 사용 (768차원, 최대 8192 토큰 컨텍스트 윈도우)
# Ollama를 통해 로컬에서 실행되며, 검색 품질 향상을 위해 task-prefix를 지원한다.
from langchain_ollama import OllamaEmbeddings
# PostgreSQL 데이터베이스를 벡터 저장소로 사용하기 위한 도구
from langchain_postgres import PGVector
# 실제로 .env 파일을 읽어서 시스템 환경 변수로 등록하는 도구
from dotenv import load_dotenv

# 보안과 설정 관리를 위해 사용하는 함수
load_dotenv()

# ========== 임베딩 모델 설정 ==========
# nomic-embed-text 사전 요구사항: ollama pull nomic-embed-text
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
# nomic-embed-text는 8192 토큰(약 6000자)을 처리할 수 있으므로 청크를 크게 설정 가능
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "300"))

class ResumeRAG:
    """
    이력서(PDF)를 읽어 PostgreSQL(pgvector)에 저장하고,
    관련 내용을 검색(Retriever)할 수 있게 해주는 클래스.
    
    임베딩 모델: nomic-embed-text (768차원, 8192 토큰 컨텍스트)
    - 검색에 최적화된 전용 임베딩 모델
    - search_document: / search_query: 접두사로 검색 품질 향상
    """
    def __init__(self, connection_string: str = None, collection_name: str = "resume_vectors"):
        # 기본 연결 문자열 (환경변수가 없을 경우 사용)
        DEFAULT_CONNECTION = "POSTGRES_CONNECTION_STRING"
        conn_str = connection_string or os.getenv("POSTGRES_CONNECTION_STRING") or DEFAULT_CONNECTION
        
        # langchain-postgres는 psycopg3를 사용하므로 'postgresql+psycopg://' 형식 필요
        if conn_str and conn_str.startswith("postgresql://"):
            conn_str = conn_str.replace("postgresql://", "postgresql+psycopg://", 1)
        
        self.connection = conn_str
        self.collection_name = collection_name

        # nomic-embed-text 임베딩 모델 초기화 (768차원 벡터 생성)
        self.embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

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
        
        nomic-embed-text 최적화:
        - 8192 토큰 컨텍스트 윈도우를 활용하여 큰 청크 사용 (기본 1500자)
        - 'search_document:' 접두사를 추가하여 임베딩 품질 향상
        """
        if not os.path.exists(pdf_path):
            print(f"Error: {pdf_path} 파일이 존재하지 않습니다.")
            return 0

        print(f"Loading PDF: {pdf_path} ...")
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        # nomic-embed-text의 넓은 컨텍스트 윈도우(8192 토큰)를 활용한 청킹
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]  # 의미 단위로 분할 우선
        )
        splits = text_splitter.split_documents(documents)
        print(f"Created {len(splits)} chunks (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}).")

        # nomic-embed-text 검색 품질 향상을 위해 'search_document:' 접두사 추가
        for doc in splits:
            doc.page_content = f"search_document: {doc.page_content}"

        # DB에 저장 (add_documents)
        print("Indexing to PostgreSQL (pgvector)...")
        self.vector_store.add_documents(splits)
        print("Indexing Complete.")
        return len(splits)

    def get_retriever(self, k: int = 4):
        """
        LangChain Retriever 객체를 반환합니다.
        
        nomic-embed-text 최적화:
        - MMR(Maximal Marginal Relevance) 검색으로 다양성과 관련성 균형
        - fetch_k로 후보를 넓게 가져온 뒤 k개를 다양하게 선택
        """
        return self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": k,            # 최종 반환 문서 수
                "fetch_k": k * 5,  # MMR 후보 문서 수 (다양성 확보)
                "lambda_mult": 0.7  # 0=최대 다양성, 1=최대 유사성 (0.7: 관련성 우선)
            }
        )

    def similarity_search(self, query: str, k: int = 4):
        """
        nomic-embed-text에 최적화된 유사도 검색.
        쿼리에 'search_query:' 접두사를 자동 추가하여 검색 품질을 높입니다.
        """
        prefixed_query = f"search_query: {query}"
        results = self.vector_store.similarity_search(prefixed_query, k=k)
        # 결과에서 'search_document:' 접두사 제거
        for doc in results:
            if doc.page_content.startswith("search_document: "):
                doc.page_content = doc.page_content[len("search_document: "):]
        return results

    def clear_collection(self):
        """
        기존 벡터 데이터를 삭제합니다 (필요 시).
        """
        self.vector_store.delete_collection()
        print(f"Collection '{self.collection_name}' cleared.")
