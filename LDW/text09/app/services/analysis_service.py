import json
import os
import logging
from ..database import get_db_connection, logger
from ..services.llm_service import client
from ..services.pdf_service import convert_pdf_to_images

def analyze_interview_result(interview_number, job_title, applicant_name, id_name, announcement_id=None):
    logger.info(f"Analyzing interview result for {interview_number}...")
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Fetch Announcement Details (Title & Job Description)
        if announcement_id:
             c.execute("SELECT title, job FROM interview_announcement WHERE id = %s", (announcement_id,))
        else:
             c.execute("""
                SELECT title, job 
                FROM interview_announcement 
                WHERE title = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (job_title,))
        
        announcement_row = c.fetchone()
        
        announcement_title = announcement_row[0] if announcement_row else job_title
        announcement_job = announcement_row[1] if announcement_row else "직무 내용 없음"

        # Fetch all Q&A and session_name
        c.execute("""
            SELECT Create_Question, Question_answer, Answer_Evaluation, session_name
            FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id ASC
        """, (interview_number,))
        rows = c.fetchall()
        
        session_name = rows[0][3] if rows else "알 수 없음" 
        
        interview_log = ""
        for row in rows:
            q = row[0]
            a = row[1] if row[1] else "답변 없음"
            e = row[2] if row[2] else "평가 없음"
            interview_log += f"Q: {q}\nA: {a}\nEval: {e}\n\n"
            
        prompt = f"""
        당신은 면접관입니다. 다음은 지원자의 전체 면접 기록입니다.
        
        [면접 정보]
        지원자: {applicant_name}
        지원 직무: {announcement_title}
        직무 내용: {announcement_job}
        
        [면접 기록]
        {interview_log}
        
        [요청 사항]
        위 기록을 바탕으로 다음 4가지 항목을 평가하고 점수(0~100점)를 매겨주세요.
        1. 기술(직무 적합성): Tech
        2. 문제해결능력: Problem Solving
        3. 의사소통능력: Communication
        4. 비언어적 요소(태도, 성실성 등 답변 내용에서 유추): Non-verbal
        
        그리고 최종적으로 '합격' 또는 '불합격'을 결정해주세요.
        
        반드시 JSON 형식으로 반환해주세요.
        {{
            "tech_score": 85,
            "tech_eval": "기술적 이해도가 높음...",
            "problem_solving_score": 80,
            "problem_solving_eval": "논리적으로 접근함...",
            "communication_score": 90,
            "communication_eval": "명확하게 의사를 전달함...",
            "non_verbal_score": 88,
            "non_verbal_eval": "성실한 태도가 보임...",
            "pass_fail": "합격"
        }}
        pass_fail 값은 반드시 "합격" 또는 "불합격" 이어야 합니다.
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = completion.choices[0].message.content
        result = json.loads(content)
        
        pass_fail = result.get("pass_fail", "불합격")
        if pass_fail not in ["합격", "불합격"]:
             pass_fail = "불합격"
             
        c.execute("SELECT email FROM users WHERE id_name = %s", (id_name,))
        user_row = c.fetchone()
        user_email = user_row[0] if user_row else ""

        c.execute("""
            INSERT INTO Interview_Result (
                interview_number, 
                tech_score, tech_eval, 
                problem_solving_score, problem_solving_eval, 
                communication_score, communication_eval, 
                non_verbal_score, non_verbal_eval, 
                pass_fail,
                title, announcement_job,
                id_name, session_name,
                email,
                resume_image_path,
                announcement_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            interview_number,
            int(result.get("tech_score", 0)), result.get("tech_eval", ""),
            int(result.get("problem_solving_score", 0)), result.get("problem_solving_eval", ""),
            int(result.get("communication_score", 0)), result.get("communication_eval", ""),
            int(result.get("non_verbal_score", 0)), result.get("non_verbal_eval", ""),
            pass_fail,
            announcement_title, announcement_job,
            id_name, session_name,
            user_email,
            None,
            announcement_id
        ))
        
        conn.commit()
        
        # --- Generate Resume Images ---
        # 1. Find resume path
        c.execute("SELECT resume FROM interview_information WHERE id_name = %s AND job = %s ORDER BY created_at DESC LIMIT 1", (id_name, announcement_job))
        res_row = c.fetchone()
        if res_row:
             resume_path = res_row[0]
             if os.path.exists(resume_path):
                 image_folder = os.path.join("uploads", "resume_images", interview_number)
                 image_paths = convert_pdf_to_images(resume_path, image_folder)
                 
                 if image_paths:
                     # Update DB with image paths (JSON string)
                     c.execute("UPDATE Interview_Result SET resume_image_path = %s WHERE interview_number = %s", (json.dumps(image_paths), interview_number))
                     conn.commit()

        logger.info(f"Interview result saved for {interview_number}")
        
    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        try:
             c.execute("""
                INSERT INTO Interview_Result (
                    interview_number, 
                    tech_score, tech_eval, 
                    problem_solving_score, problem_solving_eval, 
                    communication_score, communication_eval, 
                    non_verbal_score, non_verbal_eval, 
                    pass_fail,
                    title, announcement_job,
                    id_name, session_name
                ) VALUES (%s, 0, '분석 실패', 0, '분석 실패', 0, '분석 실패', 0, '분석 실패', '보류', %s, '분석 중 오류 발생', %s, %s)
            """, (interview_number, job_title, id_name, session_name))
             conn.commit()
        except Exception as db_e:
             logger.error(f"Failed to write error record: {db_e}")

    finally:
        conn.close()
