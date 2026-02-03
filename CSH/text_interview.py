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

import psycopg2

# 프로젝트 루트에서 .env 파일을 찾기 위해 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# 프로젝트 폴더에 있는 .env 파일에 적힌 설정값들을 읽어서 파이썬 프로그램이 사용할 수 있도록 환경 변수로 등록해주는 함수
load_dotenv() 

def main(): # 프로그램의 메인 로직을 담는 함수
    print("AI 면접 시스템을 시작합니다")

    # 환경 변수를 사용해 데이터베이스 연결 정보를 안전하게 가져오고, 이를 바탕으로 RAG(검색 증강 생성) 시스템을 초기화
    CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")
    
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    
    # 객체 초기화: 위에서 가져온 DB 주소를 ResumeRAG라는 클래스에 전달. 클래스 내부에서 DB 주소를 받아 PostgreSQL(PGVector)에 접속하고, 지원자의 이력서 데이터를 조회할 준비를 마친다.
    rag = ResumeRAG(connection_string=CONNECTION_STRING)
    
    # 이력서 파일 확인
    resume_path = os.path.join(current_dir, "resume.pdf")
    if os.path.exists(resume_path):
        print(f"'{resume_path}' 파일이 발견되었습니다.")
        do_index = input("이력서를 DB에 새로 인덱싱하시겠습니까? (y/n, default: n): ").strip().lower()
        if do_index == 'y':
            rag.clear_collection() # 기존 데이터 삭제 (중복 방지)
            # PDF 파일을 읽어서 텍스트로 쪼갠 뒤, 벡터(숫자)로 변환하여 DB에 저장
            rag.load_and_index_pdf(resume_path)
    else:
        print(f"Warning: '{resume_path}' 파일을 찾을 수 없습니다. RAG 기능이 제한될 수 있습니다.")
        print("CSH 폴더에 'resume.pdf'를 배치해주세요.")

    # 인덱싱(Indexing)되어 DB에 저장된 방대한 데이터 중, 질문과 가장 관련 있는 내용을 골라내는 '검색기'를 가져오는 코드
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

            # 사용자의 질문(user_input)을 바탕으로 DB에서 관련 있는 문서 조각들을 실제로 가져온다
            # 질문을 벡터(숫자)로 바꾼 뒤, DB에 저장된 이력서 조각들 중 숫자가 가장 비슷한 것들을 골라낸다
            # 결과값인 retrieved_docs는 문서 객체들의 리스트(List) 형태이다 (예: [문서1, 문서2, 문서3])
            retrieved_docs = retriever.invoke(user_input)
            # 리스트 형태의 문서들을 AI가 읽기 편하도록 하나의 긴 텍스트로 합치는 과정
            context_text = "\n".join([doc.page_content for doc in retrieved_docs])
            
            # 검색된 컨텍스트가 있다면 프롬프트에 주입
            # context_message라는 변수를 생성하고 초기값을 None으로 설정. 검색 결과가 없을 경우를 대비해 변수를 미리 초기화해두는 과정.
            context_message = None
            # context_text: 벡터 DB 등에서 검색해온 텍스트 데이터
            if context_text:
                context_message = SystemMessage(content=f"--- [RAG System] 참고용 이력서 관련 내용 ---\n{context_text}\n------------------------------------------")

            # 사용자의 질문(user_input)과 이전 대화 기록(chat_history)을 합쳐서 AI 모델에게 전달할 최종 메시지 리스트를 만드는 과정
            messages_for_inference = list(chat_history)
            messages_for_inference.append(HumanMessage(content=user_input))
            
            # AI 모델은 [이전 대화 내역 + 현재 질문]에 더해 [참고해야 할 이력서 데이터]까지 한꺼번에 전달 받게 된다
            if context_message:
                messages_for_inference.append(context_message)

            # LLM 응답 생성
            print("\n(AI가 생각 중입니다... 내용을 분석하고 있습니다...)")
            response = llm.invoke(messages_for_inference)
            
            # AI가 생성한 답변 중 텍스트 내용(content)만 추출하여 화면에 출력
            print(f"\nAI 면접관: {response.content}")

            # 실제 대화 기록에는 User Input과 AI Response만 저장 (Context는 중복 저장 안 함)
            # 방금 나눈 대화를 메모리(대화 기록)에 저장하여, 다음 질문을 했을 때 AI가 앞선 내용을 기억할 수 있게 만드는 과정
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(response)

        except KeyboardInterrupt:
            print("\n\n면접이 강제로 종료되었습니다.")
            break
        except Exception as e:
            print(f"\n오류가 발생했습니다: {e}")
            break

if __name__ == "__main__":
    main()
