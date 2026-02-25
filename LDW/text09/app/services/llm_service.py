import json
import os
import time
import warnings
import google.generativeai as genai
from ..config import GOOGLE_API_KEY, logger
from ..database import get_db_connection
from google.api_core.exceptions import ResourceExhausted

# Google GenAI FutureWarnings 무시
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

# Gemini 클라이언트 초기화
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY가 없습니다. .env 파일에 설정해주세요.")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

# Gemini 2.0 Flash 모델 사용
MODEL_NAME = "gemini-2.0-flash"

# Gemini 모델 인스턴스를 저장할 전역 변수 (싱글톤 패턴과 유사하게 사용)
_MODEL_INSTANCE = None

def get_model():
    """
    Gemini 모델 인스턴스를 불러옵니다.
    매번 생성하는 대신, 이미 생성된 인스턴스가 있다면 재사용하여 속도를 개선합니다.
    """
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        logger.info(f"새로운 {MODEL_NAME} 모델 인스턴스를 생성합니다.")
        _MODEL_INSTANCE = genai.GenerativeModel(MODEL_NAME)
    return _MODEL_INSTANCE

def generate_content_with_retry(model, prompt, generation_config=None, max_retries=3):
    """
    할당량 초과 및 시간 초과에 대비한 재시도 로직이 포함된 콘텐츠 생성 헬퍼 함수입니다.
    """
    # 타임아웃 설정 (일반적인 요청의 경우 30초)
    request_options = {"timeout": 30}

    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt, 
                generation_config=generation_config,
                request_options=request_options
            )
            return response
        except ResourceExhausted:
            wait_time = (2 ** attempt) + 1
            logger.warning(f"사용량 제한 초과. {wait_time}초 후 재시도합니다...")
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"GenAI 오류 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(1) # 기타 오류 발생 시 짧게 대기
    
    raise ResourceExhausted("최대 재시도 횟수를 초과했습니다.")

def clean_json_string(json_str):
    """
    JSON 문자열에서 마크다운 코드 블록을 제거합니다.
    """
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
    return json_str.strip()

