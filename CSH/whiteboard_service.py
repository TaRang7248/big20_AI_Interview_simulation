"""
화이트보드 다이어그램 분석 서비스
================================
시스템 아키텍처 면접을 위한 화이트보드 다이어그램 분석

기능:
1. Claude 3.5 Sonnet Vision API를 통한 다이어그램 인식
2. 시스템 아키텍처 평가 (구조, 확장성, 보안 등)
3. 피드백 및 개선 제안
"""

import os
import base64
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# FastAPI
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Anthropic Claude API
try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    print("⚠️ anthropic 패키지 미설치. pip install anthropic")

# LLM Fallback
try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


# ========== 설정 ==========
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"


# ========== 모델 ==========
class DiagramAnalysisRequest(BaseModel):
    image_data: str  # Base64 인코딩된 이미지 데이터
    session_id: str
    problem_context: Optional[str] = None  # 문제 설명
    user_explanation: Optional[str] = None  # 사용자 설명


class DiagramAnalysisResult(BaseModel):
    overall_score: int  # 100점 만점
    diagram_recognition: Dict  # 다이어그램 인식 결과
    architecture_evaluation: Dict  # 아키텍처 평가
    component_analysis: List[Dict]  # 컴포넌트 분석
    feedback: List[str]  # 개선 피드백
    strengths: List[str]  # 강점
    weaknesses: List[str]  # 약점
    detailed_analysis: str  # 상세 분석


class ArchitectureProblem(BaseModel):
    id: str
    title: str
    description: str
    requirements: List[str]
    expected_components: List[str]
    difficulty: str  # easy, medium, hard
    time_limit: int  # 분
    category: Optional[str] = None


# ========== AI 동적 문제 생성 시스템 ==========

# 문제 카테고리 및 키워드
PROBLEM_CATEGORIES = {
    "messaging": {
        "name": "메시징/실시간 통신",
        "keywords": ["채팅", "메시지 큐", "알림", "푸시", "실시간", "WebSocket", "이벤트"],
        "examples": ["실시간 채팅", "알림 시스템", "이벤트 브로커", "협업 도구"]
    },
    "ecommerce": {
        "name": "전자상거래/결제",
        "keywords": ["결제", "장바구니", "재고", "주문", "배송", "정산", "쿠폰"],
        "examples": ["결제 시스템", "재고 관리", "주문 처리", "정산 시스템"]
    },
    "media": {
        "name": "미디어/스트리밍",
        "keywords": ["영상", "음악", "스트리밍", "트랜스코딩", "CDN", "업로드"],
        "examples": ["영상 플랫폼", "음악 스트리밍", "라이브 방송", "팟캐스트"]
    },
    "social": {
        "name": "소셜/커뮤니티",
        "keywords": ["피드", "팔로우", "좋아요", "댓글", "공유", "타임라인"],
        "examples": ["소셜 피드", "커뮤니티 플랫폼", "포럼", "리뷰 시스템"]
    },
    "data": {
        "name": "데이터/분석",
        "keywords": ["분석", "대시보드", "로그", "메트릭", "검색", "추천"],
        "examples": ["로그 분석", "추천 엔진", "검색 시스템", "데이터 파이프라인"]
    },
    "infra": {
        "name": "인프라/DevOps",
        "keywords": ["배포", "모니터링", "로깅", "스케줄링", "오케스트레이션"],
        "examples": ["CI/CD 파이프라인", "모니터링 시스템", "작업 스케줄러", "서비스 메시"]
    },
    "storage": {
        "name": "저장소/파일",
        "keywords": ["파일", "클라우드", "동기화", "백업", "공유"],
        "examples": ["클라우드 스토리지", "파일 공유", "백업 시스템", "문서 관리"]
    },
    "auth": {
        "name": "인증/보안",
        "keywords": ["로그인", "인증", "권한", "SSO", "OAuth", "토큰"],
        "examples": ["통합 인증", "권한 관리", "API 게이트웨이", "보안 감사"]
    }
}

