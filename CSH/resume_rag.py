# RAG(검색 증강 생성) 시스템을 구축하기 위해 필요한 라이브러리를 불러오고 환경 설정을 준비
import os # 운영체제와 상호작용하기 위해 사용. 시스템의 환경 변수에 접근하거나, 파일 경로를 다룰 때 필요
import sys
import json # JSON 파일 파싱용
import asyncio

# Windows에서 psycopg3 async 모드 호환성 문제 해결
# ProactorEventLoop는 psycopg3에서 지원하지 않으므로 SelectorEventLoop으로 변경
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from langchain_community.document_loaders import PyPDFLoader # PDF 파일을 읽어오기 위한 도구
from langchain_text_splitters import RecursiveCharacterTextSplitter # 텍스트를 적절한 크기로 자르는 도구
from langchain_core.documents import Document # 문서 객체 타입

# 임베딩 도구: nomic-embed-text 모델 사용 (768차원, 최대 8192 토큰 컨텍스트 윈도우)
# Ollama를 통해 로컬에서 실행되며, 검색 품질 향상을 위해 task-prefix를 지원한다.
from langchain_ollama import OllamaEmbeddings
# PostgreSQL 데이터베이스를 벡터 저장소로 사용하기 위한 도구
# V2 PGVectorStore: 데이터 유형별 물리적 테이블 분리 (resume_embeddings / qa_embeddings)
from langchain_postgres import PGVectorStore, PGEngine
from langchain_postgres.v2.vectorstores import DistanceStrategy
# 실제로 .env 파일을 읽어서 시스템 환경 변수로 등록하는 도구
from dotenv import load_dotenv

# 보안과 설정 관리를 위해 사용하는 함수
load_dotenv()

# ========== 임베딩 모델 설정 ==========
# nomic-embed-text 사전 요구사항: ollama pull nomic-embed-text
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
VECTOR_SIZE = 768  # nomic-embed-text 임베딩 차원 수
# nomic-embed-text는 8192 토큰(약 6000자)을 처리할 수 있으므로 청크를 크게 설정 가능
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "300"))

# ========== 테이블 이름 설정 ==========
RESUME_TABLE = "resume_embeddings"      # 이력서 벡터 테이블
QA_TABLE = "qa_embeddings"              # 면접 Q&A 벡터 테이블


def _get_connection_string() -> str:
    """DB 연결 문자열을 가져옵니다 (psycopg3 형식)."""
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING", "")
    if conn_str.startswith("postgresql://"):
        conn_str = conn_str.replace("postgresql://", "postgresql+psycopg://", 1)
    return conn_str


