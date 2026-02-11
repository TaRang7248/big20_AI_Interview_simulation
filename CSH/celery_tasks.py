"""
Celery 태스크 정의
==================
AI 면접 시스템의 비동기 작업 태스크들을 정의합니다.

태스크 종류:
1. LLM 기반 답변 평가
2. 감정 분석 (배치)
3. 리포트 생성
4. TTS 음성 생성
5. 이력서 RAG 처리
6. 세션 정리 및 통계 집계

이벤트 기반 아키텍처:
- 각 태스크 완료 시 Redis Pub/Sub를 통해 이벤트를 발행합니다.
- API 서버에서 이벤트를 수신하여 WebSocket으로 프론트엔드에 전달합니다.
"""

import os
import sys
import json
import time
import re
from typing import Dict, List, Any, Optional

# JSON Resilience 유틸리티
from json_utils import parse_evaluation_json
from datetime import datetime, timedelta
from collections import Counter

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from celery_app import celery_app
from celery import shared_task, group, chain, chord
from celery.exceptions import SoftTimeLimitExceeded
from dotenv import load_dotenv

load_dotenv()


# ========== 이벤트 발행 헬퍼 (Celery Worker 동기 컨텍스트) ==========

def _publish_event(event_type_str: str, session_id: str = None, data: dict = None, source: str = "celery_worker"):
    """
    Celery 태스크 내부에서 이벤트 발행 (동기, Redis Pub/Sub).
    API 서버의 EventBus가 수신하여 로컬 핸들러 + WebSocket 브로드캐스트 처리.
    """
    try:
        import redis
        r = redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"), decode_responses=True)
        event_payload = json.dumps({
            "event_type": event_type_str,
            "event_id": os.urandom(6).hex(),
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "session_id": session_id,
            "data": data or {},
        }, ensure_ascii=False)
        channel = f"interview_events:{event_type_str}"
        r.publish(channel, event_payload)
        r.close()
    except Exception as e:
        print(f"[EventPublish] 이벤트 발행 실패 ({event_type_str}): {e}")

# ========== 서비스 초기화 (Worker에서 사용) ==========
_llm = None
_rag = None
_tts_service = None


def get_llm():
    """LLM 인스턴스 가져오기 (Lazy Loading)"""
    global _llm
    if _llm is None:
        try:
            from langchain_ollama import ChatOllama
            DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
            DEFAULT_LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "16384"))
            _llm = ChatOllama(model=DEFAULT_LLM_MODEL, temperature=0.3, num_ctx=DEFAULT_LLM_NUM_CTX)
        except Exception as e:
            print(f"LLM 초기화 실패: {e}")
    return _llm


def get_rag():
    """RAG 인스턴스 가져오기 (Lazy Loading)"""
    global _rag
    if _rag is None:
        try:
            from resume_rag import ResumeRAG
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
            if connection_string:
                _rag = ResumeRAG(connection_string=connection_string)
        except Exception as e:
            print(f"RAG 초기화 실패: {e}")
    return _rag


def get_tts_service():
    """TTS 서비스 인스턴스 가져오기 (Lazy Loading)"""
    global _tts_service
    if _tts_service is None:
        try:
            from hume_tts_service import HumeInterviewerVoice
            _tts_service = HumeInterviewerVoice()
        except Exception as e:
            print(f"TTS 초기화 실패: {e}")
    return _tts_service


# ========== LLM 평가 태스크 ==========

EVALUATION_PROMPT = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 답변을 분석하고 평가해주세요.

[평가 기준]
1. 문제 해결력 (1-5점): 지원자가 문제를 어떻게 접근하고 해결하는지를 평가합니다.
2. 논리성 (1-5점): 답변의 논리적 흐름이 일관성 있는지를 평가합니다.
3. 기술 이해도 (1-5점): 기술적 개념에 대한 이해가 정확한가?
4. STAR 기법 (1-5점): 상황-과제-행동-결과 구조로 답변했는가?
5. 의사소통능력 (1-5점): 답변이 명확하고 이해하기 쉬운가?

[합격 추천 기준]
- "합격": 총점 20점 이상이고 모든 항목 3점 이상
- "보류": 총점 15~19점이거나 일부 항목 2점
- "불합격": 총점 14점 이하이거나 2개 이상 항목 2점 이하

