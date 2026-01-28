import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def test_pipeline():
    print("--- Testing /interview/question ---")
    try:
        resp = requests.get(f"{BASE_URL}/interview/question")
        resp.raise_for_status()
        question_data = resp.json()
        question = question_data.get("question")
        print(f"Question: {question}")
    except Exception as e:
        print(f"Error fetching question: {e}")
        return

    print("\n--- Testing /interview/answer ---")
    payload = {
        "question": question,
        "answer": "저는 대규모 트래픽 처리를 위해 Redis와 Kafka를 활용한 경험이 있으며, 데이터베이스 최적화에 전문성이 있습니다."
    }
    try:
        resp = requests.post(f"{BASE_URL}/interview/answer", json=payload)
        resp.raise_for_status()
        eval_data = resp.json()
        print(f"ID: {eval_data.get('id')}")
        print(f"Evaluation: {json.dumps(eval_data.get('evaluation'), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error submitting answer: {e}")

if __name__ == "__main__":
    test_pipeline()
