import json
import os
import logging
import collections
from ..database import get_db_connection, logger
from ..services.llm_service import client
from ..services.pdf_service import convert_pdf_to_images
from ..config import UPLOAD_FOLDER

def get_video_analysis_summary(interview_number):
    """
    Reads the video log JSON for the interview and returns a summary string.
    """
    log_path = os.path.join(UPLOAD_FOLDER, "video_logs", f"{interview_number}.json")
    if not os.path.exists(log_path):
        return "비디오 분석 데이터가 없습니다."
        
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
            
        if not logs:
            return "비디오 분석 데이터가 비어 있습니다."
            
        total_frames = len(logs)
        emotions = []
        gaze_avoidance_count = 0
        bad_posture_count = 0
        hand_fidgeting_count = 0
        
        for log in logs:
            # Emotion
            if "emotion" in log and log["emotion"]:
                emotions.append(log["emotion"])
            
            # Gaze (Placeholder logic: if face not detected or specific gaze flag)
            # In real implementation, we would check specific landmarks
            if log.get("face_mesh") != "detected": 
                 # Assuming if face mesh didn't detect efficiently or logic was added
                 pass 
            
            # Posture (Placeholder)
            if log.get("pose") == "bad_posture": # Placeholder if we added logic
                bad_posture_count += 1
                
            # Hands
            if log.get("hands", 0) > 0:
                hand_fidgeting_count += 1

        emotion_counts = collections.Counter(emotions)
        top_emotions = emotion_counts.most_common(3)
        emotion_summary = ", ".join([f"{e}: {c}회" for e, c in top_emotions])
        
        summary = f"""
        [비디오 분석 요약]
        - 총 분석 프레임: {total_frames}
        - 주요 감정: {emotion_summary}
        - 손 움직임 감지 프레임: {hand_fidgeting_count} (손을 자주 움직이는지 참고)
        - (참고: 자세 및 시선 분석은 현재 감지된 프레임 수만 집계됨)
        """
        return summary

    except Exception as e:
        logger.error(f"Error reading video logs: {e}")
        return "비디오 분석 데이터 처리 중 오류 발생."