# 난이도별 규모 설정
DIFFICULTY_SCALES = {
    "easy": {
        "users": ["1만", "10만", "100만"],
        "requests": ["초당 100건", "초당 1,000건", "분당 10만건"],
        "time_limit": 10,
        "complexity": "기본적인 구조 설계"
    },
    "medium": {
        "users": ["100만", "1,000만", "1억"],
        "requests": ["초당 1만건", "초당 10만건", "분당 100만건"],
        "time_limit": 15,
        "complexity": "확장성과 성능을 고려한 설계"
    },
    "hard": {
        "users": ["1억", "10억", "글로벌"],
        "requests": ["초당 100만건", "초당 1,000만건", "실시간 처리"],
        "time_limit": 20,
        "complexity": "대규모 분산 시스템 설계"
    }
}


class ArchitectureProblemGenerator:
    """AI 기반 동적 아키텍처 문제 생성기"""
    
    def __init__(self):
        self.llm = None
        self.claude_client = None
        self.generated_problems_cache: Dict[str, ArchitectureProblem] = {}
        self.problem_counter = 0
        
        # LLM 초기화
        if OLLAMA_AVAILABLE:
            try:
                self.llm = ChatOllama(model="llama3:8b-instruct-q4_0", temperature=0.8)
                print("✅ 아키텍처 문제 생성기 초기화 (Ollama)")
            except Exception as e:
                print(f"⚠️ Ollama 초기화 실패: {e}")
        
        if CLAUDE_AVAILABLE and ANTHROPIC_API_KEY:
            self.claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            print("✅ Claude 문제 생성기 활성화")
    
    def _get_random_category(self) -> str:
        """랜덤 카테고리 선택"""
        import random
        return random.choice(list(PROBLEM_CATEGORIES.keys()))
    
    def _get_random_difficulty(self) -> str:
        """랜덤 난이도 선택 (가중치 적용)"""
        import random
        # easy: 30%, medium: 50%, hard: 20%
        return random.choices(
            ["easy", "medium", "hard"],
            weights=[0.3, 0.5, 0.2]
        )[0]
    
    async def generate_problem(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None
    ) -> ArchitectureProblem:
        """AI를 사용해 새로운 아키텍처 문제 생성"""
        import random
        import json
        
        # 카테고리/난이도 선택
        if not category:
            category = self._get_random_category()
        if not difficulty:
            difficulty = self._get_random_difficulty()
        
        cat_info = PROBLEM_CATEGORIES.get(category, PROBLEM_CATEGORIES["messaging"])
        diff_info = DIFFICULTY_SCALES.get(difficulty, DIFFICULTY_SCALES["medium"])
        
        # 문제 ID 생성
        self.problem_counter += 1
        problem_id = f"gen_{self.problem_counter}_{category}_{difficulty}"
        
        # 프롬프트 생성
        prompt = f"""당신은 시스템 설계 면접관입니다. 아래 조건에 맞는 새로운 아키텍처 설계 문제를 생성하세요.

## 조건
- 카테고리: {cat_info['name']}
- 관련 키워드: {', '.join(cat_info['keywords'])}
- 난이도: {difficulty.upper()} ({diff_info['complexity']})
- 예상 사용자/트래픽 규모: {random.choice(diff_info['users'])} 사용자, {random.choice(diff_info['requests'])}
- 제한 시간: {diff_info['time_limit']}분

## 출력 형식 (JSON)
```json
{{
    "title": "시스템 이름 (예: 실시간 협업 문서 편집기)",
    "description": "상세한 문제 설명. 4-6줄로 구체적인 요구사항 포함",
    "requirements": ["기술적 요구사항 1", "요구사항 2", "요구사항 3", "요구사항 4"],
    "expected_components": ["예상 컴포넌트 1", "컴포넌트 2", "컴포넌트 3", "컴포넌트 4", "컴포넌트 5"]
}}
```

## 주의사항
- 기존의 흔한 문제(채팅, URL 단축기 등)와 다른 **창의적인** 문제를 내세요
- 실제 기업에서 사용하는 시스템을 참고하되, 독특한 제약조건을 추가하세요
- 요구사항은 측정 가능하고 구체적이어야 합니다
- 한국어로 작성하세요

새로운 아키텍처 문제를 JSON 형식으로 생성하세요:"""

        try:
            # Claude 사용 시도
            if self.claude_client:
                response = self.claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            # Ollama 폴백
            elif self.llm:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                response_text = response.content
            else:
                # LLM 없으면 기본 문제 반환
                return self._create_fallback_problem(category, difficulty, problem_id, cat_info, diff_info)
            
            # JSON 파싱
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]
            
            data = json.loads(json_match.strip())
            
            problem = ArchitectureProblem(
                id=problem_id,
                title=data.get("title", "시스템 설계 문제"),
                description=data.get("description", "시스템을 설계하세요."),
                requirements=data.get("requirements", ["확장성", "가용성", "성능"]),
                expected_components=data.get("expected_components", ["서버", "데이터베이스", "캐시"]),
                difficulty=difficulty,
                time_limit=diff_info["time_limit"],
                category=category
            )
            
            # 캐시에 저장
            self.generated_problems_cache[problem_id] = problem
            
            return problem
            
        except Exception as e:
            print(f"문제 생성 오류: {e}")
            return self._create_fallback_problem(category, difficulty, problem_id, cat_info, diff_info)
    
    def _create_fallback_problem(
        self,
        category: str,
        difficulty: str,
        problem_id: str,
        cat_info: dict,
        diff_info: dict
    ) -> ArchitectureProblem:
        """LLM 실패 시 폴백 문제 생성"""
        import random
        
        example = random.choice(cat_info["examples"])
        scale = random.choice(diff_info["users"])
        
        return ArchitectureProblem(
            id=problem_id,
            title=f"{example} 시스템 설계",
            description=f"""{scale} 사용자를 위한 {example} 시스템을 설계하세요.
- {cat_info['keywords'][0]}와 {cat_info['keywords'][1]} 기능 구현
- {diff_info['requests']} 처리 능력 필요
- 고가용성 및 장애 복구 고려
- 보안 및 데이터 무결성 보장""",
            requirements=[
                f"{diff_info['complexity']}",
                "수평적 확장 가능",
                "99.9% 가용성",
                "데이터 일관성 보장"
            ],
            expected_components=[
                "API 게이트웨이",
                "로드밸런서",
                "애플리케이션 서버",
                "데이터베이스",
                "캐시 레이어"
            ],
            difficulty=difficulty,
            time_limit=diff_info["time_limit"],
            category=category
        )
    
    async def get_problem_set(self, count: int = 5) -> List[ArchitectureProblem]:
        """여러 개의 랜덤 문제 세트 생성"""
        problems = []
        used_categories = set()
        
        for _ in range(count):
            # 다양한 카테고리에서 문제 생성
            available_categories = [c for c in PROBLEM_CATEGORIES.keys() if c not in used_categories]
            if not available_categories:
                available_categories = list(PROBLEM_CATEGORIES.keys())
            
            import random
            category = random.choice(available_categories)
            used_categories.add(category)
            
            problem = await self.generate_problem(category=category)
            problems.append(problem)
        
        return problems
    
    def get_cached_problem(self, problem_id: str) -> Optional[ArchitectureProblem]:
        """캐시된 문제 조회"""
        return self.generated_problems_cache.get(problem_id)


