# OpenAI LLM을 활용한 간단한 텍스트 기반 AI 면접 프로그램
# LangChain 라이브러리를 사용하여 OpenAI의 Chat 모델과 대화하며, 면접관 페르소나를 가진 AI가 질문을 하고 사용자가 답하는 방식으로 구현

# 운영체제(OS)의 기능을 파이썬에서 사용할 수 있게 해주는 모듈. 주로 API 키와 같은 환경 변수를 .env 파일에서 가져올 때 사용
import os
# 파이썬 인터프리터와 시스템 관련 설정을 제어
import sys
# .env 파일에 저장된 비밀 정보(OpenAI API 키 등)를 읽어와서 시스템 환경 변수로 등록해 주는 도구
from dotenv import load_dotenv
# LangChain에서 제공하는 OpenAI 전용 채팅 모델 연결 도구. 이를 통해 GPT-4o 같은 모델과 대화할 수 있다.
from langchain_openai import ChatOpenAI
# ChatPromptTemplate: AI에게 줄 명령문(프롬프트)의 틀을 만든다
# MessagesPlaceholder: 대화 내용이 들어갈 '빈자리'를 만든다. 이전 대화 기록을 통째로 갈아 끼울 때 사용.
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# AI 대화에 쓰이는 메시지 타입을 정의
# HumanMessage: 사용자가 입력한 메시지
# AIMessage: AI가 생성한 메시지
# SystemMessage: AI의 인격(페르소나)과 규칙을 부여하는 메시지
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 프로젝트 루트에서 .env 파일을 찾기 위해 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# 프로젝트 폴더에 있는 .env 파일에 적힌 설정값들을 읽어서 파이썬 프로그램이 사용할 수 있도록 환경 변수로 등록해주는 함수
load_dotenv() 

def main(): # 프로그램의 메인 로직을 담는 함수
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: .env 파일에 OPENAI_API_KEY가 설정되지 않았습니다.")
        return # 함수 종료

    print("AI 면접 시스템을 시작합니다...")

    # LLM 초기화 (모델은 필요에 따라 변경 가능, 예: gpt-3.5-turbo, gpt-4)
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    # 시스템 프롬프트: 면접관의 페르소나 설정
    system_prompt = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 기술 스택과 경험에 대해 심도 있는 질문을 던지세요.
답변이 부실하면 구체적인 예시를 요구하거나 꼬리 질문을 하세요.

꼬리 질문은 주제당 최대 2번까지만 허용합니다. 

[중요 규칙]
1. 동일한 기술적 주제에 대해 2번의 답변을 들었다면, 반드시 "알겠습니다. 다음은 다른 주제로 넘어가죠."라고 말한 뒤 완전히 새로운 분야(예: 네트워크, DB, 인성 등)의 질문을 던지세요.
2. 현재 질문이 몇 번째 꼬리 질문인지 스스로 체크하되, 답변에 꼬리 질문 횟수를 표시하지 마세요. 

질문을 할 때 너무 공격적이지 않게, 정중하지만 날카로운 태도를 유지하세요.
면접은 자기소개로 시작합니다."""

    # 대화 기록 관리
    chat_history = [
        SystemMessage(content=system_prompt)
    ]

    print(f"\n[{'='*30} AI 면접 시작 {'='*30}]")
    initial_greeting = "안녕하세요. 오늘 면접을 진행하게 된 면접관입니다. 먼저 간단한 자기소개를 부탁드립니다."
    print(f"AI 면접관: {initial_greeting}")
    chat_history.append(AIMessage(content=initial_greeting))

    while True: # 무한 루프
        try:
            user_input = input("\n지원자 (종료하려면 'exit' 입력): ")
            if user_input.lower().strip() in ["exit", "종료", "quit"]:
                print("\nAI 면접관: 면접을 종료합니다. 수고하셨습니다.")
                break
            
            # 아무 내용도 입력하지 않고 엔터만 쳤을 때를 처리. 내용이 비어있으면 AI에게 빈 값을 보낼 필요가 없으므로, 아래 로직(AI 호출 등)을 무시하고 다시 루프의 처음으로 돌아가 입력을 다시 기다린다.
            if not user_input.strip():
                continue

            # 사용자 입력을 대화 기록에 추가
            chat_history.append(HumanMessage(content=user_input))

            # LLM 응답 생성
            # stream을 사용하여 타자기 효과를 낼 수도 있지만, 여기서는 간단히 invoke 사용
            response = llm.invoke(chat_history)
            
            print(f"\nAI 면접관: {response.content}")

            # AI 응답을 대화 기록에 추가
            chat_history.append(response)

        except KeyboardInterrupt:
            print("\n\n면접이 강제로 종료되었습니다.")
            break
        except Exception as e:
            print(f"\n오류가 발생했습니다: {e}")
            break

if __name__ == "__main__":
    main()
