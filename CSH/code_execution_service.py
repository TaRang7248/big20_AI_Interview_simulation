"""
코드 실행 및 AI 분석 서비스 (보안 강화 버전)
================================================
면접 코딩 테스트를 위한 샌드박스 코드 실행 및 AI 기반 코드 분석

보안 기능:
1. Docker 컨테이너 격리 (사용 가능 시 자동 전환)
   - --network none: 네트워크 완전 격리
   - --memory 256m: 메모리 제한
   - --read-only + tmpfs: 파일시스템 접근 제한
   - --cap-drop ALL: 커널 권한 박탈
   - --security-opt no-new-privileges: 권한 상승 방지
   - --pids-limit 50: 프로세스 폭탄 방지
   - non-root USER: 최소 권한 실행
2. 코드 보안 검사 (CodeSanitizer)
   - 5개 언어별 위험 패턴 차단 (시스템 명령, 네트워크, 파일 접근 등)
3. 리소스 모니터링 (subprocess fallback)
   - psutil 기반 메모리 모니터링
   - 시간 제한 (timeout)
4. Python 런타임 SafeImporter (defense in depth)
5. LLM 자동 코딩 문제 생성 (1회 1문제)
"""

import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

# .env 파일에서 환경변수 로드
from dotenv import load_dotenv

load_dotenv()

# JSON Resilience 유틸리티
# FastAPI
from fastapi import APIRouter, HTTPException
from json_utils import parse_code_analysis_json
from pydantic import BaseModel

# LLM for code analysis
try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


# ========== 설정 ==========
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
DEFAULT_LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))

# 코딩 테스트 전용 경량 LLM 설정 (이원화 전략)
# [사용자 요청 시 — API 직접 호출용] qwen3:1.7b (VRAM ~2GB, 빠른 응답)
# [백그라운드 사전 생성 — Celery용] qwen3:4b (고품질, 시간 여유)
# 환경변수로 별도 설정 가능
CODING_LLM_MODEL = os.getenv("CODING_LLM_MODEL", "qwen3:1.7b")
CODING_LLM_NUM_CTX = int(os.getenv("CODING_LLM_NUM_CTX", "4096"))
CODING_CELERY_LLM_MODEL = os.getenv("CODING_CELERY_LLM_MODEL", "qwen3:4b")
CODING_CELERY_LLM_NUM_CTX = int(os.getenv("CODING_CELERY_LLM_NUM_CTX", "4096"))

MAX_EXECUTION_TIME = 10  # 초
MAX_OUTPUT_SIZE = 10000  # 문자
SUPPORTED_LANGUAGES = ["python", "javascript", "java", "c", "cpp"]


# ========== 샌드박스 설정 ==========
DOCKER_IMAGE = "interview-sandbox"
DOCKER_AVAILABLE = False
SANDBOX_MEMORY_MB = 256
SANDBOX_MEMORY_LIMIT = f"{SANDBOX_MEMORY_MB}m"
SANDBOX_PID_LIMIT = "50"
SANDBOX_CPU_LIMIT = "1"


