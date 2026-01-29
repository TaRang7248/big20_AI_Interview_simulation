import requests
import json
import time

BASE_URL = "http://127.0.0.1:8001"

def test_pipeline():
    print("Testing Pipeline...")

    # 1. Get First Question
    try:
        resp = requests.get(f"{BASE_URL}/interview/question")
        resp.raise_for_status()
        data = resp.json()
        question = data.get("question")
        print(f"[SUCCESS] Got first question: {question}")
    except Exception as e:
        print(f"[FAILURE] Get question failed: {e}")
        return

    # 2. Submit Answer
    answer_text = "저는 딥러닝에서 오버피팅을 방지하기 위해 드롭아웃을 사용해본 경험이 있습니다."
    print(f"Submitting answer: {answer_text}")
    
    payload = {
        "question": question,
        "answer": answer_text
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/interview/answer", json=payload)
        resp.raise_for_status()
        result = resp.json()
        print(f"[SUCCESS] Got evaluation: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"[FAILURE] Submit answer failed: {e}")
        return

    # 3. Get Follow-up Question
    try:
        resp = requests.get(f"{BASE_URL}/interview/question", params={"last_answer": answer_text})
        resp.raise_for_status()
        data = resp.json()
        follow_up_question = data.get("question")
        print(f"[SUCCESS] Got follow-up question: {follow_up_question}")
        
        # Check if it's related (naive check)
        if "드롭아웃" in follow_up_question or "오버피팅" in follow_up_question or "딥러닝" in follow_up_question or "규제" in follow_up_question:
             print("[SUCCESS] Follow-up question seems related.")
        else:
             print("[WARNING] Follow-up question might not be related. Please check manually.")
             
    except Exception as e:
        print(f"[FAILURE] Get follow-up question failed: {e}")
        return

if __name__ == "__main__":
    test_pipeline()
