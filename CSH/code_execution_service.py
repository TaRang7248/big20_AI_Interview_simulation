"""
코드 실행 및 AI 분석 서비스
============================
면접 코딩 테스트를 위한 샌드박스 코드 실행 및 AI 기반 코드 분석

기능:
1. Python, JavaScript, Java, C, C++ 코드 실행 (샌드박스)
2. 실행 시간 및 메모리 측정
3. AI 기반 코드 품질 분석 (시간 복잡도, 스타일, 주석 등)
4. LLM 자동 코딩 문제 생성 (1회 1문제)
"""

import os
import sys
import subprocess
import tempfile
import time
import re
import json
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# .env 파일에서 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# JSON Resilience 유틸리티
from json_utils import parse_code_analysis_json

# FastAPI
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# LLM for code analysis
try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


# ========== 설정 ==========
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
DEFAULT_LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "16384"))
MAX_EXECUTION_TIME = 10  # 초
MAX_OUTPUT_SIZE = 10000  # 문자
SUPPORTED_LANGUAGES = ["python", "javascript", "java", "c", "cpp"]


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


class CodingProblemGenerator:
    """LLM 기반 코딩 문제 자동 생성기"""

    def __init__(self):
        if LLM_AVAILABLE:
            self.llm = ChatOllama(
                model=DEFAULT_LLM_MODEL,
                temperature=0.8,  # 다양한 문제 생성을 위해 높은 temperature
                num_ctx=DEFAULT_LLM_NUM_CTX,
            )
        else:
            self.llm = None

    async def generate(self, difficulty: str = "medium") -> CodingProblem:
        """LLM을 사용하여 코딩 문제 1개를 생성합니다."""
        if not self.llm:
            return self._fallback_problem(difficulty)

        try:
            prompt = PROBLEM_GENERATION_PROMPT.format(difficulty=difficulty)
            response = await asyncio.to_thread(
                self.llm.invoke,
                [
                    SystemMessage(content="당신은 코딩 면접 문제 출제 전문가입니다. JSON 형식으로만 응답하세요."),
                    HumanMessage(content=prompt),
                ]
            )
            raw = response.content.strip()

            # <think> 태그 제거 (Qwen 모델)
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

            # JSON 파싱 (json_utils 활용)
            parsed = parse_code_analysis_json(raw)
            if not parsed:
                # 직접 JSON 추출 시도
                json_match = re.search(r'\{[\s\S]*\}', raw)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    print(f"[CodingProblemGenerator] JSON 파싱 실패, fallback 사용")
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
            print(f"[CodingProblemGenerator] 문제 생성 완료: {problem.title} (ID: {problem_id})")
            return problem

        except Exception as e:
            print(f"[CodingProblemGenerator] 문제 생성 실패: {e}")
            return self._fallback_problem(difficulty)

    def _fallback_problem(self, difficulty: str = "easy") -> CodingProblem:
        """LLM 사용 불가 시 기본 문제 반환"""
        problem_id = str(uuid.uuid4())[:8]
        problem = CodingProblem(
            id=problem_id,
            title="두 수의 합 (Two Sum)",
            difficulty=difficulty,
            description="""정수 배열 nums와 정수 target이 주어집니다.
nums에서 두 수를 선택하여 더한 값이 target이 되는 두 수의 인덱스를 반환하세요.

각 입력에는 정확히 하나의 해답이 있다고 가정하며, 같은 요소를 두 번 사용할 수 없습니다.

**입력 형식:**
- 첫 번째 줄: 배열의 크기 n
- 두 번째 줄: n개의 정수 (공백으로 구분)
- 세 번째 줄: target 값

**출력 형식:**
- 두 인덱스를 공백으로 구분하여 출력""",
            examples=[
                {"input": "4\n2 7 11 15\n9", "output": "0 1", "explanation": "nums[0] + nums[1] = 2 + 7 = 9"},
                {"input": "3\n3 2 4\n6", "output": "1 2", "explanation": "nums[1] + nums[2] = 2 + 4 = 6"},
            ],
            test_cases=[
                {"input": "4\n2 7 11 15\n9", "expected": "0 1"},
                {"input": "3\n3 2 4\n6", "expected": "1 2"},
                {"input": "2\n3 3\n6", "expected": "0 1"},
                {"input": "5\n1 5 3 7 2\n9", "expected": "1 3"},
            ],
            hints=["해시맵을 사용하면 O(n) 시간 복잡도로 해결할 수 있습니다."],
        )
        _generated_problems[problem_id] = problem
        return problem


