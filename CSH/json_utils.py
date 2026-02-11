"""
JSON Resilience 유틸리티
========================
LLM 응답에서 JSON을 안정적으로 추출하고 파싱하는 방어 로직

주요 기능:
1. Markdown 코드블록(```json ... ```) 자동 제거
2. Qwen3 <think>...</think> 사고 블록 제거
3. JSON 앞뒤의 불필요한 텍스트(설명문) 자동 제거
4. trailing comma, 제어문자 등 흔한 구문 오류 자동 수정
5. 중첩된 JSON에서 가장 바깥쪽 객체/배열 추출
6. 다단계 파싱 시도 (원본 → 정제 → 정규식 추출 → fallback)
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def resilient_json_parse(
    text: str,
    fallback: Optional[Any] = None,
    expect_type: Optional[type] = None,
    context: str = ""
) -> Any:
    """
    LLM 응답 텍스트에서 JSON을 안정적으로 추출하고 파싱합니다.
    
    Args:
        text: LLM 응답 원문 (JSON + 설명문 혼합 가능)
        fallback: 모든 파싱 시도 실패 시 반환할 기본값 (None이면 빈 dict)
        expect_type: 기대하는 결과 타입 (dict, list). 타입 불일치 시 fallback 반환
        context: 로깅용 컨텍스트 문자열 (어디서 호출했는지)
        
    Returns:
        파싱된 JSON 객체 (dict/list) 또는 fallback 값
    """
    if fallback is None:
        fallback = {}
    
    if not text or not isinstance(text, str):
        logger.warning(f"[JSON Resilience]{f' ({context})' if context else ''} 빈 입력")
        return fallback
    
    log_prefix = f"[JSON Resilience]{f' ({context})' if context else ''}"
    
    # ========== 1단계: 전처리 ==========
    cleaned = _preprocess(text)
    
    # ========== 2단계: 다단계 파싱 시도 ==========
    strategies = [
        ("직접 파싱", lambda: json.loads(cleaned)),
        ("코드블록 추출", lambda: _parse_from_codeblock(cleaned)),
        ("가장 바깥쪽 JSON 객체 추출", lambda: _extract_outermost_json(cleaned, "object")),
        ("가장 바깥쪽 JSON 배열 추출", lambda: _extract_outermost_json(cleaned, "array")),
        ("구문 오류 수정 후 파싱", lambda: _parse_with_fixes(cleaned)),
        ("정규식 greedy 추출", lambda: _regex_extract(cleaned)),
    ]
    
    for name, strategy in strategies:
        try:
            result = strategy()
            if result is not None:
                # 타입 검증
                if expect_type and not isinstance(result, expect_type):
                    logger.debug(f"{log_prefix} '{name}' 성공했으나 타입 불일치: "
                                f"기대={expect_type.__name__}, 실제={type(result).__name__}")
                    continue
                logger.debug(f"{log_prefix} '{name}' 전략으로 파싱 성공")
                return result
        except (json.JSONDecodeError, ValueError, IndexError, KeyError):
            continue
        except Exception as e:
            logger.debug(f"{log_prefix} '{name}' 예외: {e}")
            continue
    
    # ========== 3단계: 모든 시도 실패 → fallback ==========
    # 원문 앞 200자만 로그에 표시 (너무 긴 텍스트 방지)
    preview = text[:200].replace('\n', '\\n')
    logger.warning(f"{log_prefix} 모든 파싱 전략 실패. 원문 미리보기: {preview}...")
    return fallback


# ==================== 내부 헬퍼 함수 ====================

def _preprocess(text: str) -> str:
    """LLM 응답 전처리: thinking 블록 제거, 제어문자 정리"""
    # 1) Qwen3 <think>...</think> 블록 제거
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.DOTALL)
    
    # 2) 제어문자 제거 (탭, 개행은 유지)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    
    return text.strip()


def _parse_from_codeblock(text: str) -> Optional[Any]:
    """```json ... ``` 또는 ``` ... ``` 코드블록에서 JSON 추출"""
    # ```json ... ``` 패턴 (가장 일반적)
    patterns = [
        r'```json\s*\n?([\s\S]*?)```',   # ```json ... ```
        r'```\s*\n?([\s\S]*?)```',         # ``` ... ```
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            content = match.strip()
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # 구문 오류 수정 시도
                    fixed = _apply_json_fixes(content)
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        continue
    return None


def _extract_outermost_json(text: str, target: str = "object") -> Optional[Any]:
    """
    괄호 매칭으로 가장 바깥쪽 JSON 객체 또는 배열 추출
    단순 정규식보다 중첩 구조를 정확하게 처리
    """
    open_char = '{' if target == "object" else '['
    close_char = '}' if target == "object" else ']'
    
    start_idx = text.find(open_char)
    if start_idx == -1:
        return None
    
    depth = 0
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                json_str = text[start_idx:i + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    fixed = _apply_json_fixes(json_str)
                    return json.loads(fixed)
    
    return None


def _parse_with_fixes(text: str) -> Optional[Any]:
    """흔한 JSON 구문 오류를 수정한 뒤 파싱"""
    # 코드블록이 있으면 먼저 추출
    content = text
    if "```" in content:
        for pattern in [r'```json\s*\n?([\s\S]*?)```', r'```\s*\n?([\s\S]*?)```']:
            match = re.search(pattern, content)
            if match:
                content = match.group(1)
                break
    
    fixed = _apply_json_fixes(content.strip())
    return json.loads(fixed)


def _apply_json_fixes(text: str) -> str:
    """흔한 JSON 구문 오류 수정"""
    s = text.strip()
    
    # 1) trailing comma 제거: ,} → }, ,] → ]
    s = re.sub(r',\s*([}\]])', r'\1', s)
    
    # 2) 작은따옴표 → 큰따옴표 (JSON 키/값에서)
    #    단, 문자열 내부의 작은따옴표(apostrophe)는 유지해야 하므로 보수적으로 처리
    s = re.sub(r"(?<=[\[{,:\s])'([^']*)'(?=\s*[,}\]:])", r'"\1"', s)
    
    # 3) 키에 따옴표 누락: { key: "value" } → { "key": "value" }
    s = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)
    
    # 4) 숫자 뒤 불필요한 텍스트 (예: "score": 5점 → "score": 5)
    s = re.sub(r':\s*(\d+)\s*[가-힣]+([,}\]])', r': \1\2', s)
    
    # 5) NaN, Infinity → null
    s = re.sub(r'\bNaN\b', 'null', s)
    s = re.sub(r'\bInfinity\b', 'null', s)
    s = re.sub(r'-Infinity\b', 'null', s)
    
    # 6) 여러 줄 주석 제거 (// ... )
    s = re.sub(r'//[^\n]*', '', s)
    
    # 7) 줄 끝 콤마 뒤 빈 줄 정리
    s = re.sub(r',\s*\n\s*\n', ',\n', s)
    
    return s


def _regex_extract(text: str) -> Optional[Any]:
    """정규식으로 가장 큰 JSON 블록 추출 (최후 수단)"""
    # 가장 큰 {...} 블록을 greedy로 찾기
    matches = re.findall(r'\{[\s\S]*\}', text)
    if matches:
        # 가장 긴 매치를 사용 (가장 바깥쪽일 가능성 높음)
        longest = max(matches, key=len)
        fixed = _apply_json_fixes(longest)
        return json.loads(fixed)
    
    # 배열 시도
    matches = re.findall(r'\[[\s\S]*\]', text)
    if matches:
        longest = max(matches, key=len)
        fixed = _apply_json_fixes(longest)
        return json.loads(fixed)
    
    return None


# ==================== 편의 함수 ====================

def parse_evaluation_json(text: str, context: str = "evaluation") -> Dict:
    """
    답변 평가용 JSON 파싱 (scores, total_score 등 포함)
    파싱 실패 시 안전한 기본 평가를 반환
    """
    default_eval = {
        "scores": {
            "problem_solving": 3,
            "logic": 3,
            "technical": 3,
            "star": 3,
            "communication": 3
        },
        "total_score": 15,
        "recommendation": "불합격",
        "recommendation_reason": "JSON 파싱 실패로 기본 평가 적용",
        "strengths": ["답변을 완료했습니다."],
        "improvements": ["더 구체적인 예시를 들어보세요."],
        "brief_feedback": "답변을 분석 중입니다.",
        "fallback": True
    }
    
    result = resilient_json_parse(text, fallback=default_eval, expect_type=dict, context=context)
    
    # 필수 키 검증 및 보정
    if "scores" not in result:
        result["scores"] = default_eval["scores"]
    if "total_score" not in result:
        scores = result.get("scores", {})
        result["total_score"] = sum(scores.values()) if isinstance(scores, dict) else 15
    if "strengths" not in result:
        result["strengths"] = default_eval["strengths"]
    if "improvements" not in result:
        result["improvements"] = default_eval["improvements"]
    if "brief_feedback" not in result:
        result["brief_feedback"] = default_eval["brief_feedback"]
    
    return result


def parse_code_analysis_json(text: str, context: str = "code_analysis") -> Dict:
    """
    코드 분석용 JSON 파싱 (overall_score, correctness 등 포함)
    파싱 실패 시 안전한 기본 분석 결과를 반환
    """
    default_analysis = {
        "overall_score": 0,
        "correctness": {"score": 0, "feedback": "분석 실패"},
        "time_complexity": {"notation": "N/A", "score": 0, "feedback": "분석 실패"},
        "space_complexity": {"notation": "N/A", "score": 0, "feedback": "분석 실패"},
        "code_style": {"score": 0, "feedback": "분석 실패"},
        "comments": {"score": 0, "feedback": "분석 실패"},
        "best_practices": {"score": 0, "feedback": "분석 실패"},
        "feedback": ["AI 분석을 완료하지 못했습니다."],
        "detailed_analysis": "JSON 파싱 실패로 기본 분석 결과를 반환합니다.",
        "fallback": True
    }
    
    result = resilient_json_parse(text, fallback=default_analysis, expect_type=dict, context=context)
    
    # 필수 키 보정
    if "overall_score" not in result:
        result["overall_score"] = 0
    if "feedback" not in result:
        result["feedback"] = default_analysis["feedback"]
    
    return result


def parse_architecture_json(text: str, context: str = "architecture") -> Dict:
    """
    아키텍처 문제/평가용 JSON 파싱
    파싱 실패 시 안전한 기본값 반환
    """
    default_arch = {
        "diagram_recognition": {"components": [], "connections": [], "data_flows": []},
        "architecture_evaluation": {
            "structure_score": 0,
            "scalability_score": 0,
            "security_score": 0,
            "performance_score": 0
        },
        "component_analysis": [],
        "strengths": [],
        "weaknesses": [],
        "feedback": ["분석을 완료하지 못했습니다."],
        "detailed_analysis": "JSON 파싱 실패로 기본 결과를 반환합니다.",
        "fallback": True
    }
    
    return resilient_json_parse(text, fallback=default_arch, expect_type=dict, context=context)