[출력 형식 - 반드시 JSON으로 응답]
{{
    "scores": {{
        "problem_solving": 숫자,
        "logic": 숫자,
        "technical": 숫자,
        "star": 숫자,
        "communication": 숫자
    }},
    "total_score": 숫자(25점 만점),
    "recommendation": "합격" 또는 "보류" 또는 "불합격",
    "recommendation_reason": "추천 사유를 한 줄로 작성",
    "strengths": ["강점1", "강점2"],
    "improvements": ["개선점1", "개선점2"],
    "brief_feedback": "한 줄 피드백"
}}"""


@celery_app.task(
    bind=True,
    name="celery_tasks.evaluate_answer_task",
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=60,
    time_limit=90
)
def evaluate_answer_task(
    self,
    session_id: str,
    question: str,
    answer: str,
    resume_context: str = ""
) -> Dict:
    """
    LLM을 사용하여 답변 평가 (비동기 태스크)
    
    Args:
        session_id: 세션 ID
        question: 면접 질문
        answer: 사용자 답변
        resume_context: 이력서 관련 컨텍스트 (RAG에서 추출)
    
    Returns:
        평가 결과 딕셔너리
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 답변 평가 시작 - Session: {session_id}")
    
    try:
        llm = get_llm()
        if not llm:
            return _default_evaluation("LLM 서비스 사용 불가")
        
        from langchain_core.messages import HumanMessage, SystemMessage
        
        # RAG 컨텍스트 추가
        rag_section = ""
        if resume_context:
            rag_section = f"\n[참고: 이력서 내용]\n{resume_context}"
        
        messages = [
            SystemMessage(content=EVALUATION_PROMPT),
            HumanMessage(content=f"""
[질문]
{question}

[지원자 답변]
{answer}
{rag_section}

위 답변을 평가해주세요. 반드시 JSON 형식으로 응답해주세요.
""")
        ]
        
        response = llm.invoke(messages)
        response_text = response.content
        
        # JSON Resilience 파싱
        evaluation = parse_evaluation_json(response_text, context=f"celery_evaluate_answer[{task_id}]")
        evaluation["task_id"] = task_id
        evaluation["evaluated_at"] = datetime.now().isoformat()
        print(f"[Task {task_id}] 평가 완료 - 점수: {evaluation.get('total_score', 'N/A')}")

        # 📤 이벤트 발행: 평가 완료
        _publish_event(
            "evaluation.completed",
            session_id=session_id,
            data={"task_id": task_id, "score": evaluation.get("total_score"), "feedback": evaluation.get("brief_feedback", "")},
        )
        return evaluation
            
    except SoftTimeLimitExceeded:
        print(f"[Task {task_id}] 시간 초과")
        return _default_evaluation("평가 시간 초과")
        
    except Exception as e:
        print(f"[Task {task_id}] 평가 오류: {e}")
        # 재시도
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return _default_evaluation(str(e))


def _default_evaluation(reason: str = "") -> Dict:
    """기본 평가 결과 반환"""
    return {
        "scores": {
            "problem_solving": 3,
            "logic": 3,
            "technical": 3,
            "star": 3,
            "communication": 3
        },
        "total_score": 15,
        "recommendation": "보류",
        "recommendation_reason": reason or "LLM 서비스 미사용으로 기본 평가 적용",
        "strengths": ["답변을 완료했습니다."],
        "improvements": ["더 구체적인 예시를 들어보세요."],
        "brief_feedback": reason or "답변을 분석 중입니다.",
        "fallback": True
    }