# 문제 생성기 인스턴스
problem_generator = ArchitectureProblemGenerator()


# ========== Claude Vision 다이어그램 분석 서비스 ==========
class DiagramAnalyzer:
    """Claude 3.5 Sonnet을 사용한 다이어그램 분석"""
    
    def __init__(self):
        self.client = None
        if CLAUDE_AVAILABLE and ANTHROPIC_API_KEY:
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            print("✅ Claude Vision API 초기화 완료")
        else:
            print("⚠️ Claude API 미설정. 폴백 모드 사용")
    
    async def analyze_diagram(
        self,
        image_base64: str,
        problem: Optional[ArchitectureProblem] = None,
        user_explanation: Optional[str] = None
    ) -> DiagramAnalysisResult:
        """다이어그램 분석 수행"""
        
        if self.client:
            return await self._analyze_with_claude(image_base64, problem, user_explanation)
        else:
            return await self._analyze_with_fallback(problem, user_explanation)
    
    async def _analyze_with_claude(
        self,
        image_base64: str,
        problem: Optional[ArchitectureProblem],
        user_explanation: Optional[str]
    ) -> DiagramAnalysisResult:
        """Claude Vision API로 다이어그램 분석"""
        
        # 이미지 데이터 정리 (data:image/png;base64, 제거)
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        # 시스템 프롬프트
        system_prompt = """당신은 시스템 아키텍처 전문가입니다.
제공된 다이어그램을 분석하고 다음을 평가해주세요:

1. **다이어그램 인식**: 어떤 컴포넌트들이 있는지 식별
2. **아키텍처 평가**: 
   - 구조적 완성도 (0-25점)
   - 확장성 (0-25점)
   - 보안성 (0-25점)
   - 성능 고려 (0-25점)
3. **강점과 약점**: 구체적으로 분석
4. **개선 제안**: 실질적인 피드백

반드시 아래 JSON 형식으로 응답하세요:
```json
{
    "diagram_recognition": {
        "components": ["컴포넌트1", "컴포넌트2"],
        "connections": ["A -> B", "B -> C"],
        "data_flows": ["설명1", "설명2"]
    },
    "architecture_evaluation": {
        "structure_score": 20,
        "structure_comment": "구조 평가 코멘트",
        "scalability_score": 18,
        "scalability_comment": "확장성 평가 코멘트",
        "security_score": 15,
        "security_comment": "보안성 평가 코멘트",
        "performance_score": 22,
        "performance_comment": "성능 평가 코멘트"
    },
    "component_analysis": [
        {"name": "컴포넌트명", "role": "역할", "evaluation": "평가"}
    ],
    "strengths": ["강점1", "강점2"],
    "weaknesses": ["약점1", "약점2"],
    "feedback": ["피드백1", "피드백2", "피드백3"],
    "detailed_analysis": "전체적인 상세 분석 텍스트"
}
```"""
        
        # 문제 컨텍스트 추가
        user_content = []
        
        if problem:
            user_content.append({
                "type": "text",
                "text": f"""## 문제 정보
**제목**: {problem.title}
**설명**: {problem.description}
**요구사항**: {', '.join(problem.requirements)}
**예상 컴포넌트**: {', '.join(problem.expected_components)}
**난이도**: {problem.difficulty}
"""
            })
        
        # 이미지 추가
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_base64
            }
        })
        
        # 사용자 설명 추가
        if user_explanation:
            user_content.append({
                "type": "text",
                "text": f"\n## 지원자 설명\n{user_explanation}"
            })
        
        user_content.append({
            "type": "text",
            "text": "\n위 다이어그램을 분석하고 JSON 형식으로 평가해주세요."
        })
        
        try:
            # Claude API 호출
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_content}
                ]
            )
            
            # 응답 파싱
            response_text = response.content[0].text
            
            # JSON 추출
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]
            
            result_data = json.loads(json_match.strip())
            
            # 점수 계산
            eval_data = result_data.get("architecture_evaluation", {})
            overall_score = (
                eval_data.get("structure_score", 0) +
                eval_data.get("scalability_score", 0) +
                eval_data.get("security_score", 0) +
                eval_data.get("performance_score", 0)
            )
            
            return DiagramAnalysisResult(
                overall_score=min(100, overall_score),
                diagram_recognition=result_data.get("diagram_recognition", {}),
                architecture_evaluation=eval_data,
                component_analysis=result_data.get("component_analysis", []),
                feedback=result_data.get("feedback", []),
                strengths=result_data.get("strengths", []),
                weaknesses=result_data.get("weaknesses", []),
                detailed_analysis=result_data.get("detailed_analysis", "")
            )
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return self._create_error_result("응답 파싱 오류")
        except Exception as e:
            print(f"Claude API 오류: {e}")
            return await self._analyze_with_fallback(problem, user_explanation)
    
    async def _analyze_with_fallback(
        self,
        problem: Optional[ArchitectureProblem],
        user_explanation: Optional[str]
    ) -> DiagramAnalysisResult:
        """Ollama를 사용한 폴백 분석 (이미지 없이 텍스트만)"""
        
        if not OLLAMA_AVAILABLE:
            return self._create_error_result("분석 서비스 사용 불가")
        
        try:
            llm = ChatOllama(model="llama3:8b-instruct-q4_0", temperature=0.3)
            
            prompt = f"""시스템 아키텍처 면접에서 지원자가 다이어그램을 제출했습니다.

문제: {problem.title if problem else '자유 설계'}
설명: {problem.description if problem else '없음'}
지원자 설명: {user_explanation or '없음'}

다이어그램을 직접 볼 수 없지만, 지원자의 설명을 바탕으로 평가해주세요.
JSON 형식으로 응답하세요:
{{
    "diagram_recognition": {{"components": [], "connections": [], "data_flows": []}},
    "architecture_evaluation": {{
        "structure_score": 15,
        "scalability_score": 15,
        "security_score": 15,
        "performance_score": 15
    }},
    "component_analysis": [],
    "strengths": ["설명 제공"],
    "weaknesses": ["이미지 분석 불가"],
    "feedback": ["Claude API 키를 설정하면 다이어그램을 직접 분석할 수 있습니다."],
    "detailed_analysis": "폴백 모드로 분석되었습니다."
}}"""
            
            response = llm.invoke([HumanMessage(content=prompt)])
            
            try:
                result_text = response.content
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                result_data = json.loads(result_text.strip())
                
                eval_data = result_data.get("architecture_evaluation", {})
                overall_score = sum([
                    eval_data.get("structure_score", 0),
                    eval_data.get("scalability_score", 0),
                    eval_data.get("security_score", 0),
                    eval_data.get("performance_score", 0)
                ])
                
                return DiagramAnalysisResult(
                    overall_score=overall_score,
                    diagram_recognition=result_data.get("diagram_recognition", {}),
                    architecture_evaluation=eval_data,
                    component_analysis=result_data.get("component_analysis", []),
                    feedback=result_data.get("feedback", []),
                    strengths=result_data.get("strengths", []),
                    weaknesses=result_data.get("weaknesses", []),
                    detailed_analysis=result_data.get("detailed_analysis", "")
                )
            except:
                return self._create_error_result("폴백 분석 실패")
                
        except Exception as e:
            print(f"폴백 분석 오류: {e}")
            return self._create_error_result(str(e))
    
    def _create_error_result(self, error_msg: str) -> DiagramAnalysisResult:
        """오류 결과 생성"""
        return DiagramAnalysisResult(
            overall_score=0,
            diagram_recognition={
                "components": [],
                "connections": [],
                "data_flows": [],
                "error": error_msg
            },
            architecture_evaluation={
                "structure_score": 0,
                "scalability_score": 0,
                "security_score": 0,
                "performance_score": 0,
                "error": error_msg
            },
            component_analysis=[],
            feedback=[f"분석 오류: {error_msg}"],
            strengths=[],
            weaknesses=[],
            detailed_analysis=f"분석 중 오류가 발생했습니다: {error_msg}"
        )


