# RAG(검색 증강 생성) 시스템을 구축하기 위해 필요한 라이브러리를 불러오고 환경 설정을 준비
import os # 운영체제와 상호작용하기 위해 사용. 시스템의 환경 변수에 접근하거나, 파일 경로를 다룰 때 필요
from langchain_community.document_loaders import PyPDFLoader # PDF 파일을 읽어오기 위한 도구
from langchain_text_splitters import RecursiveCharacterTextSplitter # 텍스트를 적절한 크기로 자르는 도구

# 텍스트를 숫자로 변환(임베딩)하는 도구. Ollama라는 로컬 AI 엔진을 사용하여 단어나 문장을 고차원의 벡터(숫자 리스트)로 바꿔준다. 컴퓨터는 이 숫자를 비교해 질문과 유사한 문서를 찾는다.
from langchain_ollama import OllamaEmbeddings
# PostgreSQL 데이터베이스를 벡터 저장소로 사용하기 위한 도구
from langchain_postgres import PGVector
# 실제로 .env 파일을 읽어서 시스템 환경 변수로 등록하는 도구
from dotenv import load_dotenv

# 보안과 설정 관리를 위해 사용하는 함수
load_dotenv()

class ResumeRAG:
    """
    이력서(PDF)를 읽어 PostgreSQL(pgvector)에 저장하고,
    관련 내용을 검색(Retriever)할 수 있게 해주는 클래스.
    """
    def __init__(self, connection_string: str = None, collection_name: str = "resume_vectors"):
        # 기본 연결 문자열 (환경변수가 없을 경우 사용)
        DEFAULT_CONNECTION = "POSTGRES_CONNECTION_STRING"
        conn_str = connection_string or os.getenv("POSTGRES_CONNECTION_STRING") or DEFAULT_CONNECTION
        
        # SQLAlchemy/PGVector는 'postgresql+psycopg2://' 형식이 필요하므로 변환
        if conn_str and conn_str.startswith("postgresql://"):
            conn_str = conn_str.replace("postgresql://", "postgresql+psycopg2://", 1)
        
        self.connection = conn_str
        self.collection_name = collection_name

        # 임베딩 모델: Llama 3 (Ollama)
        # 주의: 'ollama pull llama3' 및 'ollama pull nomic-embed-text' (혹은 llama3 자체) 필요
        # 검색 품질을 위해 전용 임베딩 모델(nomic-embed-text)을 권장하지만, 
        # 여기서는 편의상 llama3를 그대로 쓰거나, mxbai-embed-large 등을 쓸 수 있습니다.
        # 이번 예제에서는 'llama3'를 임베딩 모델로도 사용해 봅니다. (가능하다면 'nomic-embed-text' 추천)
        
        # llama3라는 AI 모델을 사용하여 텍스트를 숫자로 변환하는 임베딩 엔진을 생성
        self.embeddings = OllamaEmbeddings(model="llama3") 

        # PGVector 인스턴스 초기화 (연결 자체는 나중에 이루어짐)
        # 데이터베이스와 어떻게 통신할지에 대한 설정 정보를 담은 객체를 만든다
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=self.connection,
            use_jsonb=True,
        )
    # PDF 파일을 불러와서 인덱싱(색인) 작업을 수행하는 함수를 정의. pdf_path라는 이름으로 파일 경로를 입력받는다.
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