@celery_app.task(
    bind=True,
    name="celery_tasks.batch_evaluate_task",
    soft_time_limit=300,
    time_limit=360
)
def batch_evaluate_task(
    self,
    session_id: str,
    qa_pairs: List[Dict]
) -> List[Dict]:
    """
    여러 답변을 배치로 평가
    
    Args:
        session_id: 세션 ID
        qa_pairs: [{"question": "...", "answer": "..."}, ...] 리스트
    
    Returns:
        평가 결과 리스트
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 배치 평가 시작 - {len(qa_pairs)}개 답변")
    
    results = []
    for i, pair in enumerate(qa_pairs):
        try:
            result = evaluate_answer_task.apply(
                args=[session_id, pair["question"], pair["answer"], pair.get("resume_context", "")]
            ).get(timeout=90)
            result["question_index"] = i
            results.append(result)
        except Exception as e:
            print(f"[Task {task_id}] 배치 평가 {i} 오류: {e}")
            results.append({**_default_evaluation(str(e)), "question_index": i})
    
    print(f"[Task {task_id}] 배치 평가 완료 - {len(results)}개 결과")
    return results


# ========== 감정 분석 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.analyze_emotion_task",
    soft_time_limit=30,
    time_limit=45
)
def analyze_emotion_task(
    self,
    session_id: str,
    image_data: str  # Base64 인코딩된 이미지
) -> Dict:
    """
    이미지에서 감정 분석 수행 (비동기 태스크)
    
    Args:
        session_id: 세션 ID
        image_data: Base64 인코딩된 이미지 데이터
    
    Returns:
        감정 분석 결과
    """
    task_id = self.request.id
    
    try:
        import base64
        import numpy as np
        import cv2
        from deepface import DeepFace
        
        # Base64 디코딩
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("이미지 디코딩 실패")
        
        # DeepFace 분석
        result = DeepFace.analyze(img, actions=["emotion"], enforce_detection=False)
        item = result[0] if isinstance(result, list) else result
        
        scores = item.get("emotion", {})
        keys_map = {
            "happy": "happy", "sad": "sad", "angry": "angry",
            "surprise": "surprise", "fear": "fear",
            "disgust": "disgust", "neutral": "neutral"
        }
        
        raw = {k: float(scores.get(src, 0.0)) for k, src in keys_map.items()}
        total = sum(raw.values()) or 1.0
        probabilities = {k: round(v / total, 4) for k, v in raw.items()}
        
        result = {
            "session_id": session_id,
            "dominant_emotion": item.get("dominant_emotion"),
            "probabilities": probabilities,
            "raw_scores": raw,
            "analyzed_at": datetime.now().isoformat(),
            "task_id": task_id
        }

        # 📤 이벤트 발행: 감정 분석 완료
        _publish_event(
            "emotion.analyzed",
            session_id=session_id,
            data={"dominant_emotion": result["dominant_emotion"], "probabilities": probabilities, "confidence": max(probabilities.values()) if probabilities else 0},
        )
        return result
        
    except Exception as e:
        print(f"[Task {task_id}] 감정 분석 오류: {e}")
        return {
            "session_id": session_id,
            "dominant_emotion": "neutral",
            "probabilities": {"neutral": 1.0},
            "error": str(e),
            "task_id": task_id
        }


@celery_app.task(
    bind=True,
    name="celery_tasks.batch_emotion_analysis_task",
    soft_time_limit=120,
    time_limit=180
)
def batch_emotion_analysis_task(
    self,
    session_id: str,
    image_data_list: List[str]
) -> Dict:
    """
    여러 이미지의 감정을 배치로 분석하고 통계 생성
    
    Args:
        session_id: 세션 ID
        image_data_list: Base64 이미지 리스트
    
    Returns:
        감정 분석 통계
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 배치 감정 분석 시작 - {len(image_data_list)}개 이미지")
    
    results = []
    emotion_counts = Counter()
    emotion_scores = {"happy": [], "sad": [], "angry": [], "surprise": [], 
                      "fear": [], "disgust": [], "neutral": []}
    
    for i, image_data in enumerate(image_data_list):
        try:
            result = analyze_emotion_task.apply(
                args=[session_id, image_data]
            ).get(timeout=30)
            
            results.append(result)
            dominant = result.get("dominant_emotion", "neutral")
            emotion_counts[dominant] += 1
            
            for emo, prob in result.get("probabilities", {}).items():
                emotion_scores[emo].append(prob)
                
        except Exception as e:
            print(f"[Task {task_id}] 이미지 {i} 분석 오류: {e}")
    
    # 통계 계산
    avg_scores = {}
    for emo, scores in emotion_scores.items():
        if scores:
            avg_scores[emo] = round(sum(scores) / len(scores), 4)
        else:
            avg_scores[emo] = 0.0
    
    return {
        "session_id": session_id,
        "total_analyzed": len(results),
        "emotion_distribution": dict(emotion_counts),
        "average_scores": avg_scores,
        "dominant_overall": emotion_counts.most_common(1)[0][0] if emotion_counts else "neutral",
        "task_id": task_id
    }


# ========== 리포트 생성 태스크 ==========

STAR_KEYWORDS = {
    'situation': ['상황', '배경', '당시', '그때', '환경', '상태', '문제', '이슈', '과제'],
    'task': ['목표', '과제', '임무', '역할', '담당', '책임', '해야 할', '목적', '미션'],
    'action': ['행동', '수행', '실행', '처리', '해결', '개발', '구현', '적용', '진행', '시도', '노력'],
    'result': ['결과', '성과', '달성', '완료', '개선', '향상', '증가', '감소', '효과', '성공']
}

TECH_KEYWORDS = [
    'python', 'java', 'javascript', 'react', 'vue', 'django', 'flask', 'spring',
    'aws', 'azure', 'docker', 'kubernetes', 'sql', 'mongodb', 'postgresql',
    'git', 'ci/cd', 'api', 'rest', 'machine learning', 'deep learning',
    'tensorflow', 'pytorch', 'pandas', 'LLM', 'RAG', 'LangChain', 'FastAPI'
]