# ========== FastAPI 라우터 ==========
router = APIRouter(prefix="/api/whiteboard", tags=["whiteboard"])

# 서비스 인스턴스
diagram_analyzer = DiagramAnalyzer()

# 세션별 결과 저장
whiteboard_results: Dict[str, List[DiagramAnalysisResult]] = {}


@router.get("/problems")
async def get_architecture_problems(count: int = 5):
    """AI가 생성한 랜덤 아키텍처 문제 목록 조회"""
    problems = await problem_generator.get_problem_set(count=count)
    return {
        "problems": [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "requirements": p.requirements,
                "difficulty": p.difficulty,
                "time_limit": p.time_limit,
                "category": p.category
            }
            for p in problems
        ]
    }


@router.get("/problems/{problem_id}")
async def get_architecture_problem(problem_id: str):
    """특정 아키텍처 문제 조회 (캐시에서)"""
    # 캐시된 문제 찾기
    problem = problem_generator.get_cached_problem(problem_id)
    if problem:
        return {
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "requirements": problem.requirements,
            "expected_components": problem.expected_components,
            "difficulty": problem.difficulty,
            "time_limit": problem.time_limit,
            "category": problem.category
        }
    raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다. 새 문제를 생성하세요.")


@router.post("/generate")
async def generate_new_problem(
    category: Optional[str] = None,
    difficulty: Optional[str] = None
):
    """새로운 아키텍처 문제 생성"""
    problem = await problem_generator.generate_problem(
        category=category,
        difficulty=difficulty
    )
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "requirements": problem.requirements,
        "expected_components": problem.expected_components,
        "difficulty": problem.difficulty,
        "time_limit": problem.time_limit,
        "category": problem.category
    }