def _check_docker_available():
    """Docker 데몬 및 샌드박스 이미지 사용 가능 여부 확인 (서버 시작 시 1회 실행)"""
    global DOCKER_AVAILABLE
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        if result.returncode != 0:
            raise RuntimeError("Docker daemon not running")

        # 샌드박스 이미지 존재 확인
        img_check = subprocess.run(
            ["docker", "image", "inspect", DOCKER_IMAGE], capture_output=True, timeout=5
        )
        if img_check.returncode != 0:
            # 이미지 자동 빌드 시도
            dockerfile_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "sandbox"
            )
            if os.path.isfile(os.path.join(dockerfile_dir, "Dockerfile")):
                print(f"[Sandbox] Docker 이미지 '{DOCKER_IMAGE}' 빌드 중...")
                build = subprocess.run(
                    ["docker", "build", "-t", DOCKER_IMAGE, dockerfile_dir],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if build.returncode == 0:
                    print("[Sandbox] 이미지 빌드 완료 ✅")
                    DOCKER_AVAILABLE = True
                else:
                    print(f"[Sandbox] 이미지 빌드 실패 ❌: {build.stderr[:300]}")
            else:
                print(f"[Sandbox] Dockerfile 미발견: {dockerfile_dir}")
        else:
            DOCKER_AVAILABLE = True
    except Exception:
        pass

    status = (
        "✅ Docker 격리 모드"
        if DOCKER_AVAILABLE
        else "⚠️ 서브프로세스 모드 (보안 제한적)"
    )
    print(f"[Sandbox] {status}")


_check_docker_available()


# ========== 코드 보안 검사기 ==========
class CodeSanitizer:
    """5개 언어에 대한 정적 보안 코드 검사 (Docker 유무와 무관하게 항상 실행)"""

    DANGEROUS_PATTERNS: Dict[str, List[Tuple[str, str]]] = {
        "python": [
            (
                r"\b(subprocess|shutil|socket|requests|urllib|http\.client|ftplib)\b",
                "시스템/네트워크 모듈 사용 금지",
            ),
            (
                r"\b(exec|eval|compile|__import__|globals|locals)\s*\(",
                "동적 코드 실행 금지",
            ),
            (
                r"\b(ctypes|cffi|_thread|multiprocessing|signal)\b",
                "저수준 시스템 접근 금지",
            ),
            (
                r"open\s*\([^)]*[\"\']/(etc|proc|sys|dev|home|root|var)",
                "시스템 경로 접근 금지",
            ),
            (
                r"\bos\s*\.\s*(system|popen|exec|spawn|remove|unlink|rmdir|chmod|chown|kill|fork)",
                "OS 명령 실행 금지",
            ),
        ],
        "javascript": [
            (
                r"require\s*\(\s*[\"\'](?:child_process|fs|net|http|https|dgram|cluster|worker_threads|os|vm)[\"\']",
                "시스템/네트워크 모듈 사용 금지",
            ),
            (r"\beval\s*\(", "eval 사용 금지"),
            (r"\bprocess\s*\.\s*(exit|env|cwd|chdir|kill)", "프로세스 제어 금지"),
            (r"\bFunction\s*\(", "동적 함수 생성 금지"),
        ],
        "java": [
            (r"\b(Runtime|ProcessBuilder)\b.*\b(exec|start)\b", "프로세스 실행 금지"),
            (
                r"\b(Socket|ServerSocket|URL|URLConnection|HttpClient|HttpURLConnection)\b",
                "네트워크 접근 금지",
            ),
            (r"\bSystem\s*\.\s*(exit|getenv)", "시스템 제어 금지"),
            (
                r"\b(ClassLoader|\.class\.getMethod|Method\s*\.\s*invoke)\b",
                "리플렉션 금지",
            ),
            (
                r"\bnew\s+(File|FileReader|FileWriter|FileInputStream|FileOutputStream|RandomAccessFile|PrintWriter)\s*\(",
                "파일 I/O 금지 (Scanner/System.in 사용)",
            ),
        ],
        "c": [
            (
                r"\b(system|popen|execl|execlp|execle|execv|execvp|execvpe|fork|vfork)\s*\(",
                "시스템 명령/프로세스 실행 금지",
            ),
            (
                r"\b(socket|connect|bind|listen|accept|send|recv|sendto|recvfrom)\s*\(",
                "네트워크 함수 사용 금지",
            ),
            (
                r"#\s*include\s*<\s*(sys/socket|netinet|arpa|netdb|unistd)",
                "시스템/네트워크 헤더 사용 금지",
            ),
            (
                r"fopen\s*\([^)]*[\"\']/(etc|proc|sys|dev|home|root|var)",
                "시스템 경로 접근 금지",
            ),
        ],
        "cpp": [
            (
                r"\b(system|popen|execl|execlp|execle|execv|execvp|fork|vfork)\s*\(",
                "시스템 명령/프로세스 실행 금지",
            ),
            (
                r"\b(socket|connect|bind|listen|accept|send|recv)\s*\(",
                "네트워크 함수 사용 금지",
            ),
            (
                r"#\s*include\s*<\s*(sys/socket|netinet|arpa|netdb|unistd)",
                "시스템/네트워크 헤더 사용 금지",
            ),
            (r"\bstd::filesystem\b", "파일시스템 접근 금지"),
            (
                r"fopen\s*\([^)]*[\"\']/(etc|proc|sys|dev|home|root|var)",
                "시스템 경로 접근 금지",
            ),
        ],
    }

    # 코드 크기 제한 (100KB)
    MAX_CODE_SIZE = 100 * 1024

    @classmethod
    def sanitize(cls, code: str, language: str) -> Tuple[bool, Optional[str]]:
        """코드 보안 검사. (safe, error_message) 반환."""
        language = language.lower()

        # 크기 제한
        if len(code.encode("utf-8")) > cls.MAX_CODE_SIZE:
            return False, "🔒 보안 위반: 코드 크기가 100KB를 초과합니다."

        # 언어별 위험 패턴 검사
        patterns = cls.DANGEROUS_PATTERNS.get(language, [])
        for pattern, message in patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                return False, f"🔒 보안 위반: {message} (감지: '{match.group()}')"

        return True, None


# ========== 리소스 모니터링 결과 ==========
@dataclass
class _RunResult:
    """subprocess 실행 결과 (리소스 모니터링 포함)"""

    returncode: int
    stdout: str
    stderr: str
    execution_time_ms: float
    memory_mb: float = 0.0
    timed_out: bool = False
    memory_exceeded: bool = False


# ========== 모델 ==========
class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    C = "c"
    CPP = "cpp"


class CodeExecutionRequest(BaseModel):
    code: str
    language: str
    problem_id: Optional[str] = None
    test_cases: Optional[List[Dict]] = None
    stdin: Optional[str] = None


class CodeExecutionResult(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float  # ms
    memory_usage: Optional[float] = None  # MB


class CodeAnalysisResult(BaseModel):
    overall_score: int  # 100점 만점
    correctness: Dict  # 정답 여부
    time_complexity: Dict  # 시간 복잡도 분석
    space_complexity: Dict  # 공간 복잡도 분석
    code_style: Dict  # 코드 스타일 분석
    comments: Dict  # 주석 분석
    best_practices: Dict  # 모범 사례 준수
    feedback: List[str]  # 개선 피드백
    detailed_analysis: str  # 상세 분석


class CodingProblem(BaseModel):
    id: str
    title: str
    difficulty: str  # easy, medium, hard
    description: str
    examples: List[Dict]
    test_cases: List[Dict]
    hints: Optional[List[str]] = None
    time_limit: int = 5000  # ms
    memory_limit: int = 256  # MB


# ========== LLM 코딩 문제 생성기 ==========
PROBLEM_GENERATION_PROMPT = """당신은 코딩 면접 출제 전문가입니다.
주어진 난이도에 맞는 코딩 문제를 1개 생성해주세요.

[난이도: {difficulty}]

[난이도별 기준]
- easy: 기본 자료구조(배열, 문자열), 반복문, 조건문 활용 문제 (예: 정렬, 탐색, 문자열 처리)
- medium: 해시맵, 스택/큐, 이진탐색, 투 포인터, 재귀 활용 문제
- hard: DP, 그래프, 트리, 고급 알고리즘 문제

[요구사항]
1. 문제는 stdin으로 입력 받고 stdout으로 출력하는 형식이어야 합니다
2. 입력/출력 형식을 명확히 설명해야 합니다
3. 예제를 2개 이상 포함해야 합니다
4. 테스트 케이스를 4개 이상 포함해야 합니다 (예제에 사용한 것 포함)
5. 힌트를 1~2개 제공해야 합니다
6. 한국어로 작성해주세요

[출력 형식 - 반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요]
{{
    "title": "문제 제목",
    "difficulty": "{difficulty}",
    "description": "문제 설명 (입출력 형식 포함)",
    "examples": [
        {{"input": "입력값", "output": "출력값", "explanation": "설명"}}
    ],
    "test_cases": [
        {{"input": "입력값", "expected": "기대 출력값"}}
    ],
    "hints": ["힌트1", "힌트2"]
}}
"""

# 생성된 문제를 캐시 (problem_id -> CodingProblem)
_generated_problems: Dict[str, CodingProblem] = {}


# ========== Redis 기반 문제 풀 (Problem Pool) ==========
# 서버 시작 시 Celery로 난이도별 문제를 미리 생성하여 Redis에 저장합니다.
# API 요청 시 풀에서 즉시 꺼내 반환 → 사용자 체감 지연 거의 0초.
# 풀이 부족해지면 Celery 태스크로 자동 보충합니다.

# 난이도별 풀에 유지할 문제 개수 (기본값)
POOL_TARGET_SIZE = int(os.getenv("CODING_POOL_SIZE", "3"))
# 풀이 이 수치 이하로 떨어지면 보충 태스크를 발행
POOL_REFILL_THRESHOLD = 1


class ProblemPool:
    """
    Redis List 기반 코딩 문제 풀.

    각 난이도(easy/medium/hard)별로 Redis 리스트에 JSON 문제를 저장합니다.
    - pop(difficulty): 풀에서 문제 1개를 꺼냄 (RPOP)
    - push(difficulty, problem): 풀에 문제 1개를 추가 (LPUSH)
    - count(difficulty): 현재 풀 크기 조회
    - needs_refill(difficulty): 보충이 필요한지 확인

    Redis 연결 실패 시 모든 메서드는 graceful하게 None/0/True를 반환합니다.
    """

    REDIS_KEY_PREFIX = "coding_pool"

    def __init__(self):
        """Redis 클라이언트 초기화 (Lazy — 첫 호출 시 연결)"""
        self._redis = None
        self._redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

    def _get_redis(self):
        """Redis 연결을 반환합니다. 연결 실패 시 None."""
        if self._redis is None:
            try:
                import redis as redis_lib

                self._redis = redis_lib.from_url(self._redis_url, decode_responses=True)
                self._redis.ping()
            except Exception as e:
                print(f"[ProblemPool] Redis 연결 실패: {e}")
                self._redis = None
        return self._redis

    def _key(self, difficulty: str) -> str:
        """Redis 키 생성: coding_pool:easy, coding_pool:medium 등"""
        return f"{self.REDIS_KEY_PREFIX}:{difficulty}"

    def push(self, difficulty: str, problem: CodingProblem) -> bool:
        """문제를 풀에 추가합니다. 성공 시 True."""
        r = self._get_redis()
        if not r:
            return False
        try:
            data = json.dumps(problem.dict(), ensure_ascii=False)
            r.lpush(self._key(difficulty), data)
            return True
        except Exception as e:
            print(f"[ProblemPool] push 실패 ({difficulty}): {e}")
            return False

    def pop(self, difficulty: str) -> Optional[CodingProblem]:
        """풀에서 문제 1개를 꺼냅니다. 없으면 None."""
        r = self._get_redis()
        if not r:
            return None
        try:
            data = r.rpop(self._key(difficulty))
            if not data:
                return None
            parsed = json.loads(data)
            problem = CodingProblem(**parsed)
            # 꺼낸 문제를 글로벌 캐시에도 등록 (submission/analysis에서 참조)
            _generated_problems[problem.id] = problem
            return problem
        except Exception as e:
            print(f"[ProblemPool] pop 실패 ({difficulty}): {e}")
            return None

    def count(self, difficulty: str) -> int:
        """현재 풀에 남은 문제 수를 반환합니다."""
        r = self._get_redis()
        if not r:
            return 0
        try:
            return r.llen(self._key(difficulty))
        except Exception:
            return 0

    def needs_refill(self, difficulty: str) -> bool:
        """풀 보충이 필요한지 확인합니다."""
        return self.count(difficulty) <= POOL_REFILL_THRESHOLD


# 전역 문제 풀 인스턴스
problem_pool = ProblemPool()


def trigger_pool_refill(difficulty: str):
    """
    Celery 태스크를 발행하여 풀을 보충합니다.
    Celery가 사용 불가능하면 무시합니다 (다음 요청 시 LLM 직접 호출로 대체).
    """
    try:
        from celery_tasks import pre_generate_coding_problem_task

        needed = POOL_TARGET_SIZE - problem_pool.count(difficulty)
        for _ in range(max(needed, 1)):
            pre_generate_coding_problem_task.delay(difficulty)
        print(f"[ProblemPool] 보충 태스크 {needed}개 발행 ({difficulty})")
    except Exception as e:
        print(f"[ProblemPool] 보충 태스크 발행 실패: {e}")


class CodingProblemGenerator:
    """LLM 기반 코딩 문제 자동 생성기"""

    # LLM 호출 타임아웃 (초) — 이 시간 내에 응답이 없으면 fallback 문제 반환
    # qwen3:1.7b + num_ctx 4096 기준, 코딩 문제 생성 약 15~30초 소요 예상
    LLM_TIMEOUT_SEC = 60

    def __init__(self):
        if LLM_AVAILABLE:
            self.llm = ChatOllama(
                model=CODING_LLM_MODEL,  # 코딩 테스트 전용 경량 모델 (qwen3:1.7b)
                temperature=0.8,  # 다양한 문제 생성을 위해 높은 temperature
                num_ctx=CODING_LLM_NUM_CTX,  # 코딩 문제는 4096 컨텍스트면 충분
                num_predict=2048,  # 최대 생성 토큰 수 제한 (문제 JSON ~1000토큰)
                think=None,  # thinking 모드 비활성화 — 응답 지연 방지
            )
        else:
            self.llm = None

    async def generate(self, difficulty: str = "medium") -> CodingProblem:
        """LLM을 사용하여 코딩 문제 1개를 생성합니다.

        LLM_TIMEOUT_SEC(기본 60초) 이내에 응답이 없으면
        asyncio.TimeoutError가 발생하여 _fallback_problem()을 반환합니다.
        """
        if not self.llm:
            return self._fallback_problem(difficulty)

        try:
            prompt = PROBLEM_GENERATION_PROMPT.format(difficulty=difficulty)
            # /no_think 지시어로 Qwen3 모델의 thinking 모드를 명시적으로 비활성화
            # asyncio.wait_for()로 타임아웃을 감싸서 LLM 무한 대기 방지
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm.invoke,
                    [
                        SystemMessage(
                            content="당신은 코딩 면접 문제 출제 전문가입니다. JSON 형식으로만 응답하세요."
                        ),
                        HumanMessage(content=prompt + "\n/no_think"),
                    ],
                ),
                timeout=self.LLM_TIMEOUT_SEC,
            )
            raw = response.content.strip()

            # <think> 태그 제거 (Qwen 모델 — 열림/닫힘 쌍 및 단독 닫힘 태그 모두 제거)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"</think>", "", raw).strip()

            # JSON 파싱 (json_utils 활용)
            parsed = parse_code_analysis_json(raw)
            if not parsed:
                # 직접 JSON 추출 시도
                json_match = re.search(r"\{[\s\S]*\}", raw)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    print("[CodingProblemGenerator] JSON 파싱 실패, fallback 사용")
                    return self._fallback_problem(difficulty)

            problem_id = str(uuid.uuid4())[:8]
            problem = CodingProblem(
                id=problem_id,
                title=parsed.get("title", "코딩 문제"),
                difficulty=parsed.get("difficulty", difficulty),
                description=parsed.get("description", ""),
                examples=parsed.get("examples", []),
                test_cases=parsed.get("test_cases", []),
                hints=parsed.get("hints", []),
            )

            # 캐시에 저장
            _generated_problems[problem_id] = problem
            print(
                f"[CodingProblemGenerator] 문제 생성 완료: {problem.title} (ID: {problem_id})"
            )
            return problem

        except asyncio.TimeoutError:
            # LLM 응답이 타임아웃 내에 오지 않은 경우 fallback 문제 반환
            print(
                f"[CodingProblemGenerator] LLM 타임아웃 ({self.LLM_TIMEOUT_SEC}초 초과) — fallback 문제 사용"
            )
            return self._fallback_problem(difficulty)

        except Exception as e:
            print(f"[CodingProblemGenerator] 문제 생성 실패: {e}")
            return self._fallback_problem(difficulty)

    def generate_sync(self, difficulty: str = "medium") -> Optional[CodingProblem]:
        """
        동기(Synchronous) 버전 문제 생성 — Celery worker에서 호출합니다.

        asyncio 이벤트 루프가 없는 Celery worker 환경에서 사용하며,
        고품질 모델(qwen3:4b)로 생성하여 Redis 풀에 저장합니다.
        실패 시 None을 반환합니다.
        """
        if not LLM_AVAILABLE:
            return None

        try:
            # Celery 전용 고품질 LLM 인스턴스 (백그라운드 사전 생성용, 시간 여유)
            celery_llm = ChatOllama(
                model=CODING_CELERY_LLM_MODEL,  # qwen3:4b (고품질 모델)
                temperature=0.8,
                num_ctx=CODING_CELERY_LLM_NUM_CTX,  # 4096 (충분한 컨텍스트)
                num_predict=2048,  # 문제 JSON ~1000토큰이면 충분
                think=None,  # thinking 모드 비활성화
            )

            prompt = PROBLEM_GENERATION_PROMPT.format(difficulty=difficulty)
            # /no_think 지시어로 Qwen3 thinking 모드 명시적 비활성화
            response = celery_llm.invoke(
                [
                    SystemMessage(
                        content="당신은 코딩 면접 문제 출제 전문가입니다. JSON 형식으로만 응답하세요."
                    ),
                    HumanMessage(content=prompt + "\n/no_think"),
                ]
            )
            raw = response.content.strip()

            # <think> 태그 제거 (Qwen 모델 — 열림/닫힘 쌍 및 단독 닫힘 태그 모두 제거)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"</think>", "", raw).strip()

            # JSON 파싱
            parsed = parse_code_analysis_json(raw)
            if not parsed:
                json_match = re.search(r"\{[\s\S]*\}", raw)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    print("[CodingProblemGenerator] generate_sync: JSON 파싱 실패")
                    return None

            problem_id = str(uuid.uuid4())[:8]
            problem = CodingProblem(
                id=problem_id,
                title=parsed.get("title", "코딩 문제"),
                difficulty=parsed.get("difficulty", difficulty),
                description=parsed.get("description", ""),
                examples=parsed.get("examples", []),
                test_cases=parsed.get("test_cases", []),
                hints=parsed.get("hints", []),
            )
            print(
                f"[CodingProblemGenerator] 동기 생성 완료: {problem.title} (ID: {problem_id})"
            )
            return problem

        except Exception as e:
            print(f"[CodingProblemGenerator] generate_sync 실패: {e}")
            return None

    def _fallback_problem(self, difficulty: str = "easy") -> CodingProblem:
        """
        LLM 사용 불가 시 문제 은행에서 랜덤 반환.

        난이도별 7+개의 문제를 보유하며, 요청시 랜덤으로 1개를 선택합니다.
        Redis 풀이 비어있고 LLM도 실패할 때 사용되므로, 체감 지연 0초.
        """

        # ========== 난이도별 문제 은행 ==========
        problems_bank = {
            "easy": [
                {
                    "title": "두 수의 합 (Two Sum)",
                    "description": """정수 배열 nums와 정수 target이 주어집니다.
nums에서 두 수를 선택하여 더한 값이 target이 되는 두 수의 인덱스를 반환하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)
- 세 번째 줄: target 값

**출력 형식:**
- 두 인덱스를 공백으로 구분하여 출력""",
                    "examples": [
                        {
                            "input": "4\n2 7 11 15\n9",
                            "output": "0 1",
                            "explanation": "nums[0] + nums[1] = 2 + 7 = 9",
                        },
                        {
                            "input": "3\n3 2 4\n6",
                            "output": "1 2",
                            "explanation": "nums[1] + nums[2] = 2 + 4 = 6",
                        },
                    ],
                    "test_cases": [
                        {"input": "4\n2 7 11 15\n9", "expected": "0 1"},
                        {"input": "3\n3 2 4\n6", "expected": "1 2"},
                        {"input": "2\n3 3\n6", "expected": "0 1"},
                        {"input": "5\n1 5 3 7 2\n9", "expected": "1 3"},
                    ],
                    "hints": [
                        "해시맵을 사용하면 O(n) 시간 복잡도로 해결할 수 있습니다."
                    ],
                },
                {
                    "title": "문자열 뒤집기 (Reverse String)",
                    "description": """주어진 문자열을 뒤집어 출력하세요.

**입력 형식:**
- 한 줄의 문자열

**출력 형식:**
- 뒤집어진 문자열""",
                    "examples": [
                        {
                            "input": "hello",
                            "output": "olleh",
                            "explanation": "'hello'를 뒤집으면 'olleh'",
                        },
                        {
                            "input": "world",
                            "output": "dlrow",
                            "explanation": "'world'를 뒤집으면 'dlrow'",
                        },
                    ],
                    "test_cases": [
                        {"input": "hello", "expected": "olleh"},
                        {"input": "world", "expected": "dlrow"},
                        {"input": "a", "expected": "a"},
                        {"input": "abcdef", "expected": "fedcba"},
                    ],
                    "hints": ["문자열 슬라이싱을 활용해보세요."],
                },
                {
                    "title": "최댓값 찾기 (Find Maximum)",
                    "description": """정수 배열에서 최댓값을 찾아 출력하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)

**출력 형식:**
- 최댓값""",
                    "examples": [
                        {
                            "input": "5\n3 1 4 1 5",
                            "output": "5",
                            "explanation": "배열에서 가장 큰 수는 5",
                        },
                        {
                            "input": "3\n-1 -5 -3",
                            "output": "-1",
                            "explanation": "음수만 있을 때 가장 큰 수는 -1",
                        },
                    ],
                    "test_cases": [
                        {"input": "5\n3 1 4 1 5", "expected": "5"},
                        {"input": "3\n-1 -5 -3", "expected": "-1"},
                        {"input": "1\n42", "expected": "42"},
                        {"input": "4\n10 20 30 40", "expected": "40"},
                    ],
                    "hints": ["변수 하나로 최댓값을 추적하면서 반복하세요."],
                },
                {
                    "title": "팔린드롬 판별 (Palindrome Check)",
                    "description": """주어진 문자열이 팔린드롬(앞뒤가 같은 문자열)인지 판별하세요.

**입력 형식:**
- 한 줄의 문자열 (소문자 영어만)

**출력 형식:**
- 팔린드롬이면 True, 아니면 False""",
                    "examples": [
                        {
                            "input": "racecar",
                            "output": "True",
                            "explanation": "racecar는 뒤집어도 같으므로 팔린드롬",
                        },
                        {
                            "input": "hello",
                            "output": "False",
                            "explanation": "hello는 뒤집으면 olleh이므로 팔린드롬이 아님",
                        },
                    ],
                    "test_cases": [
                        {"input": "racecar", "expected": "True"},
                        {"input": "hello", "expected": "False"},
                        {"input": "a", "expected": "True"},
                        {"input": "abba", "expected": "True"},
                        {"input": "abc", "expected": "False"},
                    ],
                    "hints": ["문자열을 뒤집어서 원래 문자열과 비교해보세요."],
                },
                {
                    "title": "FizzBuzz",
                    "description": """정수 n이 주어지면 1부터 n까지 각 수에 대해:
- 3의 배수이면 Fizz
- 5의 배수이면 Buzz
- 3과 5의 공배수이면 FizzBuzz
- 아니면 그 수를 출력하세요.

**입력 형식:**
- 정수 n

**출력 형식:**
- 각 줄에 결과 출력""",
                    "examples": [
                        {
                            "input": "5",
                            "output": "1\n2\nFizz\n4\nBuzz",
                            "explanation": "3은 Fizz, 5는 Buzz",
                        },
                        {
                            "input": "15",
                            "output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz",
                            "explanation": "15는 3과 5의 공배수",
                        },
                    ],
                    "test_cases": [
                        {"input": "5", "expected": "1\n2\nFizz\n4\nBuzz"},
                        {"input": "3", "expected": "1\n2\nFizz"},
                        {"input": "1", "expected": "1"},
                        {
                            "input": "15",
                            "expected": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz",
                        },
                    ],
                    "hints": [
                        "나머지 연산자(%)를 활용하세요.",
                        "3과 5의 공배수부터 먼저 확인하세요.",
                    ],
                },
                {
                    "title": "배열 정렬 (Array Sort)",
                    "description": """주어진 정수 배열을 오름차순으로 정렬하여 출력하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)

**출력 형식:**
- 정렬된 정수를 공백으로 구분하여 출력""",
                    "examples": [
                        {
                            "input": "5\n5 3 1 4 2",
                            "output": "1 2 3 4 5",
                            "explanation": "오름차순 정렬",
                        },
                        {
                            "input": "3\n3 1 2",
                            "output": "1 2 3",
                            "explanation": "오름차순 정렬",
                        },
                    ],
                    "test_cases": [
                        {"input": "5\n5 3 1 4 2", "expected": "1 2 3 4 5"},
                        {"input": "3\n3 1 2", "expected": "1 2 3"},
                        {"input": "1\n1", "expected": "1"},
                        {"input": "4\n-3 0 5 -1", "expected": "-3 -1 0 5"},
                    ],
                    "hints": ["내장 정렬 함수를 사용하거나 직접 구현해보세요."],
                },
                {
                    "title": "짝수/홀수 분류 (Even/Odd Count)",
                    "description": """정수 배열에서 짝수와 홀수의 개수를 각각 출력하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)

**출력 형식:**
- 짝수_개수 홀수_개수 (공백으로 구분)""",
                    "examples": [
                        {
                            "input": "5\n1 2 3 4 5",
                            "output": "2 3",
                            "explanation": "짝수(2,4)=2개, 홀수(1,3,5)=3개",
                        },
                        {
                            "input": "3\n2 4 6",
                            "output": "3 0",
                            "explanation": "모두 짝수",
                        },
                    ],
                    "test_cases": [
                        {"input": "5\n1 2 3 4 5", "expected": "2 3"},
                        {"input": "3\n2 4 6", "expected": "3 0"},
                        {"input": "1\n7", "expected": "0 1"},
                        {"input": "4\n0 1 2 3", "expected": "2 2"},
                    ],
                    "hints": ["나머지 연산자(%)로 짝수/홀수를 판별하세요."],
                },
            ],
            "medium": [
                {
                    "title": "유효한 괄호 (Valid Parentheses)",
                    "description": """주어진 문자열이 유효한 괄호 조합인지 판별하세요.
괄호 종류: (), {{}}, []

**입력 형식:**
- 한 줄의 괄호 문자열

**출력 형식:**
- 유효하면 True, 아니면 False""",
                    "examples": [
                        {
                            "input": "()[]{}",
                            "output": "True",
                            "explanation": "모든 괄호가 올바르게 닫힘",
                        },
                        {
                            "input": "(]",
                            "output": "False",
                            "explanation": "괄호 종류가 다름",
                        },
                    ],
                    "test_cases": [
                        {"input": "()[]{}", "expected": "True"},
                        {"input": "(]", "expected": "False"},
                        {"input": "(())", "expected": "True"},
                        {"input": "([)]", "expected": "False"},
                        {"input": "", "expected": "True"},
                    ],
                    "hints": [
                        "스택 자료구조를 활용하세요.",
                        "여는 괄호는 push, 닫는 괄호는 pop하여 매칭하세요.",
                    ],
                },
                {
                    "title": "중복 문자 없는 가장 긴 부분 문자열",
                    "description": """주어진 문자열에서 중복 문자가 없는 가장 긴 부분 문자열의 길이를 구하세요.

**입력 형식:**
- 한 줄의 문자열

**출력 형식:**
- 가장 긴 부분 문자열의 길이 (정수)""",
                    "examples": [
                        {
                            "input": "abcabcbb",
                            "output": "3",
                            "explanation": "'abc'가 가장 긴 중복없는 부분문자열 (길이 3)",
                        },
                        {
                            "input": "bbbbb",
                            "output": "1",
                            "explanation": "'b'가 가장 긴 중복없는 부분문자열 (길이 1)",
                        },
                    ],
                    "test_cases": [
                        {"input": "abcabcbb", "expected": "3"},
                        {"input": "bbbbb", "expected": "1"},
                        {"input": "pwwkew", "expected": "3"},
                        {"input": "abcdef", "expected": "6"},
                        {"input": "a", "expected": "1"},
                    ],
                    "hints": [
                        "슬라이딩 윈도우 기법을 사용해보세요.",
                        "set으로 현재 윈도우의 문자를 추적하세요.",
                    ],
                },
                {
                    "title": "애너그램 그룹화 (Group Anagrams)",
                    "description": """주어진 문자열 배열에서 애너그램끼리 그룹화하세요.
애너그램: 문자를 재배열하면 같아지는 단어들

**입력 형식:**
- 첫 번째 줄: 단어의 개수 n
- 두 번째 줄: n개의 단어 (공백으로 구분)

**출력 형식:**
- 각 그룹을 한 줄에 공백으로 구분하여 출력 (알파벳 순)""",
                    "examples": [
                        {
                            "input": "3\neat tea ate",
                            "output": "ate eat tea",
                            "explanation": "eat, tea, ate는 서로 애너그램",
                        },
                        {
                            "input": "2\nabc bca",
                            "output": "abc bca",
                            "explanation": "abc와 bca는 애너그램",
                        },
                    ],
                    "test_cases": [
                        {"input": "3\neat tea ate", "expected": "ate eat tea"},
                        {"input": "2\nabc bca", "expected": "abc bca"},
                        {"input": "1\nhello", "expected": "hello"},
                        {
                            "input": "4\nlisten silent abc cab",
                            "expected": "abc cab\nlisten silent",
                        },
                    ],
                    "hints": [
                        "단어를 정렬하면 애너그램은 같은 문자열이 됩니다.",
                        "dict를 사용하여 그룹화하세요.",
                    ],
                },
                {
                    "title": "이진 탐색 (Binary Search)",
                    "description": """정렬된 정수 배열에서 target 값의 인덱스를 찾으세요.
존재하지 않으면 -1을 출력하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정렬된 정수 (공백으로 구분)
- 세 번째 줄: target 값

**출력 형식:**
- target의 인덱스 (없으면 -1)""",
                    "examples": [
                        {
                            "input": "5\n1 3 5 7 9\n5",
                            "output": "2",
                            "explanation": "5는 인덱스 2에 위치",
                        },
                        {
                            "input": "5\n1 3 5 7 9\n4",
                            "output": "-1",
                            "explanation": "4는 배열에 없음",
                        },
                    ],
                    "test_cases": [
                        {"input": "5\n1 3 5 7 9\n5", "expected": "2"},
                        {"input": "5\n1 3 5 7 9\n4", "expected": "-1"},
                        {"input": "1\n10\n10", "expected": "0"},
                        {"input": "6\n2 4 6 8 10 12\n12", "expected": "5"},
                    ],
                    "hints": [
                        "이진 탐색은 O(log n) 시간 복잡도입니다.",
                        "left, right 포인터를 사용하세요.",
                    ],
                },
                {
                    "title": "순열 조합 (Permutation)",
                    "description": """주어진 정수 n에 대해 1부터 n까지의 모든 순열을 사전순으로 출력하세요.

**입력 형식:**
- 정수 n (1 ≤ n ≤ 6)

**출력 형식:**
- 각 순열을 한 줄에 공백으로 구분하여 출력""",
                    "examples": [
                        {
                            "input": "2",
                            "output": "1 2\n2 1",
                            "explanation": "1,2의 모든 순열",
                        },
                        {
                            "input": "3",
                            "output": "1 2 3\n1 3 2\n2 1 3\n2 3 1\n3 1 2\n3 2 1",
                            "explanation": "1,2,3의 모든 순열",
                        },
                    ],
                    "test_cases": [
                        {"input": "2", "expected": "1 2\n2 1"},
                        {
                            "input": "3",
                            "expected": "1 2 3\n1 3 2\n2 1 3\n2 3 1\n3 1 2\n3 2 1",
                        },
                        {"input": "1", "expected": "1"},
                    ],
                    "hints": [
                        "재귀 또는 백트래킹 알고리즘을 활용하세요.",
                        "itertools.permutations를 사용할 수도 있습니다.",
                    ],
                },
                {
                    "title": "행렬 덧셈 (Matrix Addition)",
                    "description": """두 개의 N×M 행렬을 더한 결과를 출력하세요.

**입력 형식:**
- 첫 번째 줄: N M (행과 열의 수)
- 다음 N줄: 첫 번째 행렬
- 다음 N줄: 두 번째 행렬

**출력 형식:**
- N개의 줄에 계산 결과 행렬 출력 (공백으로 구분)""",
                    "examples": [
                        {
                            "input": "2 2\n1 2\n3 4\n5 6\n7 8",
                            "output": "6 8\n10 12",
                            "explanation": "(1+5, 2+6) (3+7, 4+8)",
                        },
                    ],
                    "test_cases": [
                        {"input": "2 2\n1 2\n3 4\n5 6\n7 8", "expected": "6 8\n10 12"},
                        {"input": "1 1\n5\n3", "expected": "8"},
                        {
                            "input": "2 3\n1 2 3\n4 5 6\n7 8 9\n10 11 12",
                            "expected": "8 10 12\n14 16 18",
                        },
                    ],
                    "hints": ["이중 반복문을 사용하여 각 위치의 값을 더하세요."],
                },
                {
                    "title": "공통 문자 찾기 (Common Characters)",
                    "description": """두 문자열에서 공통되는 문자를 알파벳 순서로 출력하세요.
각 문자는 하나만 저장하며, 중복은 제거합니다.

**입력 형식:**
- 첫 번째 줄: 문자열 A
- 두 번째 줄: 문자열 B

**출력 형식:**
- 공통 문자를 알파벳 순서로 출력 (없으면 NONE)""",
                    "examples": [
                        {
                            "input": "abcde\nbcfgh",
                            "output": "bc",
                            "explanation": "b와 c가 공통",
                        },
                        {
                            "input": "abc\nxyz",
                            "output": "NONE",
                            "explanation": "공통 문자 없음",
                        },
                    ],
                    "test_cases": [
                        {"input": "abcde\nbcfgh", "expected": "bc"},
                        {"input": "abc\nxyz", "expected": "NONE"},
                        {"input": "hello\nworld", "expected": "lo"},
                        {"input": "aaa\na", "expected": "a"},
                    ],
                    "hints": ["set 자료구조의 교집합 연산을 활용하세요."],
                },
            ],
            "hard": [
                {
                    "title": "최장 증가 부분 수열 (LIS)",
                    "description": """정수 배열이 주어질 때, 가장 긴 증가 부분 수열의 길이를 구하세요.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)

**출력 형식:**
- 최장 증가 부분 수열의 길이""",
                    "examples": [
                        {
                            "input": "6\n10 9 2 5 3 7",
                            "output": "3",
                            "explanation": "[2, 5, 7] 또는 [2, 3, 7]이 최장 증가 수열 (길이 3)",
                        },
                        {
                            "input": "4\n7 7 7 7",
                            "output": "1",
                            "explanation": "모두 같으므로 길이 1",
                        },
                    ],
                    "test_cases": [
                        {"input": "6\n10 9 2 5 3 7", "expected": "3"},
                        {"input": "4\n7 7 7 7", "expected": "1"},
                        {"input": "8\n0 1 0 3 2 3 4 5", "expected": "6"},
                        {"input": "1\n5", "expected": "1"},
                    ],
                    "hints": [
                        "DP 배열을 사용하여 각 위치에서의 LIS 길이를 구하세요.",
                        "이진 탐색을 활용하면 O(n log n)으로 최적화할 수 있습니다.",
                    ],
                },
                {
                    "title": "동전 교환 (Coin Change)",
                    "description": """동전 종류와 목표 금액이 주어질 때, 목표 금액을 만들기 위한 최소 동전 수를 구하세요.
만들 수 없으면 -1을 출력하세요.

**입력 형식:**
- 첫 번째 줄: 동전 종류 수 n, 목표 금액 amount
- 두 번째 줄: n개의 동전 값어치 (공백으로 구분)

**출력 형식:**
- 최소 동전 수 (불가능하면 -1)""",
                    "examples": [
                        {
                            "input": "3 11\n1 5 6",
                            "output": "2",
                            "explanation": "6 + 5 = 11 (동전 2개)",
                        },
                        {
                            "input": "1 3\n2",
                            "output": "-1",
                            "explanation": "2로 3을 만들 수 없음",
                        },
                    ],
                    "test_cases": [
                        {"input": "3 11\n1 5 6", "expected": "2"},
                        {"input": "1 3\n2", "expected": "-1"},
                        {"input": "3 0\n1 2 5", "expected": "0"},
                        {"input": "2 7\n3 5", "expected": "-1"},
                        {"input": "3 6\n1 3 4", "expected": "2"},
                    ],
                    "hints": [
                        "보텀업 DP를 활용하세요.",
                        "dp[i] = 금액 i를 만드는 최소 동전 수",
                    ],
                },
                {
                    "title": "섬의 개수 (Number of Islands)",
                    "description": """‘0’(물)과 ‘1’(땅)로 이루어진 2D 그리드에서 섬의 개수를 구하세요.
섬은 상하좌우로 연결된 1들의 집합입니다.

**입력 형식:**
- 첫 번째 줄: 행 수 R, 열 수 C
- 다음 R줄: 0과 1로 이루어진 그리드 (공백으로 구분)

**출력 형식:**
- 섬의 개수""",
                    "examples": [
                        {
                            "input": "3 3\n1 1 0\n0 1 0\n0 0 1",
                            "output": "2",
                            "explanation": "왼쪽 상단 섬(1,1,1)과 우쪽 하단 섬(1) = 2개",
                        },
                        {
                            "input": "2 2\n0 0\n0 0",
                            "output": "0",
                            "explanation": "땅이 없으므로 섬 0개",
                        },
                    ],
                    "test_cases": [
                        {"input": "3 3\n1 1 0\n0 1 0\n0 0 1", "expected": "2"},
                        {"input": "2 2\n0 0\n0 0", "expected": "0"},
                        {"input": "1 5\n1 0 1 0 1", "expected": "3"},
                        {
                            "input": "4 4\n1 1 0 0\n1 1 0 0\n0 0 1 1\n0 0 1 1",
                            "expected": "2",
                        },
                    ],
                    "hints": [
                        "BFS 또는 DFS를 활용하여 연결된 영역을 탐색하세요.",
                        "방문한 칸은 0으로 표시하면 별도 visited 배열이 필요 없습니다.",
                    ],
                },
                {
                    "title": "계단 오르기 (Climbing Stairs)",
                    "description": """계단이 n개 있을 때, 한 번에 1계단 또는 2계단을 오를 수 있습니다.
꼭대기에 도달하는 방법의 수를 구하세요.

**입력 형식:**
- 정수 n

**출력 형식:**
- 방법의 수""",
                    "examples": [
                        {
                            "input": "3",
                            "output": "3",
                            "explanation": "1+1+1, 1+2, 2+1 = 3가지",
                        },
                        {"input": "5", "output": "8", "explanation": "8가지 방법"},
                    ],
                    "test_cases": [
                        {"input": "3", "expected": "3"},
                        {"input": "5", "expected": "8"},
                        {"input": "1", "expected": "1"},
                        {"input": "10", "expected": "89"},
                    ],
                    "hints": [
                        "피보나치 수열과 유사한 구조입니다.",
                        "dp[i] = dp[i-1] + dp[i-2]",
                    ],
                },
                {
                    "title": "배낭 문제 (0/1 Knapsack)",
                    "description": """무게 제한이 있는 배낭에 물건을 넣어 최대 가치를 구하세요.
각 물건은 하나만 선택 가능합니다.

**입력 형식:**
- 첫 번째 줄: 물건 수 n, 배낭 용량 W
- 다음 n줄: 각 물건의 무게와 가치 (공백으로 구분)

**출력 형식:**
- 최대 가치""",
                    "examples": [
                        {
                            "input": "3 4\n1 2\n2 4\n3 5",
                            "output": "6",
                            "explanation": "물건 1(무게1,가치2) + 물건 2(무게2,가치4) = 무게3, 가치6",
                        },
                        {
                            "input": "2 3\n2 3\n3 4",
                            "output": "3",
                            "explanation": "물건 1만 선택 (무게2, 가치3)",
                        },
                    ],
                    "test_cases": [
                        {"input": "3 4\n1 2\n2 4\n3 5", "expected": "6"},
                        {"input": "2 3\n2 3\n3 4", "expected": "3"},
                        {"input": "1 1\n2 3", "expected": "0"},
                        {"input": "4 7\n1 1\n3 4\n4 5\n5 7", "expected": "9"},
                    ],
                    "hints": [
                        "2차원 DP 테이블을 활용하세요.",
                        "dp[i][w] = i번째 물건까지 고려하고 용량 w일 때 최대 가치",
                    ],
                },
                {
                    "title": "최단 경로 (Dijkstra)",
                    "description": """가중치 그래프에서 시작 노드에서 도착 노드까지의 최단 거리를 구하세요.
도달할 수 없으면 -1을 출력하세요.

**입력 형식:**
- 첫 번째 줄: 노드 수 V, 간선 수 E
- 다음 E줄: 시작노드 도착노드 가중치 (공백으로 구분)
- 마지막 줄: 시작노드 도착노드

**출력 형식:**
- 최단 거리 (도달 불가 시 -1)""",
                    "examples": [
                        {
                            "input": "5 6\n1 2 2\n1 3 5\n2 3 1\n2 4 7\n3 4 3\n4 5 1\n1 5",
                            "output": "7",
                            "explanation": "1→2→3→4→5 = 2+1+3+1 = 7",
                        },
                    ],
                    "test_cases": [
                        {
                            "input": "5 6\n1 2 2\n1 3 5\n2 3 1\n2 4 7\n3 4 3\n4 5 1\n1 5",
                            "expected": "7",
                        },
                        {"input": "3 2\n1 2 3\n2 3 4\n1 3", "expected": "7"},
                        {"input": "2 0\n1 2", "expected": "-1"},
                        {"input": "3 3\n1 2 1\n2 3 2\n1 3 10\n1 3", "expected": "3"},
                    ],
                    "hints": [
                        "다익스트라 알고리즘을 활용하세요.",
                        "우선순위 큐(heapq)를 사용하면 O((V+E)logV)로 최적화됩니다.",
                    ],
                },
            ],
        }

        # 해당 난이도 문제 목록에서 랜덤 선택
        bank = problems_bank.get(difficulty, problems_bank["easy"])
        selected = random.choice(bank)

        problem_id = str(uuid.uuid4())[:8]
        problem = CodingProblem(
            id=problem_id,
            title=selected["title"],
            difficulty=difficulty,
            description=selected["description"],
            examples=selected["examples"],
            test_cases=selected["test_cases"],
            hints=selected.get("hints", []),
        )
        _generated_problems[problem_id] = problem
        return problem