@celery_app.task(
    bind=True,
    name="celery_tasks.generate_report_task",
    soft_time_limit=120,
    time_limit=180
)
def generate_report_task(
    self,
    session_id: str,
    chat_history: List[Dict],
    evaluations: List[Dict],
    emotion_stats: Optional[Dict] = None,
    prosody_stats: Optional[Dict] = None
) -> Dict:
    """
    면접 종합 리포트 생성 (비동기 태스크)
    
    Args:
        session_id: 세션 ID
        chat_history: 대화 기록
        evaluations: 평가 결과 리스트
        emotion_stats: 감정 분석 통계 (DeepFace)
        prosody_stats: 음성 감정 분석 통계 (Hume Prosody)
    
    Returns:
        종합 리포트
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 리포트 생성 시작 - Session: {session_id}")
    
    try:
        # 사용자 답변 추출
        answers = [msg["content"] for msg in chat_history if msg["role"] == "user"]
        
        # STAR 분석
        star_analysis = _analyze_star_structure(answers)
        
        # 키워드 추출
        keywords = _extract_keywords(answers)
        
        # 메트릭 계산
        metrics = {
            'total_answers': len(answers),
            'avg_length': round(sum(len(a) for a in answers) / len(answers), 1) if answers else 0,
            'total_chars': sum(len(a) for a in answers)
        }
        
        # 평가 점수 집계
        if evaluations:
            avg_scores = {"problem_solving": 0, "logic": 0, "technical": 0, "star": 0, "communication": 0}
            for ev in evaluations:
                for key in avg_scores:
                    avg_scores[key] += ev.get("scores", {}).get(key, 0)
            for key in avg_scores:
                avg_scores[key] = round(avg_scores[key] / len(evaluations), 1)
            total_avg = round(sum(avg_scores.values()) / 5, 1)
        else:
            avg_scores = {}
            total_avg = 0
        
        # 전체 강점/개선점 집계
        all_strengths = []
        all_improvements = []
        for ev in evaluations:
            all_strengths.extend(ev.get("strengths", []))
            all_improvements.extend(ev.get("improvements", []))
        
        strength_counts = Counter(all_strengths)
        improvement_counts = Counter(all_improvements)
        
        report = {
            "session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "task_id": task_id,
            "summary": {
                "total_questions": len([m for m in chat_history if m["role"] == "assistant"]),
                "total_answers": metrics['total_answers'],
                "average_answer_length": metrics['avg_length'],
                "interview_duration": "N/A"  # 세션에서 가져와야 함
            },
            "star_analysis": {
                "situation_score": min(star_analysis['situation']['count'] * 20, 100),
                "task_score": min(star_analysis['task']['count'] * 20, 100),
                "action_score": min(star_analysis['action']['count'] * 20, 100),
                "result_score": min(star_analysis['result']['count'] * 20, 100),
                "overall_star_score": _calculate_star_score(star_analysis)
            },
            "evaluation_scores": {
                "average_by_criteria": avg_scores,
                "total_average": total_avg,
                "max_score": 25
            },
            "keywords": keywords,
            "top_strengths": strength_counts.most_common(5),
            "top_improvements": improvement_counts.most_common(5),
            "emotion_analysis": emotion_stats or {},
            "prosody_analysis": prosody_stats or {},
            "recommendations": _generate_recommendations(avg_scores, star_analysis),
            "grade": _calculate_grade(total_avg, star_analysis)
        }
        
        print(f"[Task {task_id}] 리포트 생성 완료 - 등급: {report['grade']}")

        # 📤 이벤트 발행: 리포트 생성 완료
        _publish_event(
            "report.generated",
            session_id=session_id,
            data={"task_id": task_id, "grade": report.get("grade"), "total_average": total_avg},
        )
        return report
        
    except Exception as e:
        print(f"[Task {task_id}] 리포트 생성 오류: {e}")
        _publish_event("system.error", session_id=session_id, data={"error": str(e), "source": "generate_report_task"})
        return {
            "session_id": session_id,
            "error": str(e),
            "task_id": task_id
        }


def _analyze_star_structure(answers: List[str]) -> Dict:
    """STAR 기법 분석"""
    star_analysis = {key: {'count': 0, 'examples': []} for key in STAR_KEYWORDS}
    
    for answer in answers:
        answer_lower = answer.lower()
        for element, keywords in STAR_KEYWORDS.items():
            for keyword in keywords:
                if keyword in answer_lower:
                    star_analysis[element]['count'] += 1
                    break
    
    return star_analysis


def _extract_keywords(answers: List[str]) -> Dict:
    """키워드 추출"""
    all_text = ' '.join(answers).lower()
    
    found_tech = []
    for kw in TECH_KEYWORDS:
        if kw.lower() in all_text:
            count = all_text.count(kw.lower())
            found_tech.append((kw, count))
    
    found_tech.sort(key=lambda x: x[1], reverse=True)
    
    return {
        'tech_keywords': found_tech[:10],
        'total_tech_mentions': sum(c for _, c in found_tech)
    }


def _calculate_star_score(star_analysis: Dict) -> int:
    """STAR 종합 점수 계산 (100점 만점)"""
    total = 0
    for element in ['situation', 'task', 'action', 'result']:
        count = star_analysis[element]['count']
        total += min(count * 25, 25)  # 각 요소 최대 25점
    return total


def _generate_recommendations(avg_scores: Dict, star_analysis: Dict) -> List[str]:
    """개선 권장사항 생성"""
    recommendations = []
    
    if avg_scores.get('problem_solving', 0) < 3:
        recommendations.append("답변에 구체적인 수치와 사례를 더 포함해보세요.")
    
    if avg_scores.get('star', 0) < 3:
        recommendations.append("STAR 기법(상황-과제-행동-결과)을 활용해 구조적으로 답변해보세요.")
    
    if star_analysis.get('result', {}).get('count', 0) < 2:
        recommendations.append("프로젝트나 경험의 결과와 성과를 더 강조해보세요.")
    
    if avg_scores.get('technical', 0) < 3:
        recommendations.append("기술적 용어와 개념을 정확하게 사용하도록 연습해보세요.")
    
    if not recommendations:
        recommendations.append("전반적으로 좋은 면접이었습니다! 자신감을 가지세요.")
    
    return recommendations


def _calculate_grade(total_avg: float, star_analysis: Dict) -> str:
    """등급 계산"""
    star_score = _calculate_star_score(star_analysis)
    combined = (total_avg / 5 * 50) + (star_score / 2)  # 100점 만점으로 환산
    
    if combined >= 90:
        return "S"
    elif combined >= 80:
        return "A"
    elif combined >= 70:
        return "B"
    elif combined >= 60:
        return "C"
    else:
        return "D"


# ========== TTS 생성 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.generate_tts_task",
    soft_time_limit=30,
    time_limit=45,
    max_retries=2
)
def generate_tts_task(
    self,
    text: str,
    voice_config: Optional[Dict] = None
) -> Dict:
    """
    텍스트를 음성으로 변환 (비동기 태스크)
    
    Args:
        text: 변환할 텍스트
        voice_config: 음성 설정 (선택사항)
    
    Returns:
        음성 파일 경로 또는 Base64 데이터
    """
    task_id = self.request.id
    print(f"[Task {task_id}] TTS 생성 시작 - 텍스트 길이: {len(text)}")
    
    try:
        import asyncio
        
        tts_service = get_tts_service()
        if not tts_service:
            return {"error": "TTS 서비스 사용 불가", "task_id": task_id}
        
        # 비동기 함수 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            audio_url = loop.run_until_complete(tts_service.speak(text))
        finally:
            loop.close()
        
        return {
            "audio_url": audio_url,
            "text_length": len(text),
            "generated_at": datetime.now().isoformat(),
            "task_id": task_id
        }
        
    except Exception as e:
        print(f"[Task {task_id}] TTS 생성 오류: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"error": str(e), "task_id": task_id}


# ========== RAG 처리 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.process_resume_task",
    soft_time_limit=180,
    time_limit=240
)
def process_resume_task(
    self,
    session_id: str,
    pdf_path: str
) -> Dict:
    """
    이력서 PDF를 처리하고 벡터 저장소에 인덱싱 (비동기 태스크)
    
    Args:
        session_id: 세션 ID
        pdf_path: PDF 파일 경로
    
    Returns:
        처리 결과
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 이력서 처리 시작 - Session: {session_id}")
    
    try:
        if not os.path.exists(pdf_path):
            return {"error": "파일을 찾을 수 없습니다.", "task_id": task_id}
        
        rag = get_rag()
        if not rag:
            return {"error": "RAG 서비스 사용 불가", "task_id": task_id}
        
        # PDF 인덱싱
        rag.load_and_index_pdf(pdf_path)

        # 📤 이벤트 발행: 이력서 인덱싱 완료
        _publish_event(
            "resume.indexed",
            session_id=session_id,
            data={"pdf_path": pdf_path, "task_id": task_id},
        )
        return {
            "session_id": session_id,
            "status": "success",
            "pdf_path": pdf_path,
            "indexed_at": datetime.now().isoformat(),
            "task_id": task_id
        }
        
    except Exception as e:
        print(f"[Task {task_id}] 이력서 처리 오류: {e}")
        return {
            "session_id": session_id,
            "status": "error",
            "error": str(e),
            "task_id": task_id
        }