# ========== 코드 실행 엔진 ==========
class CodeExecutor:
    """샌드박스 환경에서 코드 실행"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def execute(self, code: str, language: str, stdin: str = "") -> CodeExecutionResult:
        """코드 실행"""
        language = language.lower()
        
        if language == "python":
            return self._execute_python(code, stdin)
        elif language == "javascript":
            return self._execute_javascript(code, stdin)
        elif language == "java":
            return self._execute_java(code, stdin)
        elif language == "c":
            return self._execute_c(code, stdin)
        elif language == "cpp":
            return self._execute_cpp(code, stdin)
        else:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"지원하지 않는 언어입니다: {language}",
                execution_time=0
            )
    
    def _execute_python(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """Python 코드 실행"""
        # 임시 파일 생성
        file_path = os.path.join(self.temp_dir, "solution.py")
        
        # 보안을 위한 코드 래핑
        safe_code = f'''
import sys
import io
from contextlib import redirect_stdout, redirect_stderr

# 위험한 모듈 제한
BLOCKED_MODULES = ['os', 'subprocess', 'shutil', 'socket', 'requests']

class SafeImporter:
    def find_module(self, name, path=None):
        if name in BLOCKED_MODULES:
            raise ImportError(f"모듈 '{{name}}'은(는) 보안상 사용할 수 없습니다.")
        return None

sys.meta_path.insert(0, SafeImporter())

# 사용자 코드 실행
{code}
'''
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(safe_code)
        
        try:
            start_time = time.time()
            
            result = subprocess.run(
                [sys.executable, file_path],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=self.temp_dir
            )
            
            execution_time = (time.time() - start_time) * 1000  # ms
            
            output = result.stdout[:MAX_OUTPUT_SIZE]
            error = result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None
            
            return CodeExecutionResult(
                success=result.returncode == 0,
                output=output.strip(),
                error=error,
                execution_time=round(execution_time, 2)
            )
            
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=0
            )
        finally:
            # 임시 파일 삭제
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def _execute_javascript(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """JavaScript 코드 실행 (Node.js 필요)"""
        file_path = os.path.join(self.temp_dir, "solution.js")
        
        # stdin 처리를 위한 코드 래핑
        wrapped_code = f'''
const readline = require('readline');
const inputLines = `{stdin}`.trim().split('\\n');
let lineIndex = 0;

function input() {{
    return inputLines[lineIndex++] || '';
}}

// 사용자 코드
{code}
'''
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(wrapped_code)
        
        try:
            start_time = time.time()
            
            result = subprocess.run(
                ['node', file_path],
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=self.temp_dir
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return CodeExecutionResult(
                success=result.returncode == 0,
                output=result.stdout.strip()[:MAX_OUTPUT_SIZE],
                error=result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None,
                execution_time=round(execution_time, 2)
            )
            
        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="Node.js가 설치되어 있지 않습니다.",
                execution_time=0
            )
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=0
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def _execute_java(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """Java 코드 실행"""
        # 클래스 이름 추출
        class_match = re.search(r'public\s+class\s+(\w+)', code)
        class_name = class_match.group(1) if class_match else "Solution"
        
        file_path = os.path.join(self.temp_dir, f"{class_name}.java")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        try:
            # 컴파일
            compile_result = subprocess.run(
                ['javac', file_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir
            )
            
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0
                )
            
            # 실행
            start_time = time.time()
            
            result = subprocess.run(
                ['java', '-cp', self.temp_dir, class_name],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=self.temp_dir
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return CodeExecutionResult(
                success=result.returncode == 0,
                output=result.stdout.strip()[:MAX_OUTPUT_SIZE],
                error=result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None,
                execution_time=round(execution_time, 2)
            )
            
        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="Java가 설치되어 있지 않습니다.",
                execution_time=0
            )
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=0
            )
        finally:
            # 정리
            for ext in ['.java', '.class']:
                path = os.path.join(self.temp_dir, f"{class_name}{ext}")
                if os.path.exists(path):
                    os.remove(path)
    
    def _execute_c(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """C 코드 실행"""
        source_path = os.path.join(self.temp_dir, "solution.c")
        exe_path = os.path.join(self.temp_dir, "solution.exe" if os.name == 'nt' else "solution")
        
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        try:
            # 컴파일
            compile_result = subprocess.run(
                ['gcc', source_path, '-o', exe_path, '-lm'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir
            )
            
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0
                )
            
            # 실행
            start_time = time.time()
            
            result = subprocess.run(
                [exe_path],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=self.temp_dir
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return CodeExecutionResult(
                success=result.returncode == 0,
                output=result.stdout.strip()[:MAX_OUTPUT_SIZE],
                error=result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None,
                execution_time=round(execution_time, 2)
            )
            
        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="GCC가 설치되어 있지 않습니다. MinGW 또는 GCC를 설치해주세요.",
                execution_time=0
            )
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=0
            )
        finally:
            # 정리
            if os.path.exists(source_path):
                os.remove(source_path)
            if os.path.exists(exe_path):
                os.remove(exe_path)
    
    def _execute_cpp(self, code: str, stdin: str = "") -> CodeExecutionResult:
        """C++ 코드 실행"""
        source_path = os.path.join(self.temp_dir, "solution.cpp")
        exe_path = os.path.join(self.temp_dir, "solution.exe" if os.name == 'nt' else "solution")
        
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        try:
            # 컴파일
            compile_result = subprocess.run(
                ['g++', source_path, '-o', exe_path, '-std=c++17'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir
            )
            
            if compile_result.returncode != 0:
                return CodeExecutionResult(
                    success=False,
                    output="",
                    error=f"컴파일 오류:\n{compile_result.stderr}",
                    execution_time=0
                )
            
            # 실행
            start_time = time.time()
            
            result = subprocess.run(
                [exe_path],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=self.temp_dir
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return CodeExecutionResult(
                success=result.returncode == 0,
                output=result.stdout.strip()[:MAX_OUTPUT_SIZE],
                error=result.stderr[:MAX_OUTPUT_SIZE] if result.stderr else None,
                execution_time=round(execution_time, 2)
            )
            
        except FileNotFoundError:
            return CodeExecutionResult(
                success=False,
                output="",
                error="G++가 설치되어 있지 않습니다. MinGW 또는 G++를 설치해주세요.",
                execution_time=0
            )
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"시간 초과: {MAX_EXECUTION_TIME}초 제한을 초과했습니다.",
                execution_time=MAX_EXECUTION_TIME * 1000
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=0
            )
        finally:
            # 정리
            if os.path.exists(source_path):
                os.remove(source_path)
            if os.path.exists(exe_path):
                os.remove(exe_path)


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
                    model=DEFAULT_LLM_MODEL,
                    temperature=0.3,
                    num_ctx=DEFAULT_LLM_NUM_CTX
                )
            except Exception as e:
                print(f"⚠️ CodeAnalyzer LLM 초기화 실패: {e}")
    
    async def analyze(
        self,
        code: str,
        language: str,
        problem: Optional[CodingProblem],
        execution_results: List[Dict]
    ) -> CodeAnalysisResult:
        """코드 종합 분석"""
        
        # 테스트 결과 요약
        passed = sum(1 for r in execution_results if r.get('passed', False))
        total = len(execution_results)
        
        # LLM 분석
        if self.llm:
            try:
                analysis = await self._llm_analyze(code, language, problem, execution_results)
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
        execution_results: List[Dict]
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
        test_results = "\n".join([
            f"- 테스트 {i+1}: {'통과 ✓' if r.get('passed') else '실패 ✗'} "
            f"(실행시간: {r.get('execution_time', 0):.2f}ms)"
            for i, r in enumerate(execution_results)
        ])
        
        messages = [
            SystemMessage(content=self.CODE_ANALYSIS_PROMPT),
            HumanMessage(content=f"""
{problem_info}

