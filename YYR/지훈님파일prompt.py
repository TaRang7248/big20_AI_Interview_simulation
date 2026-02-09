import json
import time
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tqdm import tqdm

# 1. 설정
OUT_JSON_PATH = Path(r"C:\Users\TJ\Desktop\test.json")
SAVE_INTERVAL = 10  # 10개 처리할 때마다 중간 저장

# 2. 데이터 로드
if not OUT_JSON_PATH.exists():
    print(f"파일을 찾을 수 없습니다: {OUT_JSON_PATH}")
    qa_data = [] # 혹은 종료 처리
else:
    with open(OUT_JSON_PATH, "r", encoding="utf-8") as f:
        qa_data = json.load(f)
    print(f"데이터 로드 완료: {len(qa_data)}개의 질문이 있습니다.")

# 3. LLM 설정
llm = ChatOllama(model="qwen3-vl:30b", temperature=0.1) # 모범답안의 일관성을 위해 온도를 더 낮춤

# ---------------------------------------------------------
# [수정됨] 한국어 출력 강제 및 루브릭 반영 프롬프트
# ---------------------------------------------------------
system_prompt_text = """
당신은 {category} 직무의 최고 전문가이자 면접 평가관입니다.
지원자의 질문에 대해 **평가 기준 만점(5점/5점)**을 받을 수 있는 완벽한 '모범 답안(Gold Standard)'을 작성하십시오.

[필수 제약 조건]
1. **언어 (Language):** 모든 답변은 반드시 자연스럽고 전문적인 **한국어(Korean)**로 작성하십시오. 영어 사용은 기술 용어 표기(예: React, Over-fitting)에만 한정합니다.

[답안 작성 시 준수해야 할 5점 평가 기준]
1. **구조화된 논리 (Logic):** - 답변은 반드시 **두괄식(결론부터 제시)**으로 시작하십시오. 
   - 경험 질문은 **STAR 기법(상황-과제-행동-결과)**을 따르고, 기술 질문은 **'개념-원리-장단점(Trade-off)-실무사례'** 순서로 구조화하십시오.

2. **구체성 및 수치화 (Quantifiable):**
   - 모호한 표현 대신 **구체적인 수치(예: 효율 20% 개선, O(n) 복잡도 등)**나 명확한 기술 용어를 사용하십시오.
   - 단순한 정의 나열이 아니라, **엣지 케이스(Edge Case)**나 예외 상황에 대한 고려를 포함하십시오. 

3. **형식 (Format):**
   - 서론/결론의 불필요한 인사말(예: "Here is the answer", "좋은 질문입니다")은 절대 포함하지 마십시오.
   - 3~6문장 내외의 정제된 줄글(Paragraph) 형태로 작성하십시오.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt_text),
    ("user", "질문: {question}")
])

# OutputParser 연결
chain = prompt | llm | StrOutputParser()

# 4. 실행 및 중간 저장 로직
print("답변 생성을 시작합니다...")
modified_count = 0

try:
    for i, item in enumerate(tqdm(qa_data)):
        # [수정 전] 이미 답변이 있으면 건너뜀 
        # if item.get("답변") and item["답변"].strip() != "":
        #     continue
        
        # [수정 후] 조건문 없이 무조건 실행하여 덮어쓰기
        q_text = item.get("질문", "")
        # 데이터에 카테고리가 있으면 쓰고, 없으면 기본값 사용
        category = item.get("category", "IT 소프트웨어 개발") 
        
        if q_text:
            try:
                # invoke 호출
                answer = chain.invoke({"category": category, "question": q_text})
                
                # 결과 저장
                item["답변"] = answer.strip()
                modified_count += 1
                
                # 중간 저장 (데이터 유실 방지)
                if modified_count % SAVE_INTERVAL == 0:
                    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
                        json.dump(qa_data, f, ensure_ascii=False, indent=2)
                        
            except Exception as e:
                print(f"\n[Error] 질문 '{q_text[:20]}...' 처리 중 오류: {e}")
                # 에러 발생 시 잠시 대기 후 재시도 로직을 넣을 수도 있음
                time.sleep(2)

except KeyboardInterrupt:
    print("\n사용자에 의해 작업이 중단되었습니다. 현재까지의 진행 상황을 저장합니다.")

# 5. 최종 저장
if modified_count > 0:
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(qa_data, f, ensure_ascii=False, indent=2)
    print(f"\n완료! 총 {modified_count}개의 답변이 생성/업데이트 되었습니다.")
else:
    print("\n새로 생성된 답변이 없습니다.")