def get_job_questions(job_title):
    """
    직무에 맞는 질문을 가져옵니다.
    풀에 없는 경우 LLM을 사용하여 interview_answer에서 선택하고 풀에 저장합니다.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. 풀 확인
    c.execute("SELECT question_id FROM job_question_pool WHERE job_title = %s", (job_title,))
    rows = c.fetchall()
    
    if rows:
        # 실제 질문 텍스트 가져오기
        question_ids = [row[0] for row in rows]
        # IN 절을 위한 동적 쿼리 생성
        placeholders = ','.join(['%s'] * len(question_ids))
        c.execute(f"SELECT question FROM interview_answer WHERE id IN ({placeholders})", tuple(question_ids))
        questions = [r[0] for r in c.fetchall()]
        conn.close()
        return questions

    # 2. 풀이 없는 경우 LLM을 사용하여 생성
    logger.info(f"{job_title}에 대한 풀을 찾을 수 없습니다. LLM을 사용하여 생성합니다...")
    c.execute("SELECT id, question FROM interview_answer") # 모든 질문 가져오기
    all_questions = c.fetchall() # (id, question) 리스트
    
    if not all_questions:
        conn.close()
        return ["자기소개를 해주세요."]

    # LLM을 위한 JSON 변환
    questions_json = [{"id": q[0], "question": q[1]} for q in all_questions]
    
    prompt = f"""
    당신은 채용 담당자입니다.
    지원 직무: {job_title}
    
    아래 전체 면접 질문 리스트에서 해당 직무에 가장 적합한 핵심 질문 5~10개를 선별해주세요.
    반드시 JSON 형식으로 ID 리스트만 반환해주세요. 
    
    질문 리스트:
    {json.dumps(questions_json[:500], ensure_ascii=False)} 
    (데이터가 많으면 일부만 전송됨)

    Response Schema:
    {{
        "ids": [1, 5, 10]
    }}
    """
    
    try:
        model = get_model()
        response = generate_content_with_retry(
            model,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        text_response = clean_json_string(response.text)
        result = json.loads(text_response)
        selected_ids = result.get("ids", [])
        
        if not selected_ids:
             # LLM 실패 시 랜덤하게 5개 선택
             selected_ids = [q[0] for q in all_questions[:5]]

        # 풀에 저장
        for q_id in selected_ids:
            c.execute("INSERT INTO job_question_pool (job_title, question_id) VALUES (%s, %s)", (job_title, q_id))
        
        conn.commit()
        
        # 텍스트 반환
        if not selected_ids:
             questions = ["자기소개를 부탁드립니다."]
        else:
             c.execute(f"SELECT question FROM interview_answer WHERE id = ANY(%s)", (selected_ids,))
             questions = [r[0] for r in c.fetchall()]
             
        conn.close()
        return questions

    except Exception as e:
        logger.error(f"LLM 풀 생성 오류: {e}")
        conn.close()
        return ["자기소개를 부탁드립니다.", "성격의 장단점은 무엇인가요?"]

def summarize_resume(text):
    """
    LLM을 사용하여 이력서 텍스트에서 핵심 기술, 경험 및 프로젝트를 요약합니다.
    """
    logger.info("이력서 요약 중...")
    if not text:
        return "내용 없음"
        
    # 텍스트가 충분히 짧으면 그대로 반환
    if len(text) < 500:
        return text

    prompt = f"""
    아래 이력서 내용에서 면접 질문 생성에 필요한 핵심 정보를 요약해주세요.
    다음 항목 위주로 정리해주세요:
    1. 핵심 역량 (Tech Stack, Tools)
    2. 주요 프로젝트 경험 (무엇을 했는지, 어떤 성과가 있는지)
    3. 경력 사항 요약
    
    이력서 내용:
    {text[:10000]} 
    (내용이 너무 길면 앞부분만 참조함)
    """

    try:
        model = get_model()
        response = generate_content_with_retry(model, prompt)
        summary = response.text
        logger.info(f"이력서 요약: {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"이력서 요약 오류: {e}")
        return text[:1000] # 실패 시 잘라서 반환

def evaluate_answer(job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase, resume_summary=None, ref_questions=None, history_questions=None, audio_analysis=None):
    """
    지원자의 답변을 평가하고 다음 질문 또는 마무리 멘트를 생성합니다.
    이력서 요약 및 풀의 참고 질문을 사용하도록 강화되었습니다.
    """
    model = get_model()
    
    if next_phase == "END":
         evaluation_prompt = f"""
         [상황]
         직무: {job_title}
         면접자: {applicant_name}
         마무리 질문에 대한 답변: {applicant_answer}
         
         [작업]
         - 만약 답변이 "답변 없음"이라면, "지원자가 마지막 발언을 하지 않았습니다."라고 평가하고 성실성 부분에서 낮은 평가를 주세요.
         - 답변이 있다면 그 내용을 바탕으로 간단히 평가해주세요. (관리자용)
         """
         try:
             response = generate_content_with_retry(model, evaluation_prompt)
             evaluation = response.text
             next_question = "면접이 종료되었습니다. 수고하셨습니다."
             return evaluation, next_question
         except Exception as e:
             logger.error(f"평가 오류 (종료 단계): {e}")
             return "평가 실패", "면접이 종료되었습니다."
         
    else:
        # 프롬프트를 위한 컨텍스트 구성
        resume_context = ""
        if resume_summary:
            resume_context = f"""
            [지원자 이력서 요약]
            {resume_summary}
            """
            
        ref_context = ""
        if ref_questions:
            ref_questions_list = list(ref_questions)
            ref_q_text = "\\n".join([f"- {str(q)}" for q in ref_questions_list[:5]])
            ref_context = f"""
            [직무 관련 참고 질문 (질문 생성 시 참고용)]
            {ref_q_text}
            """

        history_context = ""
        if history_questions:
            history_questions_list = list(history_questions)
            hist_text = "\\n".join([f"- {str(q)}" for q in history_questions_list])
            history_context = f"""
            [이미 질문한 내역 (중복 질문 절대 금지)]
            {hist_text}
            
            ※ 주의: 위 [이미 질문한 내역]에 있는 질문들과 의미가 유사하거나 겹치는 질문은 절대로 다시 하지 마세요. 새로운 관점이나 더 깊이 있는 질문을 해주세요.
            """

        analysis_context = ""
        if audio_analysis:
            analysis_context = f"""
            [오디오/비언어적 분석 데이터 (참고용)]
            - 목소리 떨림(Jitter): {audio_analysis.get('pitch_jitter', 0)}% (높을수록 떨림, 1.0% 이상이면 불안정)
            - 목소리 진폭 변동(Shimmer): {audio_analysis.get('pitch_shimmer', 0)}% (높을수록 성량 불안정, 3.8% 이상이면 불안정)
            - 말하기 속도: {audio_analysis.get('speech_rate', 0)} 음절/초 (피드백: {audio_analysis.get('speed_feedback', '알수없음')})
            - 무음(침묵) 시간: {audio_analysis.get('silence_duration', 0)}초
            - 자신감 점수: {audio_analysis.get('confidence_score', 0)} / 100
            
            ※ 평가 시 위 데이터를 참고하여 지원자의 태도(자신감, 긴장도, 전달력)를 구체적으로 평가에 반영해주세요. 
            예: "목소리 떨림이 감지되어 긴장한 것으로 보이나...", "말하기 속도가 침착하여..."
            """

        prompt = f"""
        [상황]
        직무: {job_title}
        면접자: {applicant_name}
        현재 진행 단계: {current_q_count}번째 질문 완료. 다음은 {current_q_count + 1}번째 질문인 [{next_phase}] 단계입니다.
        
        {resume_context}
        {ref_context}
        {history_context}
        {analysis_context}

        [이전 질문]
        {prev_question}
        
        [지원자 답변]
        {applicant_answer}
        
        [작업 1] 이 답변을 평가해주세요. (관리자용, 지원자에게 보이지 않음, 장단점 및 점수 포함)
        - 만약 답변이 "답변 없음"이라면, "답변을 하지 않았습니다."라고 평가하고 점수를 매우 낮게(0-10점 사이) 책정하세요.
        - 답변이 중단되었거나 불완전하더라도 지금까지 말한 음성 답변만으로 최선을 다해 평가하세요.
        - [오디오/비언어적 분석 데이터]가 있다면 이를 적극적으로 해석하여 태도 점수에 반영하세요.
                
        [작업 2] 다음 질문을 생성해주세요.
        - 다음 단계([{next_phase}])에 맞는 질문이어야 합니다.
        - [지원자 이력서 요약]이 있다면, 해당 내용을 검증하거나 구체적인 경험을 묻는 질문을 우선적으로 생성하세요.
        - [직무 관련 참고 질문]이 있다면, 그 질문들과 유사한 맥락이거나 그 중 하나를 상황에 맞게 변형하여 질문하세요.
        - 이미 질문한 내용과 중복되지 않도록 주의하세요.
        - 이전 답변과 자연스럽게 이어지거나, 새로운 주제로 전환하세요.
        - 질문은 구어체로 정중하게 1~2문장으로 작성해주세요.
        
        [출력 형식]
        JSON 형식으로만 출력해주세요. 마크다운 코드 블록(```json ... ```)은 사용하지 마세요.
        {{
            "evaluation": "평가 내용...",
            "next_question": "다음 질문 내용..."
        }}
        """
        
        try:
            response = generate_content_with_retry(
                model, 
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            text_response = clean_json_string(response.text)
            result = json.loads(text_response)
            return result.get("evaluation", "평가 없음"), result.get("next_question", "다음 질문을 준비하지 못했습니다.")
        except ResourceExhausted:
             logger.error("LLM 할당량 초과")
             return "평가 실패 (사용량 초과)", "다음 질문으로 넘어가겠습니다. (잠시 후 다시 시도해주세요)"
        except Exception as e:
            logger.error(f"평가 오류: {e}")
            if 'response' in locals():
                logger.error(f"응답 텍스트: {response.text}")
            return "평가 중 오류 발생", "다음 질문으로 넘어가겠습니다."