# ========== 코드 실행 엔진 (보안 강화) ==========
class CodeExecutor:
    """Docker 격리 + 코드 검사 + 리소스 모니터링 기반 샌드박스 코드 실행"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.use_docker = DOCKER_AVAILABLE

    # ───── 메인 진입점 ─────

    def execute(self, code: str, language: str, stdin: str = "") -> CodeExecutionResult:
        """코드 실행 (보안 검사 → Docker 격리 또는 모니터링 서브프로세스)"""
        language = language.lower()

        if language not in SUPPORTED_LANGUAGES:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"지원하지 않는 언어입니다: {language}",
                execution_time=0,
            )

        # 1단계: 코드 보안 정적 검사 (모든 모드에서 실행)
        safe, error_msg = CodeSanitizer.sanitize(code, language)
        if not safe:
            return CodeExecutionResult(
                success=False, output="", error=error_msg, execution_time=0
            )

        # 2단계: Docker 사용 가능 → 컨테이너 격리 실행
        if self.use_docker:
            return self._execute_in_docker(code, language, stdin)

        # 3단계: Fallback → 모니터링 서브프로세스 실행
        dispatch = {
            "python": self._execute_python,
            "javascript": self._execute_javascript,
            "java": self._execute_java,
            "c": self._execute_c,
            "cpp": self._execute_cpp,
        }
        return dispatch[language](code, stdin)

    # ───── Docker 컨테이너 격리 실행 ─────

    def _execute_in_docker(
        self, code: str, language: str, stdin: str
    ) -> CodeExecutionResult:
        """
        Docker 컨테이너에서 완전 격리 실행.
        보안: --network none, --memory, --read-only, --cap-drop ALL,
              --security-opt no-new-privileges, --pids-limit, non-root user
        """
        # 언어별 파일명/컴파일/실행 설정
        lang_config = {
            "python": {
                "file": "solution.py",
                "compile": None,
                "run": "python3 solution.py",
            },
            "javascript": {
                "file": "solution.js",
                "compile": None,
                "run": "node solution.js",
            },
            "java": {
                "file": "Solution.java",
                "compile": "javac Solution.java",
                "run": "java Solution",
            },
            "c": {
                "file": "solution.c",
                "compile": "gcc solution.c -o solution -lm -O2",
                "run": "./solution",
            },
            "cpp": {
                "file": "solution.cpp",
                "compile": "g++ solution.cpp -o solution -std=c++17 -O2",
                "run": "./solution",
            },
        }

        # Java: 클래스 이름에 따라 파일명 조정
        if language == "java":
            class_match = re.search(r"public\s+class\s+(\w+)", code)
            class_name = class_match.group(1) if class_match else "Solution"
            lang_config["java"]["file"] = f"{class_name}.java"
            lang_config["java"]["compile"] = f"javac {class_name}.java"
            lang_config["java"]["run"] = f"java -Xmx{SANDBOX_MEMORY_MB}m {class_name}"

        # JavaScript: stdin 파이프 래핑
        if language == "javascript":
            code = self._wrap_js_stdin(code)

        # Python: 런타임 SafeImporter 래핑
        if language == "python":
            code = self._wrap_python_safe(code)

        cfg = lang_config[language]
        code_dir = tempfile.mkdtemp()

        try:
            # 코드 파일 + 입력 파일 작성
            code_path = os.path.join(code_dir, cfg["file"])
            input_path = os.path.join(code_dir, "input.txt")

            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code)
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(stdin)

            # Docker 명령 구성
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",  # 네트워크 격리
                "--memory",
                SANDBOX_MEMORY_LIMIT,  # 메모리 제한
                "--memory-swap",
                SANDBOX_MEMORY_LIMIT,  # 스왑 제한 (= 메모리만 사용)
                "--pids-limit",
                SANDBOX_PID_LIMIT,  # 프로세스 수 제한
                "--cpus",
                SANDBOX_CPU_LIMIT,  # CPU 제한
                "--read-only",  # 루트 파일시스템 읽기 전용
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",  # 임시 작업 공간
                "--security-opt",
                "no-new-privileges",  # 권한 상승 방지
                "--cap-drop",
                "ALL",  # 모든 커널 권한 박탈
                "--user",
                "sandbox",  # non-root 실행
                "-v",
                f"{code_dir}:/sandbox:ro",  # 코드 마운트 (읽기 전용)
                "-w",
                "/tmp",
                DOCKER_IMAGE,
            ]

            # 셸 명령: 코드 복사 → 컴파일(선택) → 실행
            shell_parts = [f"cp /sandbox/{cfg['file']} /tmp/"]
            if cfg["compile"]:
                shell_parts.append(cfg["compile"])
            shell_parts.append(
                f"timeout {MAX_EXECUTION_TIME} {cfg['run']} < /sandbox/input.txt"
            )
            shell_cmd = " && ".join(shell_parts)
            docker_cmd.extend(["bash", "-c", shell_cmd])

            start_time = time.time()
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME + 10,  # Docker 오버헤드 고려
            )
            execution_time = (time.time() - start_time) * 1000

            # Docker/Linux 종료 코드 해석
            if result.returncode == 137:  # OOM Killed
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"💾 메모리 초과: {SANDBOX_MEMORY_MB}MB 제한을 초과했습니다.",
                    execution_time=round(execution_time, 2),
                )
            if result.returncode == 124:  # timeout
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"⏱ 시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                    execution_time=round(execution_time, 2),
                )

            return CodeExecutionResult(
                success=result.returncode == 0,
                output=result.stdout.strip()[:MAX_OUTPUT_SIZE],
                error=result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None,
                execution_time=round(execution_time, 2),
            )

        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error="⏱ 시간 초과: Docker 실행 제한 시간을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000,
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"Docker 실행 오류: {str(e)}",
                execution_time=0,
            )
        finally:
            shutil.rmtree(code_dir, ignore_errors=True)

    # ───── 리소스 모니터링 서브프로세스 실행 ─────

    def _monitored_run(
        self,
        cmd: list,
        input: str = "",
        timeout: int = MAX_EXECUTION_TIME,
        cwd: Optional[str] = None,
    ) -> _RunResult:
        """
        리소스 모니터링이 적용된 서브프로세스 실행.
        - psutil 기반 메모리 모니터링 (설치 시)
        - 시간 제한 (timeout)
        - 프로세스 트리 정리
        """
        start_time = time.time()

        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd or self.temp_dir,
            creationflags=creation_flags,
        )

        memory_exceeded = threading.Event()
        max_memory = [0.0]

        def _monitor_memory():
            """백그라운드 메모리 모니터링 스레드"""
            try:
                import psutil

                ps_proc = psutil.Process(proc.pid)
                while proc.poll() is None and not memory_exceeded.is_set():
                    try:
                        mem_info = ps_proc.memory_info()
                        mem_mb = mem_info.rss / (1024 * 1024)
                        max_memory[0] = max(max_memory[0], mem_mb)
                        if mem_mb > SANDBOX_MEMORY_MB:
                            memory_exceeded.set()
                            # 프로세스 트리 전체 종료
                            for child in ps_proc.children(recursive=True):
                                try:
                                    child.kill()
                                except psutil.NoSuchProcess:
                                    pass
                            proc.kill()
                            return
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return
                    time.sleep(0.1)
            except ImportError:
                pass  # psutil 미설치 시 메모리 모니터링 스킵

        monitor_thread = threading.Thread(target=_monitor_memory, daemon=True)
        monitor_thread.start()

        try:
            stdout, stderr = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=3)
            except Exception:
                stdout, stderr = "", ""
            return _RunResult(
                returncode=-1,
                stdout="",
                stderr="",
                execution_time_ms=(time.time() - start_time) * 1000,
                memory_mb=max_memory[0],
                timed_out=True,
                memory_exceeded=False,
            )

        monitor_thread.join(timeout=1)
        execution_time_ms = (time.time() - start_time) * 1000

        if memory_exceeded.is_set():
            return _RunResult(
                returncode=-1,
                stdout="",
                stderr="",
                execution_time_ms=execution_time_ms,
                memory_mb=max_memory[0],
                timed_out=False,
                memory_exceeded=True,
            )

        return _RunResult(
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            execution_time_ms=execution_time_ms,
            memory_mb=max_memory[0],
            timed_out=False,
            memory_exceeded=False,
        )

    def _result_from_run(self, run: _RunResult) -> CodeExecutionResult:
        """_RunResult → CodeExecutionResult 변환"""
        if run.timed_out:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"⏱ 시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=round(run.execution_time_ms, 2),
                memory_usage=run.memory_mb if run.memory_mb > 0 else None,
            )
        if run.memory_exceeded:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"💾 메모리 초과: {SANDBOX_MEMORY_MB}MB 제한 초과 (사용: {run.memory_mb:.1f}MB)",
                execution_time=round(run.execution_time_ms, 2),
                memory_usage=run.memory_mb,
            )
        return CodeExecutionResult(
            success=run.returncode == 0,
            output=run.stdout.strip()[:MAX_OUTPUT_SIZE],
            error=run.stderr[:MAX_OUTPUT_SIZE] if run.stderr else None,
            execution_time=round(run.execution_time_ms, 2),
            memory_usage=run.memory_mb if run.memory_mb > 0 else None,
        )

    # ───── 코드 보안 래핑 헬퍼 ─────

    @staticmethod
    def _wrap_python_safe(code: str) -> str:
        """Python 런타임 SafeImporter 래핑 (defense in depth)"""
        return f"""
