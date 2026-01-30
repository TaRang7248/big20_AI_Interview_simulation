# OpenAI LLM을 활용한 간단한 텍스트 기반 AI 면접 프로그램
# LangChain 라이브러리를 사용하여 OpenAI의 Chat 모델과 대화하며, 면접관 페르소나를 가진 AI가 질문을 하고 사용자가 답하는 방식으로 구현

# 운영체제(OS)의 기능을 파이썬에서 사용할 수 있게 해주는 모듈. 주로 API 키와 같은 환경 변수를 .env 파일에서 가져올 때 사용
import os
# 파이썬 인터프리터와 시스템 관련 설정을 제어
import sys
# .env 파일에 저장된 비밀 정보(OpenAI API 키 등)를 읽어와서 시스템 환경 변수로 등록해 주는 도구
from dotenv import load_dotenv
# LangChain에서 제공하는 Ollama 전용 채팅 모델 연결 도구. 이를 통해 Llama 3 같은 모델과 대화할 수 있다.
from langchain_ollama import ChatOllama
# RAG 기능을 위한 모듈 임포트
from resume_rag import ResumeRAG
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
    print("AI 면접 시스템을 시작합니다... (On-premise Llama 3 사용)")

    # 1. RAG 초기화 및 이력서 인덱싱
    # DB 연결 문자열은 환경 변수에서 읽거나 기본값 사용 (사용자 환경에 맞게 수정 필요)
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/interview_db")
    print(f"Connecting to Vector DB: {db_url} (Check .env if fails)")
    
    rag = ResumeRAG(connection_string=db_url)
    
    # 이력서 파일 확인
    resume_path = os.path.join(current_dir, "resume.pdf")
    if os.path.exists(resume_path):
        print(f"'{resume_path}' 파일이 발견되었습니다.")
        do_index = input("이력서를 DB에 새로 인덱싱하시겠습니까? (y/n, default: n): ").strip().lower()
        if do_index == 'y':
            rag.clear_collection() # 기존 데이터 삭제 (중복 방지)
            rag.load_and_index_pdf(resume_path)
    else:
        print(f"Warning: '{resume_path}' 파일을 찾을 수 없습니다. RAG 기능이 제한될 수 있습니다.")
        print("CSH 폴더에 'resume.pdf'를 배치해주세요.")

    # Retriever 생성
    retriever = rag.get_retriever()
    
    # LLM 초기화 (Ollama 로컬 모델 사용)
    llm = ChatOllama(model="llama3", temperature=0.7)

    # 시스템 프롬프트: 면접관의 페르소나 설정
    system_prompt = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 이력서 내용과 답변을 바탕으로 기술 스택과 경험에 대해 심도 있는 질문을 던지세요.
제공된 '참고용 이력서 내용'을 적극 활용하여 구체적인 질문을 하세요.

[중요 규칙]
1. 답변이 부실하면 구체적인 예시를 요구하거나 꼬리 질문을 하세요.
2. 꼬리 질문은 주제당 최대 2번까지만 허용합니다. 
3. 동일한 기술적 주제에 대해 2번의 답변을 들었다면, "알겠습니다. 다음은..."이라며 주제를 전환하세요.
4. 질문은 한 번에 하나만 하세요.

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
            
            if not user_input.strip():
                continue

            # RAG: 사용자 답변과 관련된 이력서 내용 검색
            # (초기 자기소개 등에서도 이력서 전체 맥락이 필요할 수 있으나, 여기서는 대화 흐름에 따른 Context 검색 구현)
            retrieved_docs = retriever.invoke(user_input)
            context_text = "\n".join([doc.page_content for doc in retrieved_docs])
            
            # 검색된 컨텍스트가 있다면 프롬프트에 주입
            context_message = None
            if context_text:
                context_message = SystemMessage(content=f"--- [RAG System] 참고용 이력서 관련 내용 ---\n{context_text}\n------------------------------------------")
                # 디버깅용: 검색된 내용이 있는지 출력해볼 수 있음 (선택 사항)
                # print(f"(Debug) Retrieved Context Length: {len(context_text)}")

            # 대화 기록 구성: [System, History..., User Input, (Context - Inserted temporarily)]
            # 주의: ChatHistory에 영구 저장하지 않고, 이번 턴의 추론에만 사용
            messages_for_inference = list(chat_history)
            messages_for_inference.append(HumanMessage(content=user_input))
            
            if context_message:
                messages_for_inference.append(context_message)

            # LLM 응답 생성
            print("\n(AI가 생각 중입니다... 내용을 분석하고 있습니다...)")
            response = llm.invoke(messages_for_inference)
            
            print(f"\nAI 면접관: {response.content}")

            # 실제 대화 기록에는 User Input과 AI Response만 저장 (Context는 중복 저장 안 함)
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(response)

        except KeyboardInterrupt:
            print("\n\n면접이 강제로 종료되었습니다.")
            break
        except Exception as e:
            print(f"\n오류가 발생했습니다: {e}")
            # 에러 상세 출력 (디버깅용)
            import traceback
            traceback.print_exc()
            break

if __name__ == "__main__":
    main()
