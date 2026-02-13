import json
from openai import OpenAI
from ..config import OPENAI_API_KEY, logger
from ..database import get_db_connection

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

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
    
    prompt = f"""
    당신은 채용 담당자입니다.
    지원 직무: {job_title}
    
    아래 전체 면접 질문 리스트에서 해당 직무에 가장 적합한 핵심 질문 5~10개를 선별해주세요.
    반드시 JSON 형식으로 ID 리스트만 반환해주세요. 예: [1, 5, 10, ...]
    
    질문 리스트:
    {json.dumps(questions_json[:300], ensure_ascii=False)} 
    (데이터가 많으면 일부만 전송됨)
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content)
        selected_ids = result.get("ids", [])
        
        # fallback if json structure is different
        if not selected_ids and "usage" not in result: # just in case
             pass

        if not selected_ids:
             # If LLM fails, pick random 5
             selected_ids = [q[0] for q in all_questions[:5]]

        # Save to Pool
        for q_id in selected_ids:
            c.execute("INSERT INTO job_question_pool (job_title, question_id) VALUES (%s, %s)", (job_title, q_id))
        
        conn.commit()
        
        # Return text
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
    {text[:4000]} 
    (내용이 너무 길면 앞부분 4000자만 참조함)
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        summary = completion.choices[0].message.content
        logger.info(f"Resume Summary: {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Resume Summary Error: {e}")
        return text[:1000] # Fallback to truncation

def evaluate_answer(job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase):
    """
    Evaluates the applicant's answer and generates the next question or closing remark.
    """
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
             completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": evaluation_prompt}]
             )
             evaluation = completion.choices[0].message.content
             next_question = "면접이 종료되었습니다. 수고하셨습니다."
             return evaluation, next_question
         except Exception as e:
             logger.error(f"Evaluation Error (END): {e}")
             return "평가 실패", "면접이 종료되었습니다."
         
    else:
        prompt = f"""
        [상황]
        직무: {job_title}
        면접자: {applicant_name}
        현재 진행 단계: {current_q_count}번째 질문 완료. 다음은 {current_q_count + 1}번째 질문인 [{next_phase}] 단계입니다.
        
        [이전 질문]
        {prev_question}
        
        [지원자 답변]
        {applicant_answer}
        
        [작업 1] 이 답변을 평가해주세요. (관리자용, 지원자에게 보이지 않음, 장단점 및 점수 포함)
        - 만약 답변이 "답변 없음"이라면, "답변을 하지 않았습니다."라고 평가하고 점수를 매우 낮게(0-10점 사이) 책정하세요.
        - 답변이 중단되었거나 불완전하더라도 지금까지 말한 음성 답변만으로 최선을 다해 평가하세요.
        
        [작업 2] 다음 질문을 생성해주세요.
        - 다음 단계([{next_phase}])에 맞는 질문이어야 합니다.
        - 이전 답변과 자연스럽게 이어지거나, 새로운 주제로 전환하세요.
        - 질문은 구어체로 정중하게 1~2문장으로 작성해주세요.
        
        [출력 형식]
        JSON 형식으로만 출력해주세요.
        {{
            "evaluation": "평가 내용...",
            "next_question": "다음 질문 내용..."
        }}
        """
        
        try:
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = json.loads(completion.choices[0].message.content)
            return result.get("evaluation", "평가 없음"), result.get("next_question", "다음 질문을 준비하지 못했습니다.")
        except Exception as e:
            logger.error(f"Evaluation Error: {e}")
            return "평가 중 오류 발생", "다음 질문으로 넘어가겠습니다."

