
import json
import os
import time
import warnings
import google.generativeai as genai
from ..config import GOOGLE_API_KEY, logger
from ..database import get_db_connection
from google.api_core.exceptions import ResourceExhausted

# Suppress Google GenAI FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

# Initialize Gemini Client
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY is missing. Please set it in .env file.")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

# Use Gemini 2.0 Flash
MODEL_NAME = "gemini-2.0-flash"

def get_model():
    return genai.GenerativeModel(MODEL_NAME)

def generate_content_with_retry(model, prompt, generation_config=None, max_retries=3):
    """
    Helper function to generate content with retry logic for rate limits.
    """
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
            return response
        except ResourceExhausted:
            wait_time = (2 ** attempt) + 1  # Exponential backoff + jitter-ish
            logger.warning(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        except Exception as e:
            # If it's a blocked prompt or other safety issue, we might want to catch it specifically,
            # but for now, re-raising is okay or handle gracefully.
            raise e
    raise ResourceExhausted("Max retries exceeded")

def clean_json_string(json_str):
    """
    Cleans markdown code blocks from JSON string.
    """
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
    return json_str.strip()

def get_job_questions(job_title):
    """
    Fetches questions for a job title.
    If not in pool, selects from interview_answer using LLM and saves to pool.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Check Pool
    c.execute("SELECT question_id FROM job_question_pool WHERE job_title = %s", (job_title,))
    rows = c.fetchall()
    
    if rows:
        # Fetch actual question text
        question_ids = [row[0] for row in rows]
        # Dynamically build query for IN clause
        placeholders = ','.join(['%s'] * len(question_ids))
        c.execute(f"SELECT question FROM interview_answer WHERE id IN ({placeholders})", tuple(question_ids))
        questions = [r[0] for r in c.fetchall()]
        conn.close()
        return questions

    # 2. If no pool, create one
    logger.info(f"No pool found for {job_title}. Creating one using LLM...")
    c.execute("SELECT id, question FROM interview_answer") # Fetch ALL questions
    all_questions = c.fetchall() # list of (id, question)
    
    if not all_questions:
        conn.close()
        return ["자기소개를 해주세요."]

    # Convert to JSON for LLM
    questions_json = [{"id": q[0], "question": q[1]} for q in all_questions]
    
    # Selecting fewer questions context to fit in generic limits if needed, 
    # but Gemini Flash has large context window so 300 is fine.
    
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
             # If LLM fails, pick random 5
             selected_ids = [q[0] for q in all_questions[:5]]

        # Save to Pool
        for q_id in selected_ids:
            c.execute("INSERT INTO job_question_pool (job_title, question_id) VALUES (%s, %s)", (job_title, q_id))
        
        conn.commit()
        
        # Return text
        # Make sure selected_ids is not empty tuple for ANY syntax
        if not selected_ids:
             questions = ["자기소개를 부탁드립니다."]
        else:
             c.execute(f"SELECT question FROM interview_answer WHERE id = ANY(%s)", (selected_ids,))
             questions = [r[0] for r in c.fetchall()]
             
        conn.close()
        return questions


    except Exception as e:
        logger.error(f"LLM Pool Creation Error: {e}")
        conn.close()
        return ["자기소개를 부탁드립니다.", "성격의 장단점은 무엇인가요?"]


def summarize_resume(text):
    """
    Summarizes the resume text using LLM to extract key skills, experience, and projects.
    """
    logger.info("Summarizing resume...")
    if not text:
        return "내용 없음"
        
    # If text is short enough, just return it
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
        logger.info(f"Resume Summary: {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Resume Summary Error: {e}")
        return text[:1000] # Fallback to truncation

def evaluate_answer(job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase, resume_summary=None, ref_questions=None, history_questions=None):
    """
    Evaluates the applicant's answer and generates the next question or closing remark.
    Enhanced to use Resume Summary and Reference Questions from Pool.
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
             logger.error(f"Evaluation Error (END): {e}")
             return "평가 실패", "면접이 종료되었습니다."
         
    else:
        # Construct Context for Prompt
        resume_context = ""
        if resume_summary:
            resume_context = f"""
            [지원자 이력서 요약]
            {resume_summary}
            """
            
        ref_context = ""
        if ref_questions:
            # Join top 3-5 questions
            ref_questions_list = list(ref_questions) # ensure list
            # Avoid error if ref_questions has integers or other types
            ref_q_text = "\\n".join([f"- {str(q)}" for q in ref_questions_list[:5]])
            ref_context = f"""
            [직무 관련 참고 질문 (질문 생성 시 참고용)]
            {ref_q_text}
            """

        history_context = ""
        if history_questions:
            # Join previous questions
            history_questions_list = list(history_questions)
            hist_text = "\\n".join([f"- {str(q)}" for q in history_questions_list])
            history_context = f"""
            [이미 질문한 내역 (중복 질문 절대 금지)]
            {hist_text}
            
            ※ 주의: 위 [이미 질문한 내역]에 있는 질문들과 의미가 유사하거나 겹치는 질문은 절대로 다시 하지 마세요. 새로운 관점이나 더 깊이 있는 질문을 해주세요.
            """

        prompt = f"""
        [상황]
        직무: {job_title}
        면접자: {applicant_name}
        현재 진행 단계: {current_q_count}번째 질문 완료. 다음은 {current_q_count + 1}번째 질문인 [{next_phase}] 단계입니다.
        
        {resume_context}
        {ref_context}
        {history_context}

        [이전 질문]
        {prev_question}
        
        [지원자 답변]
        {applicant_answer}
        
        [작업 1] 이 답변을 평가해주세요. (관리자용, 지원자에게 보이지 않음, 장단점 및 점수 포함)
        - 만약 답변이 "답변 없음"이라면, "답변을 하지 않았습니다."라고 평가하고 점수를 매우 낮게(0-10점 사이) 책정하세요.
        - 답변이 중단되었거나 불완전하더라도 지금까지 말한 음성 답변만으로 최선을 다해 평가하세요.
        
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
             logger.error("LLM Quota Exceeded")
             return "평가 실패 (사용량 초과)", "다음 질문으로 넘어가겠습니다. (잠시 후 다시 시도해주세요)"
        except Exception as e:
            logger.error(f"Evaluation Error: {e}")
            if 'response' in locals():
                logger.error(f"Response Text: {response.text}")
            return "평가 중 오류 발생", "다음 질문으로 넘어가겠습니다."