@celery_app.task(
    bind=True,
    name="celery_tasks.retrieve_resume_context_task",
    soft_time_limit=30,
    time_limit=45
)
def retrieve_resume_context_task(
    self,
    query: str,
    top_k: int = 3
) -> Dict:
    """
    이력서에서 관련 컨텍스트 검색 (비동기 태스크)
    
    Args:
        query: 검색 쿼리 (답변 내용)
        top_k: 반환할 문서 수
    
    Returns:
        검색된 컨텍스트
    """
    task_id = self.request.id
    
    try:
        rag = get_rag()
        if not rag:
            return {"context": "", "task_id": task_id}
        
        retriever = rag.get_retriever()
        docs = retriever.invoke(query)
        
        if docs:
            context = "\n".join([d.page_content for d in docs[:top_k]])
            return {
                "context": context,
                "num_docs": len(docs[:top_k]),
                "task_id": task_id
            }
        
        return {"context": "", "num_docs": 0, "task_id": task_id}
        
    except Exception as e:
        print(f"[Task {task_id}] 컨텍스트 검색 오류: {e}")
        return {"context": "", "error": str(e), "task_id": task_id}


# ========== 유지보수 태스크 ==========

@celery_app.task(name="celery_tasks.cleanup_sessions_task")
def cleanup_sessions_task() -> Dict:
    """만료된 세션 정리"""
    print("[Cleanup] 세션 정리 작업 시작")
    
    # Redis에서 만료된 세션 정리
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        
        # 24시간 이상 된 세션 키 삭제
        cleaned = 0
        pattern = "session:*"
        for key in r.scan_iter(pattern):
            ttl = r.ttl(key)
            if ttl == -1:  # TTL 없는 키
                r.expire(key, 86400)  # 24시간 TTL 설정
            elif ttl < 0:
                r.delete(key)
                cleaned += 1
        
        print(f"[Cleanup] {cleaned}개 세션 정리 완료")
        return {"cleaned_sessions": cleaned, "timestamp": datetime.now().isoformat()}
        
    except Exception as e:
        print(f"[Cleanup] 오류: {e}")
        return {"error": str(e)}


