# Llama 3을 활용한 간단한 텍스트 기반 AI 면접 프로그램
# LangChain 라이브러리를 사용하여 Llama 3 모델과 대화하며, 면접관 페르소나를 가진 AI가 질문을 하고 사용자가 답하는 방식으로 구현

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
# AI 대화에 쓰이는 메시지 타입을 정의
# HumanMessage: 사용자가 입력한 메시지
# AIMessage: AI가 생성한 메시지
# SystemMessage: AI의 인격(페르소나)과 규칙을 부여하는 메시지
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 정규 표현식(Regular Expression)을 사용하는 도구
import re
# 날짜와 시간을 다루는 도구
from datetime import datetime
# 리스트 안의 단어 빈도 수를 세는 도구
from collections import Counter

# 프로젝트 루트에서 .env 파일을 찾기 위해 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# 프로젝트 폴더에 있는 .env 파일에 적힌 설정값들을 읽어서 파이썬 프로그램이 사용할 수 있도록 환경 변수로 등록해주는 함수
load_dotenv()

# LLM 모델 설정 (환경변수로 오버라이드 가능)
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
DEFAULT_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7")) 


class InterviewReportGenerator:
    """
    면접 종료 후 STAR 기법 기반 종합 리포트를 생성하는 클래스
    - STAR 기법(Situation, Task, Action, Result) 분석
    - 핵심 키워드 추출
    - 답변 구조 평가
    - 발화 속도/발음 명확성/시선 처리 등 비언어적 요소 분석 (화상 면접 내용 바탕)
    """
    
    def __init__(self, llm):
        self.llm = llm
        # STAR 기법 관련 키워드 정의
        self.star_keywords = {
            'situation': ['상황', '배경', '당시', '그때', '환경', '상태', '문제', '이슈', '과제'],
            'task': ['목표', '과제', '임무', '역할', '담당', '책임', '해야 할', '목적', '미션'],
            'action': ['행동', '수행', '실행', '처리', '해결', '개발', '구현', '적용', '진행', '시도', '노력'],
            'result': ['결과', '성과', '달성', '완료', '개선', '향상', '증가', '감소', '효과', '성공', '실패에서 배운']
        }
        # IT 관련 핵심 키워드 (기술 스택)
        self.tech_keywords = [
            'python', 'java', 'javascript', 'typescript', 'react', 'vue', 'angular', 'node',
            'django', 'flask', 'spring', 'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'sql', 'nosql', 'mongodb', 'postgresql', 'mysql', 'redis', 'kafka',
            'git', 'ci/cd', 'devops', 'agile', 'scrum', 'api', 'rest', 'graphql',
            'machine learning', 'deep learning', 'ai', '머신러닝', '딥러닝', '인공지능',
            'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn',
            '데이터', '분석', '모델', '알고리즘', '최적화', '테스트', '배포', 'LLM', 'RAG', 'LangChain', 'Spark', 'Hadoop',
            'Terraform', 'Linux', 'Prometheus', 'Grafana', 'Flutter', 'Swift', 'Kotlin', 'React Native', 
            'Next.js', 'Tailwind', 'Svelte', 'Redux', 'Go', 'C++', 'PHP', 'Ruby', 'FastAPI'
        ]
    
    def extract_user_answers(self, chat_history: list) -> list:
        """대화 기록에서 지원자의 답변만 추출"""
        answers = []
        for msg in chat_history:
            if isinstance(msg, HumanMessage):
                answers.append(msg.content)
        return answers
    
    def analyze_star_structure(self, answers: list) -> dict:
        """
        STAR 기법에 기반하여 답변 구조를 분석
        각 답변에서 S, T, A, R 요소가 얼마나 포함되어 있는지 평가
        """
        star_analysis = {
            'situation': {'count': 0, 'examples': []},
            'task': {'count': 0, 'examples': []},
            'action': {'count': 0, 'examples': []},
            'result': {'count': 0, 'examples': []}
        }
        
        for answer in answers:
            answer_lower = answer.lower()
            for star_element, keywords in self.star_keywords.items():
                for keyword in keywords:
                    if keyword in answer_lower:
                        star_analysis[star_element]['count'] += 1
                        # 키워드 주변 컨텍스트 추출 (최대 50자)
                        idx = answer_lower.find(keyword)
                        start = max(0, idx - 20)
                        end = min(len(answer), idx + len(keyword) + 30)
                        context = answer[start:end]
                        if context not in star_analysis[star_element]['examples']:
                            star_analysis[star_element]['examples'].append(f"...{context}...")
                        break  # 하나의 키워드만 카운트
        
        return star_analysis
    
    def extract_keywords(self, answers: list) -> dict:
        """답변에서 핵심 키워드 추출"""
        all_text = ' '.join(answers).lower()
        
        # 기술 키워드 추출
        found_tech_keywords = []
        for keyword in self.tech_keywords:
            if keyword.lower() in all_text:
                count = all_text.count(keyword.lower())
                found_tech_keywords.append((keyword, count))
        
        # 빈도순 정렬
        found_tech_keywords.sort(key=lambda x: x[1], reverse=True)
        
        # 답변 전체에서 2글자 이상의 한글 단어만 모두 골라낸다
        korean_words = re.findall(r'[가-힣]{2,}', all_text)
        # 골라낸 한글 단어들이 각각 몇 번씩 나왔는지 자동으로 계산
        word_freq = Counter(korean_words)
        
        # 불용어 제거
        stopwords = ['그래서', '그리고', '하지만', '그런데', '이것', '저것', '그것', '있습니다', 
                     '했습니다', '합니다', '입니다', '습니다', '것입니다', '였습니다', '됩니다']
        for sw in stopwords:
            if sw in word_freq:
                del word_freq[sw]
        
        return {
            'tech_keywords': found_tech_keywords[:10],  # 상위 10개
            'general_keywords': word_freq.most_common(15)  # 상위 15개
        }
    
    # 지원자가 답변을 얼마나 성실하고 길게 작성했는지 '양적인 측면'에서 분석하는 기능
    # 이 수치들은 단순한 숫자가 아니라 지원자의 '태도'를 보여주는 데이터가 된다
    def calculate_answer_metrics(self, answers: list) -> dict:
        """답변 관련 기본 메트릭 계산"""
        if not answers:
            return {'total_answers': 0, 'avg_length': 0, 'total_chars': 0}
        
        total_chars = sum(len(a) for a in answers)
        avg_length = total_chars / len(answers)
        
        # 답변 길이 분포
        short_answers = sum(1 for a in answers if len(a) < 50)
        medium_answers = sum(1 for a in answers if 50 <= len(a) < 200)
        long_answers = sum(1 for a in answers if len(a) >= 200)
        
        return {
            'total_answers': len(answers), # 총 답변 개수
            'avg_length': round(avg_length, 1), # 평균 길이를 소수점 첫째 자리까지 반올림
            'total_chars': total_chars, # 전체 글자 수
            'short_answers': short_answers, # 짧은 답변 개수
            'medium_answers': medium_answers, # 중간 답변 개수
            'long_answers': long_answers # 긴 답변 개수
        }
    
    def generate_star_feedback(self, star_analysis: dict) -> str:
        """STAR 분석 결과에 기반한 피드백 생성"""
        feedback = []
        
        total_elements = sum(star_analysis[k]['count'] for k in star_analysis)
        
        if total_elements == 0:
            return "⚠️ STAR 기법 요소가 거의 발견되지 않았습니다. 구체적인 상황, 과제, 행동, 결과를 포함하여 답변하면 더 효과적입니다."
        
        # 각 요소별 피드백
        element_names = {
            'situation': ('상황(Situation)', '당시 상황이나 배경'),
            'task': ('과제(Task)', '맡은 역할이나 해결해야 할 목표'),
            'action': ('행동(Action)', '구체적으로 수행한 행동'),
            'result': ('결과(Result)', '달성한 성과나 배운 점')
        }
        
        weak_elements = []
        strong_elements = []
        
        for element, (name, desc) in element_names.items():
            count = star_analysis[element]['count']
            if count == 0:
                weak_elements.append(f"{name}")
            elif count >= 3:
                strong_elements.append(f"{name}")
        
        if strong_elements:
            feedback.append(f"✅ 강점: {', '.join(strong_elements)} 요소가 잘 포함되어 있습니다.")
        
        if weak_elements:
            feedback.append(f"📝 개선 필요: {', '.join(weak_elements)} 요소를 더 보완하면 좋겠습니다.")
        
        return '\n'.join(feedback)
    
    def generate_ai_evaluation(self, chat_history: list, answers: list) -> str:
        """LLM을 사용하여 종합 평가 생성
        대화 기록(chat_history)과 지원자의 답변 리스트(answers)를 받아서 최종 평가 글(문자열)을 내놓는 함수
        """
        if not answers:
            return "답변이 없어 평가를 생성할 수 없습니다."
        
        # 대화 내용을 텍스트로 변환
        conversation_text = ""
        for msg in chat_history[1:]:  # 시스템 프롬프트 제외
            if isinstance(msg, AIMessage):
                conversation_text += f"면접관: {msg.content}\n"
            elif isinstance(msg, HumanMessage):
                conversation_text += f"지원자: {msg.content}\n"
        
        evaluation_prompt = f"""다음은 면접 대화 내용입니다. 지원자의 답변을 종합적으로 평가해주세요.

[면접 대화]
{conversation_text}

[평가 기준]
1. STAR 기법 활용도 (상황-과제-행동-결과 구조)
2. 답변의 구체성과 논리성
3. 기술적 역량 표현
4. 커뮤니케이션 능력
5. 개선이 필요한 부분

위 기준에 따라 지원자의 면접 답변을 평가하고, 각 항목별로 1~5점 척도로 점수를 매겨주세요. 평가한 결과를 바탕으로 합격 혹은 불합격 여부도 판단해주세요."""

        try:
            response = self.llm.invoke([HumanMessage(content=evaluation_prompt)])
            return response.content
        except Exception as e:
            return f"AI 평가 생성 중 오류 발생: {e}"
    
    def generate_report(self, chat_history: list, video_metrics: dict = None) -> str:
        """
        종합 리포트 생성
        
        Args:
            chat_history: 면접 대화 기록
            video_metrics: 비디오 면접 시 발화 속도, 발음 명확성, 시선 처리 데이터
        """
        print("\n" + "="*60)
        print("📊 면접 종합 리포트 생성 중...")
        print("="*60)
        
        # 지원자 답변 추출
        answers = self.extract_user_answers(chat_history)
        
        if not answers:
            return "분석할 답변이 없습니다."
        
        # 분석 수행
        star_analysis = self.analyze_star_structure(answers)
        keywords = self.extract_keywords(answers)
        metrics = self.calculate_answer_metrics(answers)
        star_feedback = self.generate_star_feedback(star_analysis)
        
        # 리포트 생성
        report = []
        report.append("\n" + "="*60)
        report.append("📋 AI 모의면접 종합 리포트")
        report.append(f"📅 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("="*60)
        
        # 1. 기본 통계
        report.append("\n[1] 📈 답변 기본 통계")
        report.append("-" * 40)
        report.append(f"  • 총 답변 수: {metrics['total_answers']}회")
        report.append(f"  • 평균 답변 길이: {metrics['avg_length']}자")
        report.append(f"  • 총 답변 분량: {metrics['total_chars']}자")
        report.append("  • 답변 길이 분포:")
        report.append(f"    - 짧은 답변(~50자): {metrics['short_answers']}회")
        report.append(f"    - 중간 답변(50~200자): {metrics['medium_answers']}회")
        report.append(f"    - 긴 답변(200자~): {metrics['long_answers']}회")
        
        # 2. STAR 기법 분석
        report.append("\n[2] ⭐ STAR 기법 분석")
        report.append("-" * 40)
        for element in ['situation', 'task', 'action', 'result']:
            element_kr = {'situation': '상황(S)', 'task': '과제(T)', 
                         'action': '행동(A)', 'result': '결과(R)'}[element]
            count = star_analysis[element]['count']
            bar = '█' * min(count, 10) + '░' * (10 - min(count, 10))
            report.append(f"  • {element_kr}: [{bar}] {count}회")
        
        report.append("\n  💡 STAR 피드백:")
        for line in star_feedback.split('\n'):
            report.append(f"     {line}")
        
        # 3. 핵심 키워드 분석
        report.append("\n[3] 🔑 핵심 키워드 분석")
        report.append("-" * 40)
        
        if keywords['tech_keywords']:
            report.append("  • 기술 키워드:")
            tech_str = ", ".join([f"{kw}({cnt}회)" for kw, cnt in keywords['tech_keywords'][:5]])
            report.append(f"    {tech_str}")
        
        if keywords['general_keywords']:
            report.append("  • 주요 표현:")
            general_str = ", ".join([f"{kw}({cnt}회)" for kw, cnt in keywords['general_keywords'][:8]])
            report.append(f"    {general_str}")
        
        # 4. 비디오 면접 메트릭 (제공된 경우)
        report.append("\n[4] 🎥 비언어적 커뮤니케이션 분석")
        report.append("-" * 40)
        if video_metrics:
            report.append(f"  • 발화 속도: {video_metrics.get('speech_rate', 'N/A')}")
            report.append(f"  • 발음 명확성: {video_metrics.get('pronunciation_clarity', 'N/A')}")
            report.append(f"  • 시선 처리: {video_metrics.get('eye_contact', 'N/A')}")
            report.append(f"  • 표정 분석: {video_metrics.get('facial_expression', 'N/A')}")
        else:
            report.append("  ℹ️ 텍스트 기반 면접으로 비언어적 분석이 제공되지 않습니다.")
            report.append("  💡 비디오 면접 모드에서 발화 속도, 발음 명확성, 시선 처리 분석이 가능합니다.")
        
        # 5. AI 종합 평가
        report.append("\n[5] 🤖 AI 종합 평가")
        report.append("-" * 40)
        print("  (AI가 면접 내용을 분석 중입니다...)")
        ai_evaluation = self.generate_ai_evaluation(chat_history, answers)
        for line in ai_evaluation.split('\n'):
            report.append(f"  {line}")
        
        # 6. 개선 제안
        report.append("\n[6] 📝 개선 제안")
        report.append("-" * 40)
        
        suggestions = []
        if metrics['short_answers'] > metrics['long_answers']:
            suggestions.append("• 답변을 더 구체적이고 상세하게 작성해보세요.")
        if star_analysis['result']['count'] < 2:
            suggestions.append("• 경험의 '결과'와 '성과'를 더 강조해보세요.")
        if star_analysis['action']['count'] < 2:
            suggestions.append("• 본인이 직접 수행한 '행동'을 더 구체적으로 설명해보세요.")
        if not keywords['tech_keywords']:
            suggestions.append("• 기술적인 용어와 도구를 더 활용해보세요.")
        
        if suggestions:
            for suggestion in suggestions:
                report.append(f"  {suggestion}")
        else:
            report.append("  ✅ 전반적으로 좋은 답변 구조를 보여주셨습니다!")
        
        report.append("\n" + "="*60)
        report.append("📋 리포트 생성 완료")
        report.append("="*60)
        
        return '\n'.join(report)


def main(): # 프로그램의 메인 로직을 담는 함수
    print("AI 면접 시스템을 시작합니다")

    # 환경 변수를 사용해 데이터베이스 연결 정보를 안전하게 가져오고, 이를 바탕으로 RAG(검색 증강 생성) 시스템을 초기화
    CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")
    
    if not CONNECTION_STRING:
        print("⚠️ 경고: POSTGRES_CONNECTION_STRING 환경변수가 설정되지 않았습니다.")
        print("   .env 파일에 데이터베이스 연결 정보를 설정해주세요.")
    
    # 객체 초기화: ResumeRAG 클래스 내부에서 SQLAlchemy를 통해 PostgreSQL(PGVector)에 접속
    # 지원자의 이력서 데이터를 조회할 준비를 마친다.
    try:
        rag = ResumeRAG(connection_string=CONNECTION_STRING)
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        print("   Docker 컨테이너가 실행 중인지, 연결 정보가 올바른지 확인해주세요.")
        return
    
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
    try:
        llm = ChatOllama(model=DEFAULT_LLM_MODEL, temperature=DEFAULT_LLM_TEMPERATURE)
        print(f"✅ LLM 모델 로드 완료: {DEFAULT_LLM_MODEL}")
    except Exception as e:
        print(f"❌ LLM 초기화 실패: {e}")
        print("   Ollama가 실행 중인지 확인해주세요: 'ollama serve'")
        return

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
                
                # 면접 종료 후 종합 리포트 생성
                generate_report = input("\n📊 면접 결과 리포트를 생성하시겠습니까? (y/n, default: y): ").strip().lower()
                if generate_report != 'n':
                    report_generator = InterviewReportGenerator(llm)
                    report = report_generator.generate_report(chat_history)
                    print(report)
                    
                    # 리포트 파일로 저장 여부 확인
                    save_report = input("\n💾 리포트를 파일로 저장하시겠습니까? (y/n, default: n): ").strip().lower()
                    if save_report == 'y':
                        try:
                            report_filename = f"interview_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            report_path = os.path.join(current_dir, report_filename)
                            with open(report_path, 'w', encoding='utf-8') as f:
                                f.write(report)
                            print(f"✅ 리포트가 저장되었습니다: {report_path}")
                        except IOError as e:
                            print(f"❌ 리포트 저장 실패: {e}")
                
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
            # 강제 종료 시에도 리포트 생성 옵션 제공
            try:
                generate_report = input("\n📊 면접 결과 리포트를 생성하시겠습니까? (y/n, default: n): ").strip().lower()
                if generate_report == 'y':
                    report_generator = InterviewReportGenerator(llm)
                    report = report_generator.generate_report(chat_history)
                    print(report)
            except (EOFError, KeyboardInterrupt):
                print("\n리포트 생성을 건너뜁니다.")
            break
        except Exception as e:
            print(f"\n오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()  # 디버깅을 위한 상세 에러 출력
            break
    
    print("\n면접 시스템을 종료합니다. 수고하셨습니다! 👋")

if __name__ == "__main__":
    main()