[제출된 코드 - {language}]
```{language}
{code}
```

[테스트 결과]
{test_results}

위 코드를 종합적으로 분석하고 JSON 형식으로 평가해주세요.
""")
        ]
        
        response = self.llm.invoke(messages)
        response_text = response.content
        
        # JSON Resilience 파싱
        analysis = parse_code_analysis_json(response_text, context="CodeAnalyzer.analyze_code")
        
        return CodeAnalysisResult(
            overall_score=analysis.get('overall_score', 0),
            correctness=analysis.get('correctness', {}),
            time_complexity=analysis.get('time_complexity', {}),
            space_complexity=analysis.get('space_complexity', {}),
            code_style=analysis.get('code_style', {}),
            comments=analysis.get('comments', {}),
            best_practices=analysis.get('best_practices', {}),
            feedback=analysis.get('feedback', []),
            detailed_analysis=analysis.get('detailed_analysis', '')
        )
    
    def _basic_analyze(
        self,
        code: str,
        language: str,
        passed: int,
        total: int
    ) -> CodeAnalysisResult:
        """기본 코드 분석 (LLM 없이)"""
        
        # 정확성 점수
        correctness_score = int((passed / total) * 25) if total > 0 else 0
        
        # 코드 스타일 분석
        lines = code.split('\n')
        has_comments = any('#' in line or '//' in line or '/*' in line for line in lines)
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
                "feedback": f"{passed}/{total} 테스트 케이스 통과"
            },
            time_complexity={
                "score": 15,
                "estimated": "분석 필요",
                "optimal": "문제에 따라 다름",
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다."
            },
            space_complexity={
                "score": 10,
                "estimated": "분석 필요",
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다."
            },
            code_style={
                "score": style_score,
                "issues": style_issues,
                "feedback": "코드 스타일이 양호합니다." if not style_issues else "개선이 필요합니다."
            },
            comments={
                "score": comment_score,
                "has_comments": has_comments,
                "quality": "fair" if has_comments else "poor",
                "feedback": "주석이 있습니다." if has_comments else "주석을 추가하세요."
            },
            best_practices={
                "score": 7,
                "followed": [],
                "missing": [],
                "feedback": "LLM을 활성화하면 상세 분석이 제공됩니다."
            },
            feedback=[
                "테스트 케이스를 모두 통과하도록 코드를 수정하세요." if passed < total else "모든 테스트를 통과했습니다!",
                "주석을 추가하여 코드 가독성을 높이세요." if not has_comments else "주석이 잘 작성되어 있습니다."
            ],
            detailed_analysis="기본 분석이 완료되었습니다. LLM을 활성화하면 더 상세한 분석을 받을 수 있습니다."
        )


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
        custom_test_cases: Optional[List[Dict]] = None
    ) -> Dict:
        """코드 실행 및 분석"""
        
        # 문제 가져오기 (캐시에서 조회)
        problem = _generated_problems.get(problem_id) if problem_id else None
        
        # 테스트 케이스 결정
        test_cases = custom_test_cases or (problem.test_cases if problem else [])
        
        if not test_cases:
            # 테스트 케이스 없으면 단순 실행
            result = self.executor.execute(code, language, "")
            return {
                "execution": result.dict(),
                "analysis": None,
                "test_results": []
            }
        
        # 각 테스트 케이스 실행
        test_results = []
        for i, tc in enumerate(test_cases):
            result = self.executor.execute(code, language, tc.get('input', ''))
            
            expected = tc.get('expected', '').strip()
            actual = result.output.strip()
            passed = actual == expected
            
            test_results.append({
                "test_id": i + 1,
                "input": tc.get('input', '')[:100] + ('...' if len(tc.get('input', '')) > 100 else ''),
                "expected": expected[:100],
                "actual": actual[:100],
                "passed": passed,
                "execution_time": result.execution_time,
                "error": result.error
            })
        
        # AI 분석
        analysis = await self.analyzer.analyze(code, language, problem, test_results)
        
        return {
            "problem": problem.dict() if problem else None,
            "test_results": test_results,
            "analysis": analysis.dict(),
            "summary": {
                "passed": sum(1 for r in test_results if r['passed']),
                "total": len(test_results),
                "overall_score": analysis.overall_score,
                "avg_execution_time": sum(r['execution_time'] for r in test_results) / len(test_results) if test_results else 0
            }
        }


# ========== FastAPI 라우터 ==========
def create_coding_router():
    """코딩 테스트 API 라우터"""
    
    router = APIRouter(prefix="/api/coding", tags=["Coding Test"])
    service = CodeExecutionService()
    generator = CodingProblemGenerator()
    
    @router.get("/generate")
    async def generate_problem(difficulty: str = "medium"):
        """LLM으로 코딩 문제 1개 생성"""
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"
        problem = await generator.generate(difficulty)
        # 테스트 케이스는 일부만 공개
        public_problem = problem.dict()
        public_problem['test_cases'] = problem.test_cases[:2]
        return public_problem
    
    @router.get("/problems/{problem_id}")
    async def get_problem(problem_id: str):
        """캐시된 문제 상세 조회"""
        problem = _generated_problems.get(problem_id)
        if not problem:
            raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다. 새 문제를 생성해주세요.")
        
        # 테스트 케이스는 일부만 공개
        public_problem = problem.dict()
        public_problem['test_cases'] = problem.test_cases[:2]
        return public_problem
    
    @router.post("/execute")
    async def execute_code(request: CodeExecutionRequest):
        """코드 실행"""
        if request.language.lower() not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 언어입니다. 지원 언어: {SUPPORTED_LANGUAGES}"
            )
        
        result = await service.run_and_analyze(
            code=request.code,
            language=request.language,
            problem_id=request.problem_id,
            custom_test_cases=request.test_cases
        )
        
        return result
    
    @router.post("/run")
    async def run_code_simple(request: CodeExecutionRequest):
        """단순 코드 실행 (분석 없이)"""
        executor = CodeExecutor()
        result = executor.execute(request.code, request.language, "")
        return result.dict()
    
    @router.post("/submit")
    async def submit_code(request: CodeExecutionRequest):
        """코드 제출 (실행 + 분석 + 테스트케이스 평가)"""
        if request.language.lower() not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 언어입니다. 지원 언어: {SUPPORTED_LANGUAGES}"
            )
        result = await service.run_and_analyze(
            code=request.code,
            language=request.language,
            problem_id=request.problem_id,
            custom_test_cases=request.test_cases
        )
        return result
    
    @router.get("/templates/{language}")
    async def get_template(language: str, problem_id: Optional[str] = None):
        """언어별 코드 템플릿"""
        templates = {
            "python": '''# Python 솔루션
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
''',
            "javascript": '''// JavaScript 솔루션
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
''',
            "java": '''import java.util.*;

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
''',
            "c": '''#include <stdio.h>
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
''',
            "cpp": '''#include <iostream>
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
'''
        }
        
        return {
            "language": language,
            "template": templates.get(language.lower(), "// 템플릿 없음")
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
        code = '''
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
'''
        
        result = await service.run_and_analyze(code, "python", problem.id)
        print("\n=== 실행 결과 ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test())