@celery_app.task(name="celery_tasks.aggregate_statistics_task")
def aggregate_statistics_task() -> Dict:
    """통계 집계 작업"""
    print("[Stats] 통계 집계 작업 시작")
    
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        
        # 오늘 날짜 기준 통계
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 간단한 통계 저장
        stats = {
            "date": today,
            "aggregated_at": datetime.now().isoformat()
        }
        
        r.hset(f"stats:{today}", mapping=stats)
        r.expire(f"stats:{today}", 604800)  # 7일간 유지
        
        print(f"[Stats] 통계 집계 완료 - {today}")
        return stats
        
    except Exception as e:
        print(f"[Stats] 오류: {e}")
        return {"error": str(e)}


# ========== 복합 워크플로우 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.complete_interview_workflow_task"
)
def complete_interview_workflow_task(
    self,
    session_id: str,
    chat_history: List[Dict],
    emotion_images: List[str] = None
) -> Dict:
    """
    면접 완료 후 전체 워크플로우 실행
    (평가 + 감정 분석 + 리포트 생성)
    
    Args:
        session_id: 세션 ID
        chat_history: 대화 기록
        emotion_images: 감정 분석용 이미지 리스트 (선택)
    
    Returns:
        최종 결과
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 면접 완료 워크플로우 시작")
    
    try:
        # 1. 모든 QA 쌍 추출
        qa_pairs = []
        current_question = None
        for msg in chat_history:
            if msg["role"] == "assistant":
                current_question = msg["content"]
            elif msg["role"] == "user" and current_question:
                qa_pairs.append({
                    "question": current_question,
                    "answer": msg["content"]
                })
                current_question = None
        
        # 2. 배치 평가 실행
        evaluations = batch_evaluate_task.apply(
            args=[session_id, qa_pairs]
        ).get(timeout=360)
        
        # 3. 감정 분석 (이미지가 있는 경우)
        emotion_stats = None
        if emotion_images:
            emotion_stats = batch_emotion_analysis_task.apply(
                args=[session_id, emotion_images]
            ).get(timeout=180)
        
        # 4. 리포트 생성
        report = generate_report_task.apply(
            args=[session_id, chat_history, evaluations, emotion_stats]
        ).get(timeout=180)
        
        print(f"[Task {task_id}] 면접 완료 워크플로우 완료")

        # 📤 이벤트 발행: 워크플로우 완료 (리포트 포함)
        _publish_event(
            "report.generated",
            session_id=session_id,
            data={
                "task_id": task_id,
                "grade": report.get("grade") if isinstance(report, dict) else None,
                "workflow": True,
            },
        )
        return {
            "session_id": session_id,
            "evaluations": evaluations,
            "emotion_stats": emotion_stats,
            "report": report,
            "workflow_task_id": task_id
        }
        
    except Exception as e:
        print(f"[Task {task_id}] 워크플로우 오류: {e}")
        _publish_event("system.error", session_id=session_id, data={"error": str(e), "source": "complete_interview_workflow_task"})
        return {
            "session_id": session_id,
            "error": str(e),
            "workflow_task_id": task_id
        }


# ========== TTS 프리페칭 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.prefetch_tts_task",
    soft_time_limit=60,
    time_limit=90
)
def prefetch_tts_task(
    self,
    session_id: str,
    texts: List[str]
) -> Dict:
    """
    여러 텍스트의 TTS를 미리 생성 (프리페칭)
    
    Args:
        session_id: 세션 ID
        texts: TTS로 변환할 텍스트 리스트
    
    Returns:
        생성된 오디오 URL 딕셔너리
    """
    task_id = self.request.id
    print(f"[Task {task_id}] TTS 프리페칭 시작 - {len(texts)}개 텍스트")
    
    results = {}
    import asyncio
    
    tts_service = get_tts_service()
    if not tts_service:
        return {"error": "TTS 서비스 사용 불가", "task_id": task_id}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        for i, text in enumerate(texts):
            try:
                audio_url = loop.run_until_complete(tts_service.speak(text))
                results[f"text_{i}"] = {
                    "text": text[:50] + "..." if len(text) > 50 else text,
                    "audio_url": audio_url,
                    "success": True
                }
            except Exception as e:
                results[f"text_{i}"] = {
                    "text": text[:50] + "..." if len(text) > 50 else text,
                    "error": str(e),
                    "success": False
                }
    finally:
        loop.close()
    
    print(f"[Task {task_id}] TTS 프리페칭 완료 - 성공: {sum(1 for r in results.values() if r.get('success'))}/{len(texts)}")
    return {
        "session_id": session_id,
        "results": results,
        "task_id": task_id
    }


# ========== 실시간 LLM 질문 생성 태스크 ==========

INTERVIEWER_PROMPT_CELERY = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
자연스럽고 전문적인 면접을 진행해주세요.
질문은 명확하고 구체적으로 해주세요."""


