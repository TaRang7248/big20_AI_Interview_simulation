import re
import json
from dataclasses import dataclass, asdict
from typing import List, Dict

# 1) 전처리
def clean_text(s: str) -> str:
    s = s.replace("\u200b", "").strip()  # zero-width 제거
    s = re.sub(r"\s+", " ", s)           # 공백 정리
    return s

# 2) 질문 분류 (룰 기반)
def classify_question(q: str) -> str:
    q_lower = q.lower()

    # 경험/사례
    if any(k in q for k in ["경험", "사례", "활동", "수행", "프로젝트", "갈등", "해결"]):
        return "experience"

    # 역량/강점/준비
    if any(k in q for k in ["역량", "강점", "준비", "노력", "개발", "전문성", "자기개발"]):
        return "competency"

    # 지원동기/포부/비전
    if any(k in q for k in ["지원", "동기", "포부", "계획", "비전", "성장", "목표"]):
        return "motivation"

    # 직무 이해/정의
    if any(k in q for k in ["직무", "역할", "특징", "정의", "중요성", "덕목"]):
        return "job_understanding"

    return "other"

# 3) 답변 생성 (템플릿 기반)
TEMPLATES: Dict[str, str] = {
    "job_understanding": (
        "해당 직무는 조직의 목표 달성을 위해 필요한 정보를 수집·정리하고, "
        "문제를 구조화해 실행 가능한 대안을 제시하는 역할을 수행합니다. "
        "저는 업무를 ‘문제 정의 → 근거 수집(데이터/문서) → 분석/정리 → 실행안 제시 → 결과 점검’의 흐름으로 이해하고 있습니다. "
        "특히 이해관계자 관점에서 요구사항을 명확히 하고, 결과를 전달 가능한 형태로 문서화하는 역량이 중요하다고 생각합니다. "
        "입사 후에는 업무 지표와 산출물 기준을 먼저 파악한 뒤, 반복 업무를 표준화하고 개선 포인트를 데이터로 검증하여 "
        "효율과 품질을 동시에 높이는 방식으로 기여하겠습니다."
    ),
    "competency": (
        "제가 가진 차별화된 역량은 문제를 구조화해 우선순위를 세우고, "
        "근거 중심으로 설명·정리하는 능력입니다. 이를 위해 학습과 프로젝트에서 "
        "요구사항을 정리하고, 핵심 지표를 설정한 뒤 결과를 문서로 남기는 훈련을 반복해왔습니다. "
        "또한 팀 단위 과제에서 역할 분담과 일정 조율을 하며 협업 과정의 리스크를 줄이는 데 집중했습니다. "
        "이러한 경험은 실무에서 제한된 시간과 자원 안에서 합리적인 결정을 돕고, "
        "업무 산출물을 재사용 가능하게 만드는 데 도움이 된다고 생각합니다. "
        "입사 후에도 업무 이해를 빠르게 확장하며, 개선 제안을 실행 가능한 형태로 제시하겠습니다."
    ),
    "experience": (
        "직무 관련 경험으로는 팀 기반 과제/프로젝트 수행 과정이 가장 의미 있었습니다. "
        "당시 저는 문제 정의와 자료 정리, 결과 정합성 점검을 담당했습니다. "
        "초기에는 목표가 모호해 산출물이 흔들렸지만, 요구사항을 문장으로 정리하고 "
        "검증 기준(지표/체크리스트)을 합의하면서 방향성을 고정했습니다. "
        "이후 분석/정리 결과를 공유 가능한 형식(요약 문서, 표, 근거 링크)으로 만들어 "
        "팀 의사결정 속도를 높였습니다. "
        "이 경험을 통해 ‘좋은 결과’보다 ‘재현 가능한 과정’이 중요하다는 것을 배웠고, "
        "실무에서도 동일한 방식으로 문제를 관리하며 기여하겠습니다."
    ),
    "motivation": (
        "지원 동기는 제가 가진 역량을 가장 실제적인 방식으로 발휘할 수 있는 환경이라고 판단했기 때문입니다. "
        "저는 단순 수행보다 ‘왜 이 일이 필요한가’를 정의하고, 근거를 정리해 실행안을 만드는 과정에 강점이 있습니다. "
        "이를 위해 직무 관련 학습과 프로젝트를 통해 문제 해결 흐름을 반복적으로 연습했고, "
        "결과를 문서화하여 공유하는 습관을 만들었습니다. "
        "입사 후에는 초기에는 업무 기준과 데이터를 빠르게 파악하고, "
        "중장기적으로는 업무 지표 개선 및 표준화에 기여하는 인재로 성장하고 싶습니다. "
        "조직의 의사결정이 더 빠르고 정확해지도록 돕는 역할을 꾸준히 수행하겠습니다."
    ),
    "other": (
        "질문 의도를 ‘업무 관점에서의 핵심 요구’로 해석한 뒤, 결론-근거-사례-기여 순으로 답변하겠습니다. "
        "저는 경험을 정리할 때 과정과 기준을 명확히 하여, 재현 가능한 형태로 설명하는 것을 중요하게 생각합니다. "
        "입사 후에는 빠르게 업무 맥락을 익히고, 결과물 품질과 협업 효율을 동시에 높이는 방향으로 기여하겠습니다."
    ),
}