import sys

# 위험한 모듈, 서브모듈 런타임 차단
_BLOCKED = frozenset([
    'os', 'subprocess', 'shutil', 'socket', 'requests', 'urllib',
    'http', 'ftplib', 'ctypes', 'cffi', 'multiprocessing', 'signal',
    'importlib', 'pathlib', 'glob', 'tempfile', 'webbrowser',
])

class _Guard:
    def find_module(self, name, path=None):
        top = name.split('.')[0]
        if top in _BLOCKED:
            raise ImportError(f"보안상 '{{name}}' 모듈은 사용할 수 없습니다.")
        return None

sys.meta_path.insert(0, _Guard())

{code}
"""

    @staticmethod
    def _wrap_js_stdin(code: str) -> str:
        """JavaScript stdin 파이프 래핑 (코드 인젝션 방지)"""
        return f"""
"use strict";
const _rl = require('readline');
const _iface = _rl.createInterface({{ input: process.stdin, terminal: false }});
const _lines = [];
_iface.on('line', l => _lines.push(l));
_iface.on('close', () => {{
    let _idx = 0;
    globalThis.input = () => _lines[_idx++] || '';
    {code}
}});
"""

    # ───── 서브프로세스 Fallback: 언어별 실행 ─────

    def _execute_python(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """Python 실행 (SafeImporter + 메모리 모니터링)"""
        file_path = os.path.join(self.temp_dir, "solution.py")
        safe_code = self._wrap_python_safe(code)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(safe_code)

        try:
            run = self._monitored_run([sys.executable, file_path], input=stdin)
            return self._result_from_run(run)
        except Exception as e:
            return CodeExecutionResult(
                success=False, output="", error=str(e), execution_time=0
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    def _execute_javascript(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """JavaScript 실행 (stdin 파이프 + 메모리 모니터링)"""
        file_path = os.path.join(self.temp_dir, "solution.js")
        wrapped_code = self._wrap_js_stdin(code)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(wrapped_code)

        try:
            run = self._monitored_run(["node", file_path], input=stdin)
            return self._result_from_run(run)
        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="Node.js가 설치되어 있지 않습니다.",
                execution_time=0,
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False, output="", error=str(e), execution_time=0
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    def _execute_java(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """Java 실행 (Xmx 메모리 제한 + 메모리 모니터링)"""
        class_match = re.search(r"public\s+class\s+(\w+)", code)
        class_name = class_match.group(1) if class_match else "Solution"
        file_path = os.path.join(self.temp_dir, f"{class_name}.java")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            # 컴파일
            compile_result = subprocess.run(
                ["javac", file_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir,
            )
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0,
                )

            # 실행 (Xmx로 JVM 메모리 제한 + 모니터링)
            run = self._monitored_run(
                ["java", f"-Xmx{SANDBOX_MEMORY_MB}m", "-cp", self.temp_dir, class_name],
                input=stdin,
            )
            return self._result_from_run(run)

        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="Java가 설치되어 있지 않습니다.",
                execution_time=0,
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False, output="", error=str(e), execution_time=0
            )
        finally:
            for ext in [".java", ".class"]:
                path = os.path.join(self.temp_dir, f"{class_name}{ext}")
                if os.path.exists(path):
                    os.remove(path)

    def _execute_c(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """C 실행 (gcc 컴파일 + 메모리 모니터링)"""
        source_path = os.path.join(self.temp_dir, "solution.c")
        exe_path = os.path.join(
            self.temp_dir, "solution.exe" if os.name == "nt" else "solution"
        )

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            compile_result = subprocess.run(
                ["gcc", source_path, "-o", exe_path, "-lm", "-O2"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir,
            )
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0,
                )

            run = self._monitored_run([exe_path], input=stdin)
            return self._result_from_run(run)

        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="GCC가 설치되어 있지 않습니다. MinGW 또는 GCC를 설치해주세요.",
                execution_time=0,
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False, output="", error=str(e), execution_time=0
            )
        finally:
            for p in (source_path, exe_path):
                if os.path.exists(p):
                    os.remove(p)

    def _execute_cpp(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """C++ 실행 (g++ 컴파일 + 메모리 모니터링)"""
        source_path = os.path.join(self.temp_dir, "solution.cpp")
        exe_path = os.path.join(
            self.temp_dir, "solution.exe" if os.name == "nt" else "solution"
        )

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            compile_result = subprocess.run(
                ["g++", source_path, "-o", exe_path, "-std=c++17", "-O2"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir,
            )
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0,
                )

            run = self._monitored_run([exe_path], input=stdin)
            return self._result_from_run(run)

        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="G++가 설치되어 있지 않습니다. MinGW 또는 G++를 설치해주세요.",
                execution_time=0,
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False, output="", error=str(e), execution_time=0
            )
        finally:
            for p in (source_path, exe_path):
                if os.path.exists(p):
                    os.remove(p)


# ========== AI 코드 분석기 ==========
class CodeAnalyzer:
    """AI 기반 코드 품질 분석"""

    CODE_ANALYSIS_PROMPT = """당신은 시니어 소프트웨어 엔지니어이자 기술 면접관입니다.