@celery_app.task(
    bind=True,
    name="celery_tasks.generate_question_task",
    soft_time_limit=30,
    time_limit=45,
    max_retries=2
)
def generate_question_task(
    self,
    session_id: str,
    user_answer: str,
    chat_history: List[Dict],
    question_count: int
) -> Dict:
    """
    LLM을 사용하여 다음 면접 질문 생성 (비동기 태스크)
    
    Args:
        session_id: 세션 ID
        user_answer: 사용자의 이전 답변
        chat_history: 대화 기록
        question_count: 현재 질문 수
    
    Returns:
        생성된 질문
    """
    task_id = self.request.id
    print(f"[Task {task_id}] 질문 생성 시작 - Session: {session_id}")
    
    try:
        llm = get_llm()
        if not llm:
            return {
                "question": "그 경험에서 가장 어려웠던 점은 무엇이었나요?",
                "fallback": True,
                "task_id": task_id
            }
        
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        messages = [SystemMessage(content=INTERVIEWER_PROMPT_CELERY)]
        
        # 대화 기록 추가
        for msg in chat_history[-6:]:  # 최근 6개만
            if msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
        
        # 질문 생성 요청
        question_prompt = f"""[현재 상황]
- 진행된 질문 수: {question_count}
- 지원자의 마지막 답변을 바탕으로 다음 질문을 생성해주세요.
- 질문만 작성하세요."""
        
        messages.append(HumanMessage(content=question_prompt))
        
        response = llm.invoke(messages)
        question = response.content.strip()
        
        print(f"[Task {task_id}] 질문 생성 완료")
        return {
            "question": question,
            "session_id": session_id,
            "task_id": task_id
        }
        
    except Exception as e:
        print(f"[Task {task_id}] 질문 생성 오류: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {
            "question": "그 경험에서 가장 어려웠던 점은 무엇이었나요?",
            "fallback": True,
            "error": str(e),
            "task_id": task_id
        }


# ========== Redis 세션 저장 태스크 ==========