class ResumeRAG:
    """
    이력서(PDF)와 면접 Q&A 데이터를 PostgreSQL(pgvector)에 저장하고,
    관련 내용을 검색(Retriever)할 수 있게 해주는 클래스.
    
    PGVectorStore V2 사용 — 데이터 유형별 물리적 테이블 분리:
    - resume_embeddings: 이력서(PDF) 벡터 저장
    - qa_embeddings: 면접 Q&A 참조 데이터 벡터 저장
    
    임베딩 모델: nomic-embed-text (768차원, 8192 토큰 컨텍스트)
    - 검색에 최적화된 전용 임베딩 모델
    - search_document: / search_query: 접두사로 검색 품질 향상
    """
    def __init__(self, table_name: str, connection_string: str = None):
        """
        Args:
            table_name: 벡터 저장 테이블명 (RESUME_TABLE 또는 QA_TABLE)
            connection_string: PostgreSQL 연결 문자열 (없으면 환경변수 사용)
        """
        conn_str = connection_string or _get_connection_string()
        # PGEngine은 psycopg3 (async) 드라이버 필요 → 연결 문자열 강제 변환
        if conn_str.startswith("postgresql://"):
            conn_str = conn_str.replace("postgresql://", "postgresql+psycopg://", 1)
        elif conn_str.startswith("postgresql+psycopg2://"):
            conn_str = conn_str.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        self.connection = conn_str
        self.table_name = table_name

        # nomic-embed-text 임베딩 모델 초기화 (768차원 벡터 생성)
        self.embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

        # PGVectorStore V2: 물리적 테이블 분리
        self.engine = PGEngine.from_connection_string(url=conn_str)
        self._ensure_table(table_name)
        self.vector_store = PGVectorStore.create_sync(
            engine=self.engine,
            table_name=table_name,
            embedding_service=self.embeddings,
            distance_strategy=DistanceStrategy.COSINE_DISTANCE,
        )
        print(f"📦 [RAG] 테이블 '{table_name}' 연결됨")
    
    def _ensure_table(self, table_name: str):
        """V2 테이블이 없으면 생성합니다."""
        try:
            self.engine.init_vectorstore_table(
                table_name=table_name,
                vector_size=VECTOR_SIZE,
                overwrite_existing=False,
            )
            print(f"✅ 테이블 '{table_name}' 준비 완료")
        except Exception as e:
            # 이미 존재하면 무시
            if "already exists" in str(e).lower():
                print(f"ℹ️ 테이블 '{table_name}' 이미 존재함")
            else:
                print(f"⚠️ 테이블 생성 중 경고: {e}")

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

    def load_and_index_json(self, json_path: str, batch_size: int = 100):
        """
        면접 Q&A JSON 데이터를 읽어서 벡터화하여 DB에 저장합니다.
        V2 모드에서는 별도 물리적 테이블(qa_embeddings)에 저장됩니다.
        
        JSON 형식: [{"id": 1, "question": "...", "answer": "..."}, ...]
        각 항목을 "면접 질문: {question}\\n모범 답변: {answer}" 형태의 Document로 변환 후 임베딩합니다.
        
        Args:
            json_path: JSON 파일 경로
            batch_size: 한번에 임베딩할 문서 수 (메모리/속도 조절용)
        
        Returns:
            저장된 문서 수
        """
        if not os.path.exists(json_path):
            print(f"Error: {json_path} 파일이 존재하지 않습니다.")
            return 0

        print(f"Loading JSON: {json_path} ...")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("Error: JSON 파일은 리스트 형식이어야 합니다.")
            return 0

        print(f"총 {len(data)}개의 Q&A 항목 발견.")

        # Q&A를 Document 객체로 변환
        documents = []
        for item in data:
            q = item.get("question", "")
            a = item.get("answer", "")
            item_id = item.get("id", "")
            
            if not q or not a:
                continue
            
            # 질문과 답변을 하나의 문서로 결합 (검색 시 질문으로도, 답변 내용으로도 매칭 가능)
            content = f"면접 질문: {q}\n모범 답변: {a}"
            
            doc = Document(
                page_content=f"search_document: {content}",
                metadata={
                    "source": "interview_qa_data",
                    "qa_id": str(item_id),
                    "question": q,
                    "type": "interview_reference"
                }
            )
            documents.append(doc)

        if not documents:
            print("Warning: 변환된 문서가 없습니다.")
            return 0

        # 긴 답변은 청크 분할 (nomic-embed-text 8192 토큰 제한 고려)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        splits = text_splitter.split_documents(documents)
        print(f"청크 분할 완료: {len(documents)}개 문서 → {len(splits)}개 청크")

        # 배치 단위로 DB에 저장 (대량 데이터 안정성)
        total_indexed = 0
        for i in range(0, len(splits), batch_size):
            batch = splits[i:i + batch_size]
            self.vector_store.add_documents(batch)
            total_indexed += len(batch)
            print(f"  진행률: {total_indexed}/{len(splits)} ({total_indexed * 100 // len(splits)}%)")

        print(f"✅ JSON 인덱싱 완료: {total_indexed}개 청크 저장됨 (테이블: {self.table_name})")
        return total_indexed

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

    def clear_table(self):
        """
        테이블의 벡터 데이터를 전부 삭제하고 재생성합니다.
        """
        self.engine.init_vectorstore_table(
            table_name=self.table_name,
            vector_size=VECTOR_SIZE,
            overwrite_existing=True,
        )
        print(f"✅ 테이블 '{self.table_name}' 초기화 완료")