@router.get("/categories")
async def get_problem_categories():
    """사용 가능한 문제 카테고리 목록"""
    return {
        "categories": [
            {
                "id": cat_id,
                "name": cat_info["name"],
                "examples": cat_info["examples"]
            }
            for cat_id, cat_info in PROBLEM_CATEGORIES.items()
        ],
        "difficulties": ["easy", "medium", "hard"]
    }


@router.post("/analyze")
async def analyze_diagram(request: DiagramAnalysisRequest):
    """다이어그램 분석 수행"""
    
    # 문제 찾기 (캐시에서)
    problem = None
    if request.problem_context:
        problem = problem_generator.get_cached_problem(request.problem_context)
    
    # 분석 수행
    result = await diagram_analyzer.analyze_diagram(
        image_base64=request.image_data,
        problem=problem,
        user_explanation=request.user_explanation
    )
    
    # 결과 저장
    if request.session_id not in whiteboard_results:
        whiteboard_results[request.session_id] = []
    whiteboard_results[request.session_id].append(result)
    
    return {
        "success": True,
        "result": {
            "overall_score": result.overall_score,
            "diagram_recognition": result.diagram_recognition,
            "architecture_evaluation": result.architecture_evaluation,
            "component_analysis": result.component_analysis,
            "feedback": result.feedback,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "detailed_analysis": result.detailed_analysis
        }
    }


@router.get("/results/{session_id}")
async def get_whiteboard_results(session_id: str):
    """세션별 화이트보드 결과 조회"""
    results = whiteboard_results.get(session_id, [])
    
    if not results:
        return {"results": [], "average_score": 0}
    
    avg_score = sum(r.overall_score for r in results) / len(results)
    
    return {
        "results": [
            {
                "overall_score": r.overall_score,
                "architecture_evaluation": r.architecture_evaluation,
                "feedback": r.feedback,
                "strengths": r.strengths,
                "weaknesses": r.weaknesses
            }
            for r in results
        ],
        "average_score": round(avg_score)
    }


@router.get("/status")
async def get_whiteboard_status():
    """화이트보드 서비스 상태 확인"""
    return {
        "claude_available": CLAUDE_AVAILABLE and bool(ANTHROPIC_API_KEY),
        "ollama_fallback": OLLAMA_AVAILABLE,
        "model": CLAUDE_MODEL if CLAUDE_AVAILABLE and ANTHROPIC_API_KEY else "llama3:8b-instruct-q4_0 (fallback)"
    }