@celery_app.task(name="celery_tasks.save_session_to_redis_task")
def save_session_to_redis_task(
    session_id: str,
    session_data: Dict
) -> Dict:
    """
    세션 데이터를 Redis에 저장 (백업용)
    
    Args:
        session_id: 세션 ID
        session_data: 세션 데이터
    
    Returns:
        저장 결과
    """
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        
        key = f"session:{session_id}"
        r.hset(key, mapping={
            "data": json.dumps(session_data, ensure_ascii=False, default=str),
            "updated_at": datetime.now().isoformat()
        })
        r.expire(key, 86400)  # 24시간 TTL
        
        return {
            "session_id": session_id,
            "status": "saved",
            "key": key
        }
        
    except Exception as e:
        return {
            "session_id": session_id,
            "status": "error",
            "error": str(e)
        }


# ========== 미디어 트랜스코딩 태스크 ==========

@celery_app.task(
    bind=True,
    name="celery_tasks.transcode_recording_task",
    soft_time_limit=600,
    time_limit=660,
    max_retries=2,
    default_retry_delay=30,
)
def transcode_recording_task(
    self,
    session_id: str,
    video_path: str,
    audio_path: str,
    target_bitrate: int = 2000,
    target_audio_bitrate: int = 128,
) -> Dict:
    """
    면접 녹화 영상을 웹 최적화 포맷으로 트랜스코딩합니다.
    GStreamer 우선, FFmpeg 폴백 하이브리드 방식.
    
    워크플로우:
    1. raw 비디오 + raw 오디오 → 먹싱 (Muxing)
    2. H.264 + AAC 트랜스코딩
    3. 썸네일 생성
    4. 원본 raw 파일 삭제
    5. 이벤트 발행 → 프론트엔드 알림
    
    Args:
        session_id: 면접 세션 ID
        video_path: raw 비디오 파일 경로
        audio_path: raw 오디오 파일 경로 (WAV)
        target_bitrate: 비디오 비트레이트 (kbps)
        target_audio_bitrate: 오디오 비트레이트 (kbps)
    
    Returns:
        트랜스코딩 결과 (출력 경로, 파일 크기, 길이 등)
    """
    task_id = self.request.id or "unknown"
    print(f"🎬 [Task {task_id}] 트랜스코딩 시작: {session_id[:8]}...")
    
    _publish_event(
        "recording.transcoding_started",
        session_id=session_id,
        data={"task_id": task_id, "video_path": video_path},
    )
    
    try:
        from media_recording_service import MediaRecordingService
        
        result = MediaRecordingService.transcode(
            session_id=session_id,
            video_path=video_path,
            audio_path=audio_path,
            target_codec="h264",
            target_bitrate=target_bitrate,
            target_audio_bitrate=target_audio_bitrate,
        )
        
        _publish_event(
            "recording.transcoding_completed",
            session_id=session_id,
            data={
                "task_id": task_id,
                "output_path": result.get("output_path"),
                "thumbnail_path": result.get("thumbnail_path"),
                "duration_sec": result.get("duration_sec", 0),
                "file_size_mb": round(result.get("file_size_bytes", 0) / 1024 / 1024, 2),
            },
        )
        
        print(f"✅ [Task {task_id}] 트랜스코딩 완료: {session_id[:8]}...")
        return {
            "session_id": session_id,
            "status": "completed",
            "task_id": task_id,
            **result,
        }
    
    except FileNotFoundError as e:
        print(f"❌ [Task {task_id}] 파일 없음: {e}")
        _publish_event(
            "recording.transcoding_failed",
            session_id=session_id,
            data={"task_id": task_id, "error": str(e)},
        )
        return {"session_id": session_id, "status": "error", "error": str(e)}
    
    except Exception as e:
        print(f"❌ [Task {task_id}] 트랜스코딩 오류: {e}")
        _publish_event(
            "recording.transcoding_failed",
            session_id=session_id,
            data={"task_id": task_id, "error": str(e)},
        )
        # 재시도
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"session_id": session_id, "status": "error", "error": str(e)}


@celery_app.task(
    bind=True,
    name="celery_tasks.cleanup_recording_task",
    soft_time_limit=60,
    time_limit=90,
)
def cleanup_recording_task(
    self,
    session_id: str,
    file_paths: List[str],
) -> Dict:
    """
    녹화 관련 파일들을 정리 (삭제)합니다.
    세션 만료 또는 사용자 요청 시 호출됩니다.
    """
    removed = []
    errors = []
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
    
    return {
        "session_id": session_id,
        "removed": removed,
        "errors": errors,
        "status": "completed" if not errors else "partial",
    }


# ========== 헬퍼 함수 ==========

def run_async(coro):
    """비동기 함수를 동기적으로 실행"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