제출된 코드를 종합적으로 분석하고 평가해주세요.

[평가 항목]
1. 정확성 (25점): 테스트 케이스 통과 여부
2. 시간 복잡도 (20점): 알고리즘 효율성 (Big-O 표기법)
3. 공간 복잡도 (15점): 메모리 사용 효율성
4. 코드 스타일 (20점): 가독성, 변수명, 들여쓰기, 일관성
5. 주석 및 문서화 (10점): 코드 설명, 주석 품질
6. 모범 사례 (10점): 언어별 관례, 에러 처리, 엣지 케이스 고려

[출력 형식 - 반드시 JSON으로 응답]
{{
    "overall_score": 0-100,
    "correctness": {{
        "score": 0-25,
        "passed_tests": 0,
        "total_tests": 0,
        "feedback": "정확성 피드백"
    }},
    "time_complexity": {{
        "score": 0-20,
        "estimated": "O(?)",
        "optimal": "O(?)",
        "feedback": "시간 복잡도 분석"
    }},
    "space_complexity": {{
        "score": 0-15,
        "estimated": "O(?)",
        "feedback": "공간 복잡도 분석"
    }},
    "code_style": {{
        "score": 0-20,
        "issues": ["이슈1", "이슈2"],
        "feedback": "스타일 피드백"
    }},
    "comments": {{
        "score": 0-10,
        "has_comments": true/false,
        "quality": "good/fair/poor",
        "feedback": "주석 피드백"
    }},
    "best_practices": {{
        "score": 0-10,
        "followed": ["따른 사례"],
        "missing": ["누락된 사례"],
        "feedback": "모범 사례 피드백"
    }},
    "feedback": ["종합 개선 제안1", "종합 개선 제안2", "종합 개선 제안3"],
    "detailed_analysis": "상세 분석 내용 (2-3문단)"
}}"""

    def __init__(self):
        self.llm = None
        if LLM_AVAILABLE:
            try:
                self.llm = ChatOllama(
                    model=CODING_LLM_MODEL,  # 코딩 테스트 전용 경량 모델 (qwen3:1.7b)
                    temperature=0.3,
                    num_ctx=CODING_LLM_NUM_CTX,  # 코딩 분석은 4096 컨텍스트면 충분
                    num_predict=2048,  # 최대 생성 토큰 수 제한 (분석 JSON ~1500토큰)
                )
            except Exception as e:
                print(f"⚠️ CodeAnalyzer LLM 초기화 실패: {e}")

    async def analyze(
        self,
        code: str,
        language: str,
        problem: Optional[CodingProblem],
        execution_results: List[Dict],
    ) -> CodeAnalysisResult:
        """코드 종합 분석"""

        # 테스트 결과 요약
        passed = sum(1 for r in execution_results if r.get("passed", False))
        total = len(execution_results)

        # LLM 분석
        if self.llm:
            try:
                analysis = await self._llm_analyze(
                    code, language, problem, execution_results
                )
                return analysis
            except Exception as e:
                print(f"LLM 분석 오류: {e}")

        # LLM 없으면 기본 분석
        return self._basic_analyze(code, language, passed, total)

    async def _llm_analyze(
        self,
        code: str,
        language: str,
        problem: Optional[CodingProblem],
        execution_results: List[Dict],
    ) -> CodeAnalysisResult:
        """LLM 기반 상세 분석"""

        # 문제 정보 구성
        problem_info = ""
        if problem:
            problem_info = f"""