def generate_answer(q: str, q_type: str, target_min_chars: int = 350) -> str:
    base = TEMPLATES.get(q_type, TEMPLATES["other"])
    if len(base) < target_min_chars:
        add = (
            " 또한 업무를 수행하며 발생하는 이슈를 기록하고, 원인-대응-결과를 남겨 "
            "다음 반복 작업에서 동일한 문제가 재발하지 않도록 관리하겠습니다."
        )
        # ver0.8: 무한 반복(while) 대신 1회만 덧붙여 과다 부풀림 방지
        base += add
    return base

# 4) 평가(정답 없이 가능한 평가)
def evaluate_answer(q: str, a: str) -> Dict[str, object]:
    score = 0
    feedback = []

    # 길이
    if 600 <= len(a) <= 900:
        score += 40
    else:
        feedback.append(f"길이 조정 필요(현재 {len(a)}자).")
        score += max(0, 40 - abs(len(a) - 750) // 20)

    # 구조 키워드(결론/근거/경험/기여 느낌)
    structure_hits = sum(1 for k in ["역할", "경험", "기여", "입사 후", "중요"] if k in a)
    score += min(40, structure_hits * 10)
    if structure_hits < 3:
        feedback.append("구조 요소(경험/근거/기여) 표현을 더 포함하면 좋음.")

    # 문장 다양성(아주 단순 체크)
    if len(set(a.split())) / max(1, len(a.split())) > 0.35:
        score += 20
    else:
        feedback.append("표현이 반복되는 편이라 문장 다양성 개선 필요.")

    return {"score": int(score), "feedback": feedback}

# 5) 실행

@dataclass
class QAItem:
    session_id: str
    turn: int
    question: str
    q_type: str
    user_answer: str
    model_answer: str
    score: int
    feedback: List[str]



FOLLOW_UP: Dict[str, str] = {
    "motivation": "좋아요. 그 동기를 뒷받침하는 구체적인 경험 한 가지를 말해줄 수 있나요?",
    "experience": "그 상황에서 본인이 맡은 역할과 결과를 조금 더 구체적으로 말해볼까요?",
    "competency": "그 역량을 보여준 사례를 하나 더 들어볼 수 있나요?",
    "job_understanding": "그 직무에서 성과를 판단하는 기준(지표)은 무엇이라고 생각하나요?",
    "other": "조금 더 구체적으로(상황-행동-결과) 순서로 말해볼까요?",
}
def next_question(prev_q: str, prev_type: str, user_answer: str) -> str:
    ua = user_answer

    # 직무 이해 → 역량 연결
    if prev_type == "job_understanding":
        if any(k in ua for k in ["수집", "정리", "구조화", "대안", "의사결정"]):
            return "좋아요. 그 역할을 잘 수행하기 위해 가장 중요한 역량은 무엇이라고 생각하나요?"
        return FOLLOW_UP["job_understanding"]

    # 지원동기 → 경험
    if prev_type == "motivation":
        return FOLLOW_UP["motivation"]

    # 경험 → 역할/성과
    if prev_type == "experience":
        if any(k in ua for k in ["결과", "성과", "개선", "%", "단축"]):
            return "그 결과를 만들기 위해 본인이 직접 한 핵심 행동은 무엇이었나요?"
        return FOLLOW_UP["experience"]

    return FOLLOW_UP.get(prev_type, FOLLOW_UP["other"])

def next_question(prev_type: str) -> str:
    return FOLLOW_UP.get(prev_type, FOLLOW_UP["other"])



def run_interview(session_id: str, first_question: str, max_turns: int = 5) -> List[QAItem]:
    items: List[QAItem] = []
    current_question = first_question

    for turn in range(1, max_turns + 1):
        q_clean = clean_text(current_question)
        q_type = classify_question(q_clean)

        print(f"\n[Q{turn}] {q_clean}")
        user_input = input("A> ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break

        user_clean = clean_text(user_input)

        # 모델 답변(여기서는 템플릿 기반 예시답안 역할)
        model_answer = generate_answer(q_clean, q_type)

        # 사용자의 답변을 평가(룰 기반)
        eval_res = evaluate_answer(q_clean, user_clean)

        items.append(QAItem(
            session_id=session_id,
            turn=turn,
            question=q_clean,
            q_type=q_type,
            user_answer=user_clean,
            model_answer=model_answer,
            score=eval_res["score"],
            feedback=eval_res["feedback"],
        ))

        # 다음 질문
        current_question = next_question(q_type)
        print(f"(debug) q_type={q_type}") # 분류 확인용 ( 나중에 제거 가능 )
        
        current_question = next_question(
            prev_q=q_clean,
            prev_type=q_type,
            user_answer=user_clean
        )

    return items


def save_jsonl(items: List[QAItem], path: str):
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    session_id = "local_session_001"
    first_question = "지원 직무의 특징과 역할에 대해 아는 대로 말해주세요! (700자)"

    items = run_interview(session_id, first_question, max_turns=5)
    save_jsonl(items, "turn_outputs.jsonl")
    print("saved:", len(items))
