import requests
import time

BASE_URL = "http://127.0.0.1:8000/api/interview"

def run_interview():
    print("1. Starting Interview...")
    try:
        start_res = requests.post(f"{BASE_URL}/start", data={
            "user_id": 1,
            "job_role": "Python Developer",
            "candidate_name": "TestCandidate"
        })
        start_data = start_res.json()
        print(f"Start Response: {start_data}")
        
        session_id = start_data.get("session_id")
        if not session_id:
            print("Failed to start session.")
            return

        current_step = start_data.get("step")
        
        # Loop through a few steps
        for i in range(1, 12): # Try to go past 10
            print(f"\n--- Step {current_step} ---")
            
            # Simulated answer
            answer_text = f"This is a test answer for step {current_step}. I am explaining my experience relevant to the question."
            
            print(f"Submitting Answer: {answer_text}")
            submit_res = requests.post(f"{BASE_URL}/submit", data={
                "session_id": session_id,
                "answer_text": answer_text
            })
            
            submit_data = submit_res.json()
            print(f"Evaluation: {submit_data.get('evaluation')}")
            print(f"Next Question: {submit_data.get('next_question')}")
            
            current_step = submit_data.get("step")
            is_completed = submit_data.get("is_completed")
            
            if is_completed:
                print("\nInterview Completed!")
                break
                
            time.sleep(1)

    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    run_interview()