[문제 정보]
제목: {problem.title}
난이도: {problem.difficulty}
설명: {problem.description}
"""

        # 테스트 결과 구성
        test_results = "\n".join(
            [
                f"- 테스트 {i + 1}: {'통과 ✓' if r.get('passed') else '실패 ✗'} "
                f"(실행시간: {r.get('execution_time', 0):.2f}ms)"
                for i, r in enumerate(execution_results)
            ]
        )

        messages = [
            SystemMessage(content=self.CODE_ANALYSIS_PROMPT),
            HumanMessage(
                content=f"""
{problem_info}

[제출된 코드 - {language}]
```{language}
{code}
```

[테스트 결과]
{test_results}

위 코드를 종합적으로 분석하고 JSON 형식으로 평가해주세요.
"""
            ),
        ]

        # asyncio.to_thread로 LLM 호출을 별도 스레드에서 실행하여 이벤트 루프 블로킹 방지
        # wait_for로 120초 타임아웃을 설정하여 무한 대기 방지
        response = await asyncio.wait_for(
            asyncio.to_thread(self.llm.invoke, messages),
            timeout=120,
        )
        response_text = response.content

        # <think> 태그 제거 (Qwen 모델 — 열림/닫힘 쌍 및 단독 닫힘 태그 모두 제거)
        response_text = re.sub(
            r"<think>.*?</think>", "", response_text, flags=re.DOTALL
        ).strip()
        response_text = re.sub(r"</think>", "", response_text).strip()

        # JSON Resilience 파싱
        analysis = parse_code_analysis_json(
            response_text, context="CodeAnalyzer.analyze_code"
        )

        return CodeAnalysisResult(
            overall_score=analysis.get("overall_score", 0),
            correctness=analysis.get("correctness", {}),
            time_complexity=analysis.get("time_complexity", {}),
            space_complexity=analysis.get("space_complexity", {}),
            code_style=analysis.get("code_style", {}),
            comments=analysis.get("comments", {}),
            best_practices=analysis.get("best_practices", {}),
            feedback=analysis.get("feedback", []),
            detailed_analysis=analysis.get("detailed_analysis", ""),
        )

    def _basic_analyze(
        self, code: str, language: str, passed: int, total: int
    ) -> CodeAnalysisResult:
        """기본 코드 분석 (LLM 없이)"""

        # 정확성 점수
        correctness_score = int((passed / total) * 25) if total > 0 else 0

        # 코드 스타일 분석
        lines = code.split("\n")
        has_comments = any(
            "#" in line or "//" in line or "/*" in line for line in lines
        )
        avg_line_length = sum(len(line) for line in lines) / len(lines) if lines else 0

        style_score = 15
        style_issues = []

        if avg_line_length > 100:
            style_score -= 5
            style_issues.append("줄 길이가 너무 깁니다 (100자 이하 권장)")

        if not has_comments:
            style_issues.append("주석이 없습니다")

        # 주석 점수
        comment_score = 8 if has_comments else 3

        # 종합 점수
        overall = correctness_score + 15 + 10 + style_score + comment_score + 7

        return CodeAnalysisResult(
            overall_score=min(100, overall),
            correctness={
                "score": correctness_score,
                "passed_tests": passed,
                "total_tests": total,
                "feedback": f"{passed}/{total} 테스트 케이스 통과",
            },
            time_complexity={
                "score": 15,
                "estimated": "분석 필요",
                "optimal": "문제에 따라 다름",
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다.",
            },
            space_complexity={
                "score": 10,
                "estimated": "분석 필요",
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다.",
            },
            code_style={
                "score": style_score,
                "issues": style_issues,
                "feedback": "코드 스타일이 양호합니다."
                if not style_issues
                else "개선이 필요합니다.",
            },
            comments={
                "score": comment_score,
                "has_comments": has_comments,
                "quality": "fair" if has_comments else "poor",
                "feedback": "주석이 있습니다."
                if has_comments
                else "주석을 추가하세요.",
            },
            best_practices={
                "score": 7,
                "followed": [],
                "missing": [],
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다.",
            },
            feedback=[
                "테스트 케이스를 모두 통과하도록 코드를 수정하세요."
                if passed < total
                else "모든 테스트를 통과했습니다!",
                "주석을 추가하여 코드 가독성을 높이세요."
                if not has_comments
                else "주석이 잘 작성되어 있습니다.",
            ],
            detailed_analysis="기본 분석이 완료되었습니다. LLM을 활성화하면 더 상세한 분석을 받을 수 있습니다.",
        )


# ========== 스마트 출력 비교 ==========
# 부동소수점 오차 허용 범위 (절대·상대)
_FLOAT_ABS_TOL = 1e-6
_FLOAT_REL_TOL = 1e-9


def _is_float(s: str) -> bool:
    """문자열이 부동소수점 숫자인지 판별"""
    try:
        float(s)
        return True
    except ValueError:
        return False


def _tokens_match(tok_a: str, tok_b: str) -> bool:
    """토큰 단위 비교: 부동소수점이면 오차 허용, 아니면 정확 비교"""
    if tok_a == tok_b:
        return True
    if _is_float(tok_a) and _is_float(tok_b):
        fa, fb = float(tok_a), float(tok_b)
        # 절대 오차 또는 상대 오차 중 하나라도 통과하면 OK
        if abs(fa - fb) <= _FLOAT_ABS_TOL:
            return True
        if fb != 0 and abs((fa - fb) / fb) <= _FLOAT_REL_TOL:
            return True
    return False


def _smart_compare(actual: str, expected: str) -> bool:
    """
    스마트 출력 비교:
    1. Trim & Clean — 각 줄의 trailing whitespace 제거, 빈 줄 무시
    2. Line-by-Line — 줄 단위로 비교하여 메모리 효율적
    3. 부동소수점 오차 허용 — 토큰별 float 판별 후 ±1e-6 허용
    """
    # 줄 분리 → trailing whitespace 제거 → 빈 줄 스킵
    a_lines = [ln.rstrip() for ln in actual.splitlines() if ln.strip()]
    e_lines = [ln.rstrip() for ln in expected.splitlines() if ln.strip()]

    if len(a_lines) != len(e_lines):
        return False

    for a_line, e_line in zip(a_lines, e_lines):
        # 빠른 경로: 줄 전체가 동일하면 통과
        if a_line == e_line:
            continue
        # 토큰 분리 비교 (공백 기준)
        a_tokens = a_line.split()
        e_tokens = e_line.split()
        if len(a_tokens) != len(e_tokens):
            return False
        for at, et in zip(a_tokens, e_tokens):
            if not _tokens_match(at, et):
                return False

    return True


# ========== 코드 실행 서비스 ==========
class CodeExecutionService:
    """코드 실행 및 분석 통합 서비스"""

    def __init__(self):
        self.executor = CodeExecutor()
        self.analyzer = CodeAnalyzer()

    async def run_and_analyze(
        self,
        code: str,
        language: str,
        problem_id: Optional[str] = None,
        custom_test_cases: Optional[List[Dict]] = None,
    ) -> Dict:
        """코드 실행 및 분석"""

        # 문제 가져오기 (캐시에서 조회)
        problem = _generated_problems.get(problem_id) if problem_id else None

        # 테스트 케이스 결정
        test_cases = custom_test_cases or (problem.test_cases if problem else [])

        if not test_cases:
            # 테스트 케이스 없으면 단순 실행
            result = self.executor.execute(code, language, "")
            return {"execution": result.dict(), "analysis": None, "test_results": []}

        # 각 테스트 케이스를 병렬로 실행 (asyncio.gather + to_thread)
        # 순차 실행 대비 테스트 케이스 수만큼 실행 시간 단축
        async def _run_single_test(i: int, tc: Dict) -> Dict:
            """단일 테스트 케이스를 별도 스레드에서 실행하고 결과를 반환합니다."""
            result = await asyncio.to_thread(
                self.executor.execute, code, language, tc.get("input", "")
            )
            expected = tc.get("expected", "").strip()
            actual = result.output.strip()
            passed = _smart_compare(actual, expected)
            return {
                "test_id": i + 1,
                "input": tc.get("input", "")[:100]
                + ("..." if len(tc.get("input", "")) > 100 else ""),
                "expected": expected[:100],
                "actual": actual[:100],
                "passed": passed,
                "execution_time": result.execution_time,
                "error": result.error,
            }

        test_results = await asyncio.gather(
            *[_run_single_test(i, tc) for i, tc in enumerate(test_cases)]
        )
        test_results = list(test_results)  # tuple → list 변환

        # AI 분석
        analysis = await self.analyzer.analyze(code, language, problem, test_results)

        return {
            "problem": problem.dict() if problem else None,
            "test_results": test_results,
            "analysis": analysis.dict(),
            "summary": {
                "passed": sum(1 for r in test_results if r["passed"]),
                "total": len(test_results),
                "overall_score": analysis.overall_score,
                "avg_execution_time": sum(r["execution_time"] for r in test_results)
                / len(test_results)
                if test_results
                else 0,
            },
        }


# ========== FastAPI 라우터 ==========
def create_coding_router():
    """코딩 테스트 API 라우터"""

    router = APIRouter(prefix="/api/coding", tags=["Coding Test"])
    service = CodeExecutionService()
    generator = CodingProblemGenerator()

    @router.get("/generate")
    async def generate_problem(difficulty: str = "medium"):
        """
        코딩 문제 1개를 반환합니다.

        1순위: Redis 문제 풀(pool)에서 즉시 꺼냄 (체감 0초)
        2순위: 풀이 비었으면 LLM 직접 호출 (50~90초)
        3순위: LLM도 실패하면 fallback 기본 문제

        풀에서 꺼낸 후 남은 수가 부족하면 Celery로 자동 보충합니다.
        """
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        # 1순위: Redis 풀에서 즉시 반환
        pooled = problem_pool.pop(difficulty)
        if pooled:
            print(
                f"[CodingRouter] 풀에서 즉시 반환: {pooled.title} (남은 수: {problem_pool.count(difficulty)})"
            )
            # 풀 부족 시 백그라운드 보충
            if problem_pool.needs_refill(difficulty):
                trigger_pool_refill(difficulty)
            public_problem = pooled.dict()
            public_problem["test_cases"] = pooled.test_cases[:2]
            return public_problem

        # 2순위: 풀이 비었으므로 LLM 직접 호출
        print(f"[CodingRouter] 풀 비어있음 — LLM 직접 생성 ({difficulty})")
        problem = await generator.generate(difficulty)

        # 백그라운드 보충도 함께 발행
        trigger_pool_refill(difficulty)

        # 테스트 케이스는 일부만 공개
        public_problem = problem.dict()
        public_problem["test_cases"] = problem.test_cases[:2]
        return public_problem

    @router.get("/problems/{problem_id}")
    async def get_problem(problem_id: str):
        """캐시된 문제 상세 조회"""
        problem = _generated_problems.get(problem_id)
        if not problem:
            raise HTTPException(
                status_code=404,
                detail="문제를 찾을 수 없습니다. 새 문제를 생성해주세요.",
            )

        # 테스트 케이스는 일부만 공개
        public_problem = problem.dict()
        public_problem["test_cases"] = problem.test_cases[:2]
        return public_problem

    @router.post("/execute")
    async def execute_code(request: CodeExecutionRequest):
        """코드 실행"""
        if request.language.lower() not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 언어입니다. 지원 언어: {SUPPORTED_LANGUAGES}",
            )

        result = await service.run_and_analyze(
            code=request.code,
            language=request.language,
            problem_id=request.problem_id,
            custom_test_cases=request.test_cases,
        )

        return result

    @router.post("/run")
    async def run_code_simple(request: CodeExecutionRequest):
        """단순 코드 실행 (분석 없이, stdin 지원)"""
        executor = CodeExecutor()
        result = executor.execute(request.code, request.language, request.stdin or "")
        return result.dict()

    @router.post("/submit")
    async def submit_code(request: CodeExecutionRequest):
        """코드 제출 (실행 + 분석 + 테스트케이스 평가)"""
        if request.language.lower() not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 언어입니다. 지원 언어: {SUPPORTED_LANGUAGES}",
            )
        result = await service.run_and_analyze(
            code=request.code,
            language=request.language,
            problem_id=request.problem_id,
            custom_test_cases=request.test_cases,
        )
        return result

    @router.get("/templates/{language}")
    async def get_template(language: str, problem_id: Optional[str] = None):
        """언어별 코드 템플릿"""
        templates = {
            "python": """# Python 솔루션