def get_recent_video_log_summary(interview_number: str, duration_seconds: int = 60) -> str:
    """
    Retrieves video logs for the specified interview_number within the last 'duration_seconds'.
    Returns a text summary of emotions and posture.
    """
    log_path = os.path.join(UPLOAD_FOLDER, "video_logs", f"{interview_number}.json")
    if not os.path.exists(log_path):
        return ""

    try:
        import time
        current_time = time.time()
        start_time = current_time - duration_seconds

        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)

        if not logs:
            return ""

        # Filter logs by timestamp if available, else take last N
        recent_logs = []
        for log in logs:
            # Assuming log has 'timestamp', if not, we can't filter by time accurately
            # But the video_router adds it.
            if "timestamp" in log:
                 if log["timestamp"] >= start_time:
                     recent_logs.append(log)
            else:
                # If no timestamp, fallback to taking the last portion (heuristic)
                # This is a fallback
                pass
        
        # If we found no time-based logs (maybe old format), take last 30 frames ~ 1 sec @ 30fps? 
        # Actually simulation might be slow. Let's just create a summary of whatever we found.
        if not recent_logs:
             # If strictly no logs in time window, maybe return empty or last few 
             return ""
        
        emotions = [log["emotion"] for log in recent_logs if log.get("emotion")]
        
        # Count analysis
        emotion_counts = collections.Counter(emotions)
        top_emotion = emotion_counts.most_common(1)
        top_emotion_str = top_emotion[0][0] if top_emotion else "분석불가"
        
        bad_posture = sum(1 for log in recent_logs if log.get("pose") == "bad_posture")
        
        summary = f"[영상분석] 주 감정: {top_emotion_str}, 분석 프레임: {len(recent_logs)}"
        return summary

    except Exception as e:
        logger.error(f"Error getting recent video logs: {e}")
        return ""

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
            
        # Get Video Analysis Summary
        video_summary = get_video_analysis_summary(interview_number)
            
        prompt = f"""
        당신은 면접관입니다. 다음은 지원자의 전체 면접 기록과 비디오 분석 결과입니다.
        이를 바탕으로 종합적으로 평가해주세요.
        
        [면접 정보]
        지원자: {applicant_name}
        지원 직무: {announcement_title}
        직무 내용: {announcement_job}
        
        [비디오 태도 분석 데이터]
        {video_summary}
        
        [면접 기록]
        {interview_log}
        
        [평가 루브릭 (Evaluation Rubric)]
        아래 기준에 따라 4가지 항목을 평가하고 점수를 매겨주세요.
        
        1. 기술 / 직무 (Tech)
        - 최우수 (100~81): 해당 분야의 독보적인 전문성을 갖춤. 실무에 즉시 투입되어 성과를 낼 수 있는 수준.
        - 우수 (80~61): 직무에 필요한 핵심 기술을 잘 이해하고 있으며, 관련 경험이 풍부함.
        - 보통 (60~41): 기초적인 지식은 갖추고 있으나 실무 적용을 위해 추가 교육이 필요함.
        - 미흡 (40~21): 직무 이해도가 낮으며, 기술적 기초가 부족함.
        - 부족 (20~0): 직무 수행을 위한 최소한의 지식이나 기술이 전무함.

        2. 문제해결 (Problem Solving)
        - 최우수 (100~81): 복잡한 상황에서도 논리적이고 창의적인 대안을 제시하며 실행력이 뛰어남.
        - 우수 (80~61): 당면한 문제를 정확히 파악하고 적절한 해결 방법을 찾아 실행함.
        - 보통 (60~41): 일반적인 수준의 문제 해결 능력은 있으나 창의성이나 논리성이 다소 부족함.
        - 미흡 (40~21): 문제의 본질을 파악하지 못하거나 수동적인 태도를 보임.
        - 부족 (20~0): 문제 상황에서 대처 능력이 없으며 포기하는 경향이 있음.

        3. 의사소통 (Communication)
        - 최우수 (100~81): 자신의 의견을 명확하고 설득력 있게 전달하며 상대의 의도를 완벽히 파악함.
        - 우수 (80~61): 논리적으로 의사를 표현하고 경청의 태도가 좋음.
        - 보통 (60~41): 기본적인 의사 전달은 가능하나 설득력이나 전달력이 다소 미흡함.
        - 미흡 (40~21): 질문의 의도를 잘 파악하지 못하거나 답변이 횡설수설함.
        - 부족 (20~0): 타인과의 소통이 원활하지 않으며 부정확한 표현을 사용함.

        4. 태도 / 인성 (Attitude / Personality) -> DB에는 'non_verbal' 컬럼에 저장됩니다.
        - 비디오 분석 데이터(감정, 손 움직임 등)와 답변의 태도를 종합하여 평가하세요.
        - 최우수 (100~81): 조직의 가치와 부합하며, 매우 긍정적이고 주도적인 성장의지를 보임. (비디오: 자신감 있는 표정, 안정된 자세)
        - 우수 (80~61): 전문적인 태도를 갖추었으며 성실함과 협업 의지가 확인됨.
        - 보통 (60~41): 평이한 태도를 보이며 조직 적응에 큰 문제는 없어 보임.
        - 미흡 (40~21): 태도가 다소 소극적이거나 조직 문화와 충돌할 가능성이 보임. (비디오: 잦은 시선 회피, 불안한 손동작 등 감지 시 감점 요인)
        - 부족 (20~0): 면접 태도가 불량하거나 직업 윤리 및 인성적 결함이 우려됨.

        [요청 사항]
        위 루브릭을 엄격하게 적용하여 평가해주세요.
        최종적으로 '합격' 또는 '불합격'을 결정해주세요.
        
        반드시 JSON 형식으로 반환해주세요.
        {{
            "tech_score": 85,
            "tech_eval": "(구체적인 평가 내용)",
            "problem_solving_score": 80,
            "problem_solving_eval": "(구체적인 평가 내용)",
            "communication_score": 90,
            "communication_eval": "(구체적인 평가 내용)",
            "non_verbal_score": 88,
            "non_verbal_eval": "(구체적인 평가 내용 - 비디오 분석 결과 포함하여 서술)",
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