# 입력 받기
n = int(input())
nums = list(map(int, input().split()))
target = int(input())

# 여기에 솔루션을 작성하세요
def solution(nums, target):
    # TODO: 구현
    pass

# 결과 출력
result = solution(nums, target)
print(result)
""",
            "javascript": """// JavaScript 솔루션
// 입력 받기
const n = parseInt(input());
const nums = input().split(' ').map(Number);
const target = parseInt(input());

// 여기에 솔루션을 작성하세요
function solution(nums, target) {
    // TODO: 구현
}

// 결과 출력
const result = solution(nums, target);
console.log(result);
""",
            "java": """import java.util.*;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        
        // 입력 받기
        int n = sc.nextInt();
        int[] nums = new int[n];
        for (int i = 0; i < n; i++) {
            nums[i] = sc.nextInt();
        }
        int target = sc.nextInt();
        
        // 솔루션 실행
        int[] result = solution(nums, target);
        
        // 결과 출력
        System.out.println(result[0] + " " + result[1]);
    }
    
    public static int[] solution(int[] nums, int target) {
        // TODO: 구현
        return new int[]{0, 1};
    }
}
""",
            "c": """#include <stdio.h>
#include <stdlib.h>

// C 솔루션
int main() {
    int n, target;
    
    // 입력 받기
    scanf("%d", &n);
    int* nums = (int*)malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) {
        scanf("%d", &nums[i]);
    }
    scanf("%d", &target);
    
    // TODO: 솔루션 구현
    int result1 = 0, result2 = 1;
    
    // 결과 출력
    printf("%d %d\\n", result1, result2);
    
    free(nums);
    return 0;
}
""",
            "cpp": """#include <iostream>
#include <vector>
#include <unordered_map>
using namespace std;

// C++ 솔루션
int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    int n, target;
    
    // 입력 받기
    cin >> n;
    vector<int> nums(n);
    for (int i = 0; i < n; i++) {
        cin >> nums[i];
    }
    cin >> target;
    
    // TODO: 솔루션 구현
    int result1 = 0, result2 = 1;
    
    // 결과 출력
    cout << result1 << " " << result2 << endl;
    
    return 0;
}
""",
        }

        return {
            "language": language,
            "template": templates.get(language.lower(), "// 템플릿 없음"),
        }

    return router


# 테스트용
if __name__ == "__main__":
    import asyncio

    async def test():
        # LLM 문제 생성 테스트
        generator = CodingProblemGenerator()
        problem = await generator.generate("easy")
        print("=== 생성된 문제 ===")
        print(json.dumps(problem.dict(), indent=2, ensure_ascii=False))

        # 코드 실행 테스트
        service = CodeExecutionService()
        code = """
n = int(input())
nums = list(map(int, input().split()))
target = int(input())

def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

result = two_sum(nums, target)
print(result[0], result[1])
"""

        result = await service.run_and_analyze(code, "python", problem.id)
        print("\n=== 실행 결과 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(test())